"""上游 AlphaGen 表达式/GP + 项目侧中性化 RankIC 的单轮 CPU benchmark。"""

import hashlib
import json
import os
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import psutil
import torch

from shaiwei.benchmark.fitness import benchmark_decision, neutralized_rank_ic
from shaiwei.config import PROJECT_ROOT, load
from shaiwei.ingest.catalog import load_latest_api
from shaiwei.ledger import append_experiment, ingest_snapshot_sha256
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
            processes = [process, *process.children(recursive=True)]
            rss = sum(child.memory_info().rss for child in processes if child.is_running())
            self.peak_bytes = max(self.peak_bytes, rss)

    def __enter__(self) -> "PeakMemorySampler":
        self._thread.start()
        return self

    def __exit__(self, *_: object) -> None:
        self._stop.set()
        self._thread.join()


def _code_snapshot_sha256() -> str:
    head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    diff = subprocess.run(["git", "diff", "--binary", "HEAD"], capture_output=True, check=True).stdout
    return hashlib.sha256(head.encode() + b"\0" + diff).hexdigest()


def _load_exposures() -> pd.DataFrame:
    daily_basic = load_latest_api("tushare.daily_basic")
    stock_basic = load_latest_api("tushare.stock_basic")
    industry = stock_basic.sort_values("list_status").drop_duplicates("ts_code", keep="last")
    industry = industry.set_index("ts_code")["industry"]
    exposures = daily_basic.loc[:, ["ts_code", "trade_date", "total_mv"]].copy()
    exposures["instrument"] = exposures["ts_code"].map(qlib_code)
    exposures["trade_date"] = pd.to_datetime(exposures["trade_date"], format="%Y%m%d")
    exposures["industry"] = exposures["ts_code"].map(industry)
    exposures["market_cap"] = pd.to_numeric(exposures["total_mv"], errors="coerce")
    return exposures.loc[:, ["trade_date", "instrument", "industry", "market_cap"]]


def main() -> int:
    settings = load()
    config = settings.alphagen_benchmark
    vendor = PROJECT_ROOT / "vendor" / "alphagen"
    if not (vendor / "gp.py").is_file():
        raise SystemExit("vendor/alphagen missing; clone the commit in config/externals.lock.yaml")
    sys.path.insert(0, str(vendor))

    from alphagen.data.expression import Constant, OutOfDataRangeError, Ref
    from alphagen.utils.random import reseed_everything
    from alphagen_generic.features import close, high, low, open_, volume, vwap
    from alphagen_generic.operators import funcs as generic_funcs
    from alphagen_qlib.stock_data import StockData, initialize_qlib
    from gplearn.fitness import make_fitness
    from gplearn.functions import make_function
    from gplearn.genetic import SymbolicRegressor

    reseed_everything(config.seed)
    device = torch.device("cpu")
    initialize_qlib(str(settings.runtime.data_root / "qlib_bin"))
    data = StockData(
        config.instrument,
        config.train_start.isoformat(),
        config.train_end.isoformat(),
        max_future_days=settings.backtest.rebalance_days + 1,
        device=device,
    )
    target = Ref(open_, -(settings.backtest.rebalance_days + 1)) / Ref(open_, -1) - 1
    label = data.make_dataframe(target.evaluate(data), columns=["label"]).reset_index()
    label.columns = ["trade_date", "instrument", "label"]
    exposures = _load_exposures()
    cache: dict[str, dict[str, object]] = {}
    namespace = {
        **vars(sys.modules["alphagen.data.expression"]),
        "open_": open_, "close": close, "high": high, "low": low, "volume": volume, "vwap": vwap,
        "Constant": Constant,
    }

    def metric(_dummy: np.ndarray, generated: np.ndarray, _weight: np.ndarray) -> float:
        expression_text = str(generated[0])
        if expression_text in cache:
            return float(cache[expression_text]["rank_ic"])
        if expression_text.count("(") + expression_text.count(")") > config.max_expression_tokens:
            cache[expression_text] = {"rank_ic": -1.0, "error": "expression_too_long"}
            return -1.0
        try:
            expression = eval(expression_text, {"__builtins__": {}}, namespace)
            factor = data.make_dataframe(expression.evaluate(data), columns=["factor"]).reset_index()
            factor.columns = ["trade_date", "instrument", "factor"]
            observations = factor.merge(label, on=["trade_date", "instrument"]).merge(
                exposures, on=["trade_date", "instrument"]
            )
            rank_ic, daily_ic = neutralized_rank_ic(observations, config.min_cross_section)
            score = rank_ic if np.isfinite(rank_ic) else -1.0
            cache[expression_text] = {
                "rank_ic": score,
                "daily_ic_count": len(daily_ic),
                "error": "" if np.isfinite(rank_ic) else "rank_ic_nan",
            }
        except (OutOfDataRangeError, TypeError, ValueError, RuntimeError) as error:
            cache[expression_text] = {"rank_ic": -1.0, "error": f"{type(error).__name__}: {error}"}
        return float(cache[expression_text]["rank_ic"])

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
    started = time.perf_counter()
    with PeakMemorySampler() as memory:
        estimator.fit(np.array([terminals]), np.array([[1]]))
    elapsed = time.perf_counter() - started
    values = np.array([float(result["rank_ic"]) for result in cache.values()], dtype=float)
    best_rank_ic = float(values.max()) if len(values) else -1.0
    summary = {
        "elapsed_seconds": elapsed,
        "peak_memory_bytes": memory.peak_bytes,
        "candidate_count": len(cache),
        "failed_candidate_count": sum(bool(result["error"]) for result in cache.values()),
        "rank_ic": {
            "min": float(values.min()), "median": float(np.median(values)), "max": best_rank_ic,
        },
        "decision": benchmark_decision(
            elapsed,
            best_rank_ic,
            rank_ic_threshold=config.rank_ic_threshold,
            scale_hours=config.scale_time_hours,
            abort_hours=config.abort_time_hours,
        ),
        "device": str(device),
    }
    common = {
        "candidate_source": "AlphaGen-GP",
        "model_or_engine": "AlphaGen upstream GP + shaiwei neutralized RankIC",
        "engine_version": "259687e8f316994426416c530a94842a2fe6405e",
        "seed": config.seed,
        "prompt_hash": "",
        "code_sha256": _code_snapshot_sha256(),
        "data_snapshot_sha256": ingest_snapshot_sha256(),
        "params_json": config.model_dump(mode="json"),
        "train_period": f"{config.train_start}~{config.train_end}",
        "valid_period": "single-round throughput benchmark",
        "admitted": False,
    }
    for expression_text, result in cache.items():
        append_experiment(
            **common,
            feature_or_formula=expression_text,
            result_json=result,
            reject_reason=str(result["error"]) or "stage0 benchmark; not factor admission",
        )
    append_experiment(
        **common,
        feature_or_formula="BENCHMARK_SUMMARY",
        result_json=summary,
        reject_reason="stage0 selection benchmark summary",
    )
    output_dir = PROJECT_ROOT / "logs" / "benchmark"
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / f"alphagen_cpu_{datetime.now(timezone.utc):%Y%m%dT%H%M%S.%fZ}.json"
    output.write_text(json.dumps({"summary": summary, "candidates": cache}, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"summary": summary, "report_path": str(output)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
