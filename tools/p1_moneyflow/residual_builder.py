"""Build core and OOS-incremental residual panels for the six frozen candidates."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import duckdb
import pandas as pd

from shaiwei.config import PROJECT_ROOT, load
from shaiwei.ledger import INGEST, ingest_snapshot_sha256, resolve_artifact_path, sha256_file
from shaiwei.provenance import code_snapshot_sha256, git_head
from shaiwei.research.g1_pipeline import build_baseline_windows, load_research_data
from tools.p1_moneyflow.contract import tool_snapshot_sha256, write_project_json
from tools.p1_moneyflow.feature_builder import (
    FeatureBuilderError,
    _read_json,
    write_content_addressed_parquet,
)
from tools.p1_moneyflow.features import (
    FORMAL_CANDIDATES,
    feature_policy_sha256,
    residualize_moneyflow_candidates,
)
from tools.p1_moneyflow.full_audit import _latest_entries


class ResidualBuilderError(RuntimeError):
    pass


def qlib_to_ts_code(instrument: str) -> str:
    value = str(instrument)
    if len(value) == 8 and value[:2] in {"SH", "SZ"} and value[2:].isdigit():
        return f"{value[2:]}.{value[:2]}"
    raise ValueError(f"unsupported qlib instrument: {instrument!r}")


def _paths(entries: pd.DataFrame) -> list[str]:
    paths = []
    for value in entries["parquet_path"]:
        path = resolve_artifact_path(value)
        if not path.is_file():
            raise ResidualBuilderError(f"committed batch file is missing: {path}")
        paths.append(str(path))
    return paths


def _liquidity_exposures(
    research_exposures: pd.DataFrame,
    ledger: pd.DataFrame,
) -> pd.DataFrame:
    base = research_exposures.copy()
    base["trade_date"] = pd.to_datetime(base["trade_date"]).dt.strftime("%Y%m%d")
    base["ts_code"] = base["instrument"].map(qlib_to_ts_code)
    base = base.loc[:, ["ts_code", "trade_date", "industry", "market_cap"]]
    connection = duckdb.connect(":memory:")
    try:
        connection.register("research_exposures", base)
        connection.read_parquet(
            _paths(_latest_entries(ledger, "tushare.daily")),
            union_by_name=True,
            hive_partitioning=False,
        ).create_view("daily")
        connection.read_parquet(
            _paths(_latest_entries(ledger, "tushare.daily_basic")),
            union_by_name=True,
            hive_partitioning=False,
        ).create_view("daily_basic")
        result = connection.execute(
            """
            SELECT e.ts_code, e.trade_date, e.industry, e.market_cap,
                   d.amount, b.turnover_rate
            FROM research_exposures e
            LEFT JOIN daily d
              ON e.ts_code = d.ts_code AND e.trade_date = CAST(d.trade_date AS VARCHAR)
            LEFT JOIN daily_basic b
              ON e.ts_code = b.ts_code AND e.trade_date = CAST(b.trade_date AS VARCHAR)
            """
        ).df()
    finally:
        connection.close()
    if result.duplicated(["ts_code", "trade_date"]).any():
        raise ResidualBuilderError("liquidity exposure join produced duplicate keys")
    return result


def _universe_features(feature_path: Path, exposures: pd.DataFrame) -> pd.DataFrame:
    keys = exposures.loc[:, ["ts_code", "trade_date"]]
    connection = duckdb.connect(":memory:")
    try:
        connection.register("universe_keys", keys)
        return connection.execute(
            """
            SELECT f.*
            FROM read_parquet(?) f
            INNER JOIN universe_keys k USING (ts_code, trade_date)
            """,
            [str(feature_path)],
        ).df()
    finally:
        connection.close()


def formalize_core_with_oos(
    core: pd.DataFrame,
    oos_incremental: pd.DataFrame,
    *,
    oos_start: str,
    oos_end: str,
) -> pd.DataFrame:
    outside = core.loc[~core["trade_date"].astype(str).between(oos_start, oos_end)].copy()
    formal = pd.concat([outside, oos_incremental], ignore_index=True)
    if formal.duplicated(["ts_code", "trade_date"]).any():
        raise ResidualBuilderError("formal residual panel contains duplicate keys")
    return formal.sort_values(["trade_date", "ts_code"], kind="stable").reset_index(drop=True)


def _prediction_frame(window_name: str, predictions: pd.Series) -> pd.DataFrame:
    frame = predictions.rename("baseline_score").reset_index()
    if len(frame.columns) != 3:
        raise ResidualBuilderError("baseline predictions must have datetime/instrument index")
    frame.columns = ["trade_date", "instrument", "baseline_score"]
    frame["trade_date"] = pd.to_datetime(frame["trade_date"]).dt.strftime("%Y%m%d")
    frame["ts_code"] = frame["instrument"].map(qlib_to_ts_code)
    frame.insert(0, "window", window_name)
    return frame.loc[:, ["window", "ts_code", "trade_date", "instrument", "baseline_score"]]


def _residual_data_sha256(
    *,
    ingest_snapshot: str,
    feature_artifact_sha256: str,
    core_artifact_sha256: str,
    formal_artifact_sha256: str,
    prediction_artifact_sha256: str,
) -> str:
    payload = {
        "ingest_snapshot_sha256": ingest_snapshot,
        "feature_artifact_sha256": feature_artifact_sha256,
        "core_artifact_sha256": core_artifact_sha256,
        "formal_artifact_sha256": formal_artifact_sha256,
        "prediction_artifact_sha256": prediction_artifact_sha256,
        "feature_policy_sha256": feature_policy_sha256(),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feature-report", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    started = time.perf_counter()
    feature_report_path = (
        args.feature_report if args.feature_report.is_absolute() else PROJECT_ROOT / args.feature_report
    )
    try:
        feature_report = _read_json(feature_report_path)
    except FeatureBuilderError as error:
        raise ResidualBuilderError(str(error)) from error
    if feature_report.get("schema_version") != "p1-moneyflow-feature-build-v1":
        raise ResidualBuilderError("input is not p1-moneyflow-feature-build-v1")
    if feature_report.get("status") != "PASS":
        raise ResidualBuilderError("feature build report is not PASS")
    if feature_report.get("feature_policy_sha256") != feature_policy_sha256():
        raise ResidualBuilderError("feature report policy differs from current frozen policy")
    current_ingest = ingest_snapshot_sha256()
    if feature_report.get("ingest_snapshot_sha256") != current_ingest:
        raise ResidualBuilderError("ingest snapshot changed after feature construction")
    artifact = feature_report.get("artifact")
    if not isinstance(artifact, dict):
        raise ResidualBuilderError("feature report lacks artifact binding")
    feature_path = PROJECT_ROOT / str(artifact["path"])
    feature_hash = str(artifact["sha256"])
    if not feature_path.is_file() or sha256_file(feature_path) != feature_hash:
        raise ResidualBuilderError("feature artifact is missing or hash-mismatched")

    settings = load()
    research = load_research_data(settings)
    baselines = build_baseline_windows(settings, research.labels)
    ledger = pd.read_csv(INGEST, dtype=str, keep_default_na=False)
    exposures = _liquidity_exposures(research.exposures, ledger)
    features = _universe_features(feature_path, exposures)
    core = residualize_moneyflow_candidates(
        features,
        exposures,
        min_cross_section=settings.alphagen_benchmark.min_cross_section,
        include_baseline_score=False,
    )

    prediction_frames = []
    incremental_frames = []
    baseline_summary = []
    for baseline in baselines:
        prediction = _prediction_frame(baseline.window.name, baseline.predictions)
        prediction_frames.append(prediction)
        start = baseline.window.test_start.strftime("%Y%m%d")
        end = baseline.window.test_end.strftime("%Y%m%d")
        window_features = features.loc[features["trade_date"].astype(str).between(start, end)].copy()
        window_exposures = exposures.loc[
            exposures["trade_date"].astype(str).between(start, end)
        ].merge(
            prediction.loc[:, ["ts_code", "trade_date", "baseline_score"]],
            on=["ts_code", "trade_date"],
            how="inner",
            validate="one_to_one",
        )
        incremental_frames.append(
            residualize_moneyflow_candidates(
                window_features,
                window_exposures,
                min_cross_section=settings.alphagen_benchmark.min_cross_section,
                include_baseline_score=True,
            )
        )
        baseline_summary.append(
            {
                "window": baseline.window.name,
                "prediction_rows": int(len(baseline.predictions)),
                "prediction_trade_dates": int(
                    baseline.predictions.index.get_level_values(0).nunique()
                ),
                "baseline_turnover": baseline.backtest.turnover,
                "baseline_cumulative_excess": baseline.backtest.cumulative_excess,
                "baseline_max_drawdown": baseline.backtest.max_drawdown,
            }
        )
    predictions = pd.concat(prediction_frames, ignore_index=True)
    incremental = pd.concat(incremental_frames, ignore_index=True)
    oos_start = min(window.test_start for window in settings.evaluation.g0_windows).strftime("%Y%m%d")
    oos_end = max(window.test_end for window in settings.evaluation.g0_windows).strftime("%Y%m%d")
    formal = formalize_core_with_oos(core, incremental, oos_start=oos_start, oos_end=oos_end)

    artifact_root = PROJECT_ROOT / "data" / "research" / "moneyflow" / "residuals"
    core_path, core_hash, core_reused = write_content_addressed_parquet(
        core,
        artifact_root,
        stem="p1-moneyflow-core-residuals-v1",
    )
    formal_path, formal_hash, formal_reused = write_content_addressed_parquet(
        formal,
        artifact_root,
        stem="p1-moneyflow-formal-residuals-v1",
    )
    prediction_path, prediction_hash, prediction_reused = write_content_addressed_parquet(
        predictions,
        artifact_root,
        stem="p1-moneyflow-alpha158-predictions-v1",
    )
    data_hash = _residual_data_sha256(
        ingest_snapshot=current_ingest,
        feature_artifact_sha256=feature_hash,
        core_artifact_sha256=core_hash,
        formal_artifact_sha256=formal_hash,
        prediction_artifact_sha256=prediction_hash,
    )
    report = {
        "schema_version": "p1-moneyflow-residual-build-v1",
        "generated_at": pd.Timestamp.utcnow().isoformat(),
        "elapsed_seconds": time.perf_counter() - started,
        "git_head": git_head(),
        "production_code_snapshot_sha256": code_snapshot_sha256(),
        "p1_tool_snapshot_sha256": tool_snapshot_sha256(),
        "ingest_snapshot_sha256": current_ingest,
        "feature_policy_sha256": feature_policy_sha256(),
        "feature_report_path": str(feature_report_path.relative_to(PROJECT_ROOT)),
        "feature_report_sha256": sha256_file(feature_report_path),
        "feature_artifact_sha256": feature_hash,
        "residual_data_snapshot_sha256": data_hash,
        "exposure_policy": {
            "discovery_and_core": [
                "sw_l1_industry_pit",
                "log_total_mv",
                "log_daily_amount",
                "turnover_rate",
            ],
            "w1_w6_additional": "alpha158_baseline_score",
        },
        "artifacts": {
            "core": {
                "path": str(core_path.relative_to(PROJECT_ROOT)),
                "sha256": core_hash,
                "row_count": int(len(core)),
                "reused": core_reused,
            },
            "formal": {
                "path": str(formal_path.relative_to(PROJECT_ROOT)),
                "sha256": formal_hash,
                "row_count": int(len(formal)),
                "reused": formal_reused,
            },
            "alpha158_predictions": {
                "path": str(prediction_path.relative_to(PROJECT_ROOT)),
                "sha256": prediction_hash,
                "row_count": int(len(predictions)),
                "reused": prediction_reused,
            },
        },
        "baseline_windows": baseline_summary,
        "formal_candidates": list(FORMAL_CANDIDATES),
        "status": "PASS",
        "authorization": "run_isolated_same_budget_comparison",
        "production_authorization": "none",
    }
    report_path = args.report if args.report.is_absolute() else PROJECT_ROOT / args.report
    write_project_json(report_path, report)
    print(
        json.dumps(
            {
                "status": "PASS",
                "residual_data_snapshot_sha256": data_hash,
                "core_rows": len(core),
                "formal_rows": len(formal),
                "prediction_rows": len(predictions),
                "elapsed_seconds": report["elapsed_seconds"],
                "report": str(report_path.relative_to(PROJECT_ROOT)),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
