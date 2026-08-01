"""STAR50 PIT discovery evaluator for the isolated M1-1 price-volume family."""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch

from shaiwei.backtest.qlib_runtime import initialize_qlib
from shaiwei.benchmark.alphagen_cpu import _verify_vendor_checkout, stock_data_effective_start
from shaiwei.benchmark.fitness import neutralized_rank_ic
from shaiwei.config import PROJECT_ROOT, load
from shaiwei.ledger import sha256_file
from shaiwei.research.alphagen_expression import parse_safe_expression
from shaiwei.research.llm_factor import AttemptPlan, D1ControlError, D1Protocol, DiscoveryEvidence
from shaiwei.research.m1_star50_contract import Star50InputIdentity, verify_star50_inputs


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _write_once(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        if path.read_text(encoding="utf-8") != payload:
            raise D1ControlError("immutable M1-1 discovery artifact differs")
        return
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        temporary.write_text(payload, encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _finite(frame: pd.DataFrame, columns: tuple[str, ...]) -> pd.Series:
    mask = pd.Series(True, index=frame.index)
    for column in columns:
        mask &= np.isfinite(pd.to_numeric(frame[column], errors="coerce"))
    return mask


def _qlib_instrument(ts_code: str) -> str:
    code, exchange = ts_code.upper().split(".", 1)
    if exchange not in {"SH", "SZ"} or not code.isdigit() or len(code) != 6:
        raise D1ControlError("M1-1 member code is not an allowed A-share identity")
    return f"{exchange}{code}"


def load_star50_exposures(protocol: D1Protocol, project_root: Path) -> pd.DataFrame:
    data = protocol.document["data_contract"]
    member_path = project_root / str(data["member_day_dataset"])
    columns = ["trade_date", "ts_code", "industry", "total_mv", "has_market_bar"]
    frame = pd.read_parquet(member_path, columns=columns)
    frame["trade_date"] = pd.to_datetime(frame["trade_date"], errors="raise")
    start, end = map(pd.Timestamp, data["requested_discovery_signal_period"])
    frame = frame.loc[frame["trade_date"].between(start, end)].copy()
    frame["instrument"] = frame["ts_code"].astype(str).map(_qlib_instrument)
    frame["market_cap"] = pd.to_numeric(frame["total_mv"], errors="coerce")
    if frame.duplicated(["trade_date", "instrument"]).any():
        raise D1ControlError("M1-1 exposure input contains duplicate member days")
    return frame[["trade_date", "instrument", "industry", "market_cap"]]


@dataclass
class Star50DiscoveryEvaluator:
    protocol: D1Protocol
    artifact_root: Path
    project_root: Path = PROJECT_ROOT

    def __post_init__(self) -> None:
        self.input_identity: Star50InputIdentity = verify_star50_inputs(
            self.protocol, self.project_root
        )
        settings = load()
        contract = self.protocol.document["data_contract"]
        provider = self.project_root / str(contract["qlib_provider"])
        vendor = self.project_root / "vendor/alphagen"
        self.vendor_commit = _verify_vendor_checkout(vendor)
        if str(vendor) not in sys.path:
            sys.path.insert(0, str(vendor))
        from alphagen.data.expression import Ref
        from alphagen_qlib import stock_data as alphagen_stock_data
        from alphagen_qlib.stock_data import StockData
        from alphagen_generic.features import open_

        initialize_qlib(settings, provider_uri=provider)
        alphagen_stock_data._QLIB_INITIALIZED = True
        start = pd.Timestamp(contract["requested_discovery_signal_period"][0]).date()
        end = pd.Timestamp(contract["requested_discovery_signal_period"][1]).date()
        if stock_data_effective_start(start, 100) != start:
            raise D1ControlError("M1-1 discovery start moved after the result-before freeze")
        future = int(contract["horizon_trade_days"]) + 1
        self.data = StockData(
            str(contract["universe"]),
            start.isoformat(),
            end.isoformat(),
            max_backtrack_days=100,
            max_future_days=future,
            device=torch.device("cpu"),
        )
        target = Ref(open_, -future) / Ref(open_, -1) - 1
        label = self.data.make_dataframe(target.evaluate(self.data), columns=["label"]).reset_index()
        label.columns = ["trade_date", "instrument", "label"]
        label["trade_date"] = pd.to_datetime(label["trade_date"], errors="raise")
        if label["trade_date"].max() > pd.Timestamp(end):
            raise D1ControlError("M1-1 label index entered the sealed validation period")
        exposures = load_star50_exposures(self.protocol, self.project_root)
        eligible = label.merge(exposures, on=["trade_date", "instrument"], how="inner")
        valid = _finite(eligible, ("label", "market_cap"))
        valid &= eligible["market_cap"].gt(0) & eligible["industry"].notna()
        self.label = label
        self.exposures = exposures
        self.eligible = eligible.loc[valid].copy()
        self.minimum_cross_section = int(contract["minimum_cross_section"])
        self.minimum_daily_ic = int(contract["minimum_daily_ic_observations"])
        self.minimum_coverage = float(contract["minimum_candidate_coverage"])
        self.data_snapshot_sha256 = self.input_identity.snapshot_sha256

    def __call__(self, plan: AttemptPlan, expression: str) -> DiscoveryEvidence:
        evaluated = parse_safe_expression(expression).evaluate(self.data)
        factor = self.data.make_dataframe(evaluated, columns=["factor"]).reset_index()
        factor.columns = ["trade_date", "instrument", "factor"]
        factor["trade_date"] = pd.to_datetime(factor["trade_date"], errors="raise")
        observations = factor.merge(self.label, on=["trade_date", "instrument"], how="inner").merge(
            self.exposures,
            on=["trade_date", "instrument"],
            how="inner",
        )
        covered = observations.loc[
            _finite(observations, ("factor", "label", "market_cap"))
            & observations["market_cap"].gt(0)
            & observations["industry"].notna()
        ].copy()
        eligible_rows = len(self.eligible)
        covered_rows = len(covered)
        coverage = covered_rows / eligible_rows if eligible_rows else None
        rank_ic, daily_ic = neutralized_rank_ic(observations, self.minimum_cross_section)
        finite_ic = float(rank_ic) if math.isfinite(float(rank_ic)) else None
        coverage_pass = coverage is not None and coverage >= self.minimum_coverage
        daily_ic_pass = len(daily_ic) >= self.minimum_daily_ic and finite_ic is not None
        passed = coverage_pass and daily_ic_pass
        failures = []
        if not coverage_pass:
            failures.append("coverage_below_minimum")
        if not daily_ic_pass:
            failures.append(f"insufficient_daily_ic:{len(daily_ic)}")
        error = ";".join(failures)
        artifact = {
            "schema_version": "m1-star50-discovery-evidence-v1",
            "attempt_id": plan.attempt_id,
            "global_ordinal": plan.global_ordinal,
            "topic": plan.topic,
            "expression": expression,
            "data_snapshot_sha256": self.data_snapshot_sha256,
            "eligible_rows": eligible_rows,
            "covered_rows": covered_rows,
            "coverage": coverage,
            "minimum_coverage": self.minimum_coverage,
            "minimum_cross_section": self.minimum_cross_section,
            "minimum_daily_ic_observations": self.minimum_daily_ic,
            "daily_ic_count": len(daily_ic),
            "rank_ic": finite_ic if passed else None,
            "error": error,
            "daily_ic": [
                {"trade_date": pd.Timestamp(date).date().isoformat(), "rank_ic": float(value)}
                for date, value in daily_ic.items()
            ],
            "sealed_validation_read": False,
            "stress_periods_read": False,
            "g1_run": False,
            "model_or_portfolio_run": False,
        }
        relative = f"discovery/{plan.attempt_id}.json"
        path = self.artifact_root / relative
        _write_once(path, json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
        return DiscoveryEvidence(
            status="PASS" if passed else "FAIL",
            eligible_rows=eligible_rows,
            covered_rows=covered_rows,
            coverage=coverage,
            daily_ic_count=len(daily_ic),
            rank_ic=finite_ic if passed else None,
            error=error,
            artifact_path=relative,
            artifact_sha256=sha256_file(path),
        )


def discovery_input_summary(protocol: D1Protocol, project_root: Path = PROJECT_ROOT) -> dict[str, Any]:
    identity = verify_star50_inputs(protocol, project_root)
    return {
        "schema_version": "m1-star50-discovery-input-summary-v1",
        "input_gate_pass": True,
        "data_snapshot_sha256": identity.snapshot_sha256,
        "qlib_artifact_sha256": identity.qlib_artifact_sha256,
        "member_day_sha256": identity.member_day_sha256,
        "discovery_rows": identity.discovery_rows,
        "discovery_trade_days": identity.discovery_trade_days,
        "factor_results_inspected": False,
        "provider_calls": 0,
        "production_authorization": "none",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--protocol",
        type=Path,
        default=PROJECT_ROOT / "config/m1_star50_factor_research_v1.yaml",
    )
    args = parser.parse_args(argv)
    try:
        protocol = D1Protocol.load(args.protocol)
        report = discovery_input_summary(protocol)
    except (D1ControlError, OSError, RuntimeError, TypeError, ValueError) as error:
        print(_canonical_json({"status": "FAIL", "error_class": type(error).__name__}))
        return 2
    print(_canonical_json(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
