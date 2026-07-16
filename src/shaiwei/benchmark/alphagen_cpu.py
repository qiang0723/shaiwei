"""上游 AlphaGen 表达式/GP + 项目侧中性化 RankIC 的单轮 CPU benchmark。"""

import argparse
import csv
import hashlib
import json
import math
import os
import subprocess
import sys
import threading
import time
from datetime import date, datetime, timezone

import numpy as np
import pandas as pd
import psutil
import torch
import yaml

from shaiwei.benchmark.fitness import (
    benchmark_decision,
    industry_pit_exposure,
    neutralized_rank_ic,
    screened_rank_ic,
)
from shaiwei.backtest.qlib_runtime import initialize_qlib
from shaiwei.config import PROJECT_ROOT, load
from shaiwei.ingest.catalog import load_latest_api
from shaiwei.ledger import EXPERIMENTS, append_experiment, ingest_snapshot_sha256
from shaiwei.provenance import code_snapshot_sha256
from shaiwei.research.alphagen_expression import audit_expression, parse_safe_expression
from shaiwei.transform.qlib_bin import qlib_code


class PeakMemorySampler:
    def __init__(self, interval: float = 0.05):
        self.interval = interval
        self.peak_bytes = 0
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        process = psutil.Process(os.getpid())
        while not self._stop.wait(self.interval):
            try:
                processes = [process, *process.children(recursive=True)]
                rss = sum(child.memory_info().rss for child in processes if child.is_running())
            except (psutil.Error, ProcessLookupError):
                continue
            self.peak_bytes = max(self.peak_bytes, rss)

    def __enter__(self) -> "PeakMemorySampler":
        self.start()
        return self

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join()

    def __exit__(self, *_: object) -> None:
        self.stop()


def stock_data_effective_start(requested_start: date, max_backtrack_days: int) -> date:
    """Avoid AlphaGen's negative-calendar-index wrap at the dataset boundary."""
    from qlib.data import D

    calendar = D.calendar()
    requested_index = int(calendar.searchsorted(pd.Timestamp(requested_start)))
    if requested_index >= max_backtrack_days:
        return requested_start
    if len(calendar) <= max_backtrack_days:
        raise RuntimeError("qlib calendar is shorter than the required AlphaGen warm-up")
    return pd.Timestamp(calendar[max_backtrack_days]).date()


def _stage1_experiment_id(
    family: str,
    formula: str,
    code_hash: str,
    data_hash: str,
) -> str:
    payload = f"{family}|{formula}|{code_hash}|{data_hash}|generation-v1"
    return hashlib.sha256(payload.encode()).hexdigest()[:12]


def _existing_experiment(experiment_id: str) -> dict[str, str] | None:
    with EXPERIMENTS.open(newline="", encoding="utf-8") as handle:
        rows = [row for row in csv.DictReader(handle) if row["experiment_id"] == experiment_id]
    if len(rows) > 1:
        raise RuntimeError(f"duplicate deterministic experiment ID: {experiment_id}")
    return rows[0] if rows else None


def _append_stage1_once(*, experiment_id: str, **row: object) -> None:
    existing = _existing_experiment(experiment_id)
    if existing is not None:
        expected = {
            "candidate_source": str(row["candidate_source"]),
            "model_or_engine": str(row["model_or_engine"]),
            "engine_version": str(row["engine_version"]),
            "seed": str(row["seed"]),
            "code_sha256": str(row["code_sha256"]),
            "data_snapshot_sha256": str(row["data_snapshot_sha256"]),
            "feature_or_formula": str(row["feature_or_formula"]),
            "train_period": str(row["train_period"]),
            "valid_period": str(row["valid_period"]),
        }
        if any(existing[key] != value for key, value in expected.items()):
            raise RuntimeError(f"existing deterministic experiment differs: {experiment_id}")
        return
    append_experiment(experiment_id=experiment_id, **row)


def _load_exposures(instruments: set[str], start: date, end: date) -> pd.DataFrame:
    daily_basic = load_latest_api("tushare.daily_basic")
    exposures = daily_basic.loc[:, ["ts_code", "trade_date", "total_mv"]].copy()
    exposures["instrument"] = exposures["ts_code"].map(qlib_code)
    start_text = pd.Timestamp(start).strftime("%Y%m%d")
    end_text = pd.Timestamp(end).strftime("%Y%m%d")
    exposures = exposures.loc[
        exposures["instrument"].isin(instruments)
        & exposures["trade_date"].astype(str).between(start_text, end_text)
    ].copy()
    industry = industry_pit_exposure(
        exposures.loc[:, ["ts_code", "trade_date"]],
        load_latest_api("tushare.index_member_all"),
    )
    exposures["industry"] = industry["industry"].to_numpy()
    exposures["market_cap"] = pd.to_numeric(exposures["total_mv"], errors="coerce")
    exposures["trade_date"] = pd.to_datetime(exposures["trade_date"], format="%Y%m%d")
    return exposures.loc[:, ["trade_date", "instrument", "industry", "market_cap"]]


def _verify_vendor_checkout(vendor: os.PathLike[str]) -> str:
    lock = yaml.safe_load((PROJECT_ROOT / "config/externals.lock.yaml").read_text(encoding="utf-8"))
    expected = str(lock["alphagen"]["commit"])
    try:
        actual = subprocess.run(
            ["git", "-C", os.fspath(vendor), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except subprocess.CalledProcessError as error:
        raise RuntimeError("vendor/alphagen is not a verifiable git checkout") from error
    if actual != expected:
        raise RuntimeError(f"AlphaGen checkout mismatch: expected {expected}, got {actual}")
    return actual


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--research-family")
    parser.add_argument("--instrument")
    parser.add_argument("--index-code")
    parser.add_argument("--train-start", type=date.fromisoformat)
    parser.add_argument("--train-end", type=date.fromisoformat)
    parser.add_argument("--population-size", type=int)
    parser.add_argument("--tournament-size", type=int)
    args = parser.parse_args(argv)
    settings = load()
    config = settings.alphagen_benchmark
    updates = {
        key: value
        for key, value in {
            "train_start": args.train_start,
            "train_end": args.train_end,
            "instrument": args.instrument,
            "index_code": args.index_code,
            "population_size": args.population_size,
            "tournament_size": args.tournament_size,
        }.items()
        if value is not None
    }
    if updates:
        config = config.model_copy(update=updates)
        config = type(config).model_validate(config.model_dump())
    vendor = PROJECT_ROOT / "vendor" / "alphagen"
    if not (vendor / "gp.py").is_file():
        raise SystemExit("vendor/alphagen missing; clone the commit in config/externals.lock.yaml")
    upstream_commit = _verify_vendor_checkout(vendor)
    sys.path.insert(0, str(vendor))

    from alphagen.data.expression import Constant, OutOfDataRangeError, Ref
    from alphagen.utils.random import reseed_everything
    from alphagen_generic.features import close, high, low, open_, volume, vwap
    from alphagen_generic.operators import funcs as generic_funcs
    from alphagen_qlib import stock_data as alphagen_stock_data
    from alphagen_qlib.stock_data import StockData
    from gplearn.fitness import make_fitness
    from gplearn.functions import make_function
    from gplearn.genetic import SymbolicRegressor

    reseed_everything(config.seed)
    device = torch.device("cpu")
    memory = PeakMemorySampler()
    memory.start()
    benchmark_started = time.perf_counter()
    initialize_qlib(settings)
    # The locked upstream module otherwise calls qlib.init again with its
    # default ./mlruns recorder and overwrites the project-owned configuration.
    alphagen_stock_data._QLIB_INITIALIZED = True
    max_backtrack_days = 100
    effective_train_start = stock_data_effective_start(config.train_start, max_backtrack_days)
    if effective_train_start >= config.train_end:
        raise RuntimeError("effective AlphaGen training period is empty after warm-up")
    data = StockData(
        config.instrument,
        effective_train_start.isoformat(),
        config.train_end.isoformat(),
        max_backtrack_days=max_backtrack_days,
        max_future_days=settings.backtest.rebalance_days + 1,
        device=device,
    )
    target = Ref(open_, -(settings.backtest.rebalance_days + 1)) / Ref(open_, -1) - 1
    label = data.make_dataframe(target.evaluate(data), columns=["label"]).reset_index()
    label.columns = ["trade_date", "instrument", "label"]
    exposures = _load_exposures(
        set(label["instrument"].dropna().astype(str)),
        effective_train_start,
        config.train_end,
    )
    setup_elapsed = time.perf_counter() - benchmark_started
    cache: dict[str, dict[str, object]] = {}
    namespace = {
        **vars(sys.modules["alphagen.data.expression"]),
        "open_": open_, "close": close, "high": high, "low": low, "volume": volume, "vwap": vwap,
        "Constant": Constant,
    }

    def metric(_dummy: np.ndarray, generated: np.ndarray, _weight: np.ndarray) -> float:
        expression_text = str(generated[0])
        if expression_text in cache:
            return float(cache[expression_text]["fitness"])
        if expression_text.count("(") + expression_text.count(")") > config.max_expression_tokens:
            cache[expression_text] = {
                "rank_ic": -1.0,
                "fitness": -1.0,
                "error": "expression_too_long",
            }
            return -1.0
        try:
            expression = (
                parse_safe_expression(expression_text)
                if args.research_family
                else eval(expression_text, {"__builtins__": {}}, namespace)
            )
            factor = data.make_dataframe(expression.evaluate(data), columns=["factor"]).reset_index()
            factor.columns = ["trade_date", "instrument", "factor"]
            observations = factor.merge(label, on=["trade_date", "instrument"]).merge(
                exposures, on=["trade_date", "instrument"]
            )
            rank_ic, daily_ic = neutralized_rank_ic(observations, config.min_cross_section)
            score, error = screened_rank_ic(
                rank_ic,
                len(daily_ic),
                config.min_daily_ic_observations,
            )
            cache[expression_text] = {
                "rank_ic": score,
                "fitness": abs(score) if args.research_family and not error else score,
                "daily_ic_count": len(daily_ic),
                "error": error,
            }
        except (OutOfDataRangeError, TypeError, ValueError, RuntimeError) as error:
            cache[expression_text] = {
                "rank_ic": -1.0,
                "fitness": -1.0,
                "error": f"{type(error).__name__}: {error}",
            }
        return float(cache[expression_text]["fitness"])

    functions = [make_function(**function._asdict()) for function in generic_funcs]
    terminals = ["open_", "close", "high", "low", "volume", "vwap"] + [
        f"Constant({value})" for value in (-30.0, -10.0, -5.0, -2.0, -1.0, -0.5, -0.01, 0.01, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0)
    ]
    estimator = SymbolicRegressor(
        population_size=config.population_size,
        generations=config.generations,
        init_depth=(2, 6),
        tournament_size=config.tournament_size,
        stopping_criteria=1.0,
        p_crossover=0.3,
        p_subtree_mutation=0.1,
        p_hoist_mutation=0.01,
        p_point_mutation=0.1,
        p_point_replace=0.6,
        max_samples=0.9,
        verbose=1,
        parsimony_coefficient=0.0,
        random_state=config.seed,
        function_set=functions,
        metric=make_fitness(function=metric, greater_is_better=True, wrap=False),
        const_range=None,
        n_jobs=1,
    )
    evolution_started = time.perf_counter()
    estimator.fit(np.array([terminals]), np.array([[1]]))
    evolution_elapsed = time.perf_counter() - evolution_started
    elapsed = time.perf_counter() - benchmark_started
    memory.stop()
    expression_audits = {}
    if args.research_family:
        for expression_text, result in cache.items():
            try:
                expression_audits[expression_text] = audit_expression(expression_text)
            except ValueError as error:
                result["rank_ic"] = -1.0
                result["fitness"] = -1.0
                result["error"] = f"expression_safety:{type(error).__name__}"
    values = np.array([float(result["rank_ic"]) for result in cache.values()], dtype=float)
    best_rank_ic = float(values.max()) if len(values) else -1.0
    valid_abs_values = [
        abs(float(result["rank_ic"]))
        for result in cache.values()
        if not result["error"] and math.isfinite(float(result["rank_ic"]))
    ]
    best_selection_rank_ic = (
        max(valid_abs_values, default=-1.0) if args.research_family else best_rank_ic
    )
    summary = {
        "elapsed_seconds": elapsed,
        "setup_elapsed_seconds": setup_elapsed,
        "evolution_elapsed_seconds": evolution_elapsed,
        "peak_memory_bytes": memory.peak_bytes,
        "input_label_rows": len(label),
        "input_exposure_rows": len(exposures),
        "candidate_count": len(cache),
        "failed_candidate_count": sum(bool(result["error"]) for result in cache.values()),
        "min_daily_ic_observations": config.min_daily_ic_observations,
        "requested_train_start": config.train_start.isoformat(),
        "effective_train_start": effective_train_start.isoformat(),
        "rank_ic": {
            "min": float(values.min()), "median": float(np.median(values)), "max": best_rank_ic,
            "max_abs_valid": max(valid_abs_values, default=-1.0),
        },
        "decision": benchmark_decision(
            elapsed,
            best_selection_rank_ic,
            rank_ic_threshold=config.rank_ic_threshold,
            scale_hours=config.scale_time_hours,
            abort_hours=config.abort_time_hours,
        ),
        "industry_exposure": "SW L1 PIT (index_member_all in_date/out_date)",
        "device": str(device),
    }
    code_hash = code_snapshot_sha256()
    data_hash = ingest_snapshot_sha256()
    common = {
        "candidate_source": "AlphaGen-GP-stage1" if args.research_family else "AlphaGen-GP",
        "model_or_engine": "AlphaGen upstream GP + shaiwei neutralized RankIC",
        "engine_version": upstream_commit,
        "seed": config.seed,
        "prompt_hash": "",
        "code_sha256": code_hash,
        "data_snapshot_sha256": data_hash,
        "train_period": f"{effective_train_start}~{config.train_end}",
        "valid_period": (
            "stage1 bounded discovery preflight"
            if args.research_family
            else "single-round throughput benchmark"
        ),
        "admitted": False,
    }
    for expression_text, result in cache.items():
        params = config.model_dump(mode="json")
        if args.research_family:
            audit = expression_audits.get(expression_text)
            params.update(
                {
                    "g1_research_family": args.research_family,
                    "expression_tokens": (
                        audit.expression_tokens
                        if audit is not None
                        else settings.g1_admission.max_expression_tokens + 1
                    ),
                    "ast_nodes": (
                        audit.ast_nodes if audit is not None else settings.g1_admission.max_ast_nodes + 1
                    ),
                    "attempt_stage": "generation",
                }
            )
        row = {
            **common,
            "feature_or_formula": expression_text,
            "params_json": params,
            "result_json": result,
            "reject_reason": (
                str(result["error"])
                or (
                    "stage1 bounded generation attempt; pending full evidence"
                    if args.research_family
                    else "stage0 benchmark; not factor admission"
                )
            ),
        }
        if args.research_family:
            _append_stage1_once(
                experiment_id=_stage1_experiment_id(
                    args.research_family, expression_text, code_hash, data_hash
                ),
                **row,
            )
        else:
            append_experiment(**row)
    summary_row = {
        **common,
        "feature_or_formula": "BENCHMARK_SUMMARY",
        "params_json": config.model_dump(mode="json"),
        "result_json": summary,
        "reject_reason": (
            "stage1 bounded generation summary; not a candidate trial"
            if args.research_family
            else "stage0 selection benchmark summary"
        ),
    }
    if args.research_family:
        _append_stage1_once(
            experiment_id=_stage1_experiment_id(
                args.research_family, "BENCHMARK_SUMMARY", code_hash, data_hash
            ),
            **summary_row,
        )
    else:
        append_experiment(**summary_row)
    output_dir = PROJECT_ROOT / "logs" / "benchmark"
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / f"alphagen_cpu_{datetime.now(timezone.utc):%Y%m%dT%H%M%S.%fZ}.json"
    output.write_text(
        json.dumps(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "code_snapshot_sha256": code_hash,
                "data_snapshot_sha256": data_hash,
                "research_family": args.research_family or "",
                "summary": summary,
                "candidates": cache,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    print(json.dumps({"summary": summary, "report_path": str(output)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
