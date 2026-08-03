"""Build label-free daily core and Alpha158-incremental F1-1 residual panels."""

from __future__ import annotations

import math
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

from shaiwei.benchmark.fitness import industry_pit_exposure
from shaiwei.config import PROJECT_ROOT
from shaiwei.ingest.catalog import load_latest_api
from shaiwei.provenance import code_snapshot_sha256, git_head
from shaiwei.research.fundamental_effect.contract import (
    FundamentalEffectError,
    FundamentalEffectProtocol,
)
from shaiwei.research.fundamental_effect.io import (
    sha256_json,
    write_content_addressed_parquet,
    write_json_once,
)
from shaiwei.research.fundamental_effect.runtime import EffectRuntime
from shaiwei.research.fundamental_pit_gate import _open_days


SERIALIZATION_DECIMALS = 12


def qlib_to_ts_code(value: str) -> str:
    instrument = str(value)
    if len(instrument) == 8 and instrument[:2] in {"SH", "SZ"} and instrument[2:].isdigit():
        return f"{instrument[2:]}.{instrument[:2]}"
    raise FundamentalEffectError(f"unsupported qlib instrument: {value!r}")


def ts_code_to_qlib(value: str) -> str:
    code = str(value)
    if len(code) == 9 and code[:6].isdigit() and code[6:] in {".SH", ".SZ"}:
        return f"{code[7:]}{code[:6]}"
    if code.endswith(".BJ"):
        raise FundamentalEffectError(".BJ is forbidden in F1-1")
    raise FundamentalEffectError(f"unsupported A-share code: {value!r}")


def expand_monthly_features(
    features: pd.DataFrame,
    open_days: list[str],
    *,
    start_date: str,
    end_date: str,
    candidate_names: tuple[str, ...],
) -> pd.DataFrame:
    required = {"formation_date", "ts_code", *candidate_names}
    if missing := required - set(features.columns):
        raise FundamentalEffectError(f"F1-1 feature panel lacks {sorted(missing)}")
    source = features.loc[:, ["formation_date", "ts_code", *candidate_names]].copy()
    source["formation_date"] = source["formation_date"].astype(str).str.replace("-", "", regex=False)
    source["ts_code"] = source["ts_code"].astype(str)
    if source["ts_code"].str.endswith(".BJ").any():
        raise FundamentalEffectError(".BJ returned in the F1-1 feature panel")
    if source.duplicated(["formation_date", "ts_code"]).any():
        raise FundamentalEffectError("F1-1 feature panel contains duplicate keys")
    formation_dates = sorted(source["formation_date"].unique())
    next_dates = dict(zip(formation_dates, [*formation_dates[1:], "99991231"], strict=True))
    source["next_formation_date"] = source["formation_date"].map(next_dates)
    calendar = pd.DataFrame(
        {"trade_date": [day for day in open_days if start_date <= day <= end_date]}
    )
    if calendar.empty:
        raise FundamentalEffectError("F1-1 daily expansion calendar is empty")
    connection = duckdb.connect(":memory:")
    try:
        connection.register("formations", source)
        connection.register("calendar", calendar)
        columns = ", ".join(f'f."{name}"' for name in candidate_names)
        expanded = connection.execute(
            f"""
            SELECT c.trade_date, f.formation_date AS source_formation_date,
                   f.ts_code, {columns}
            FROM calendar c
            JOIN formations f
              ON c.trade_date >= f.formation_date
             AND c.trade_date < f.next_formation_date
            ORDER BY c.trade_date, f.ts_code
            """
        ).df()
    finally:
        connection.close()
    if expanded.empty or expanded.duplicated(["trade_date", "ts_code"]).any():
        raise FundamentalEffectError("F1-1 daily expansion is empty or duplicated")
    if expanded["source_formation_date"].gt(expanded["trade_date"]).any():
        raise FundamentalEffectError("F1-1 daily expansion used a future formation")
    return expanded


def attach_pit_exposures(
    expanded: pd.DataFrame,
    daily_basic: pd.DataFrame,
    membership: pd.DataFrame,
) -> pd.DataFrame:
    required_basic = {"ts_code", "trade_date", "total_mv"}
    if missing := required_basic - set(daily_basic.columns):
        raise FundamentalEffectError(f"daily_basic lacks {sorted(missing)}")
    keys = expanded.loc[:, ["ts_code", "trade_date"]]
    basic = daily_basic.loc[:, ["ts_code", "trade_date", "total_mv"]].copy()
    basic["ts_code"] = basic["ts_code"].astype(str)
    basic["trade_date"] = basic["trade_date"].astype(str)
    basic = basic.loc[
        basic["ts_code"].isin(keys["ts_code"].unique())
        & basic["trade_date"].between(keys["trade_date"].min(), keys["trade_date"].max())
    ].copy()
    if basic.duplicated(["ts_code", "trade_date"]).any():
        raise FundamentalEffectError("daily_basic contains duplicate F1-1 exposure keys")
    industry = industry_pit_exposure(keys, membership)
    if industry["industry"].astype("string").str.contains("|", regex=False, na=False).any():
        raise FundamentalEffectError("F1-1 PIT industry exposure is ambiguous")
    result = expanded.merge(
        basic,
        on=["ts_code", "trade_date"],
        how="left",
        validate="one_to_one",
    ).merge(
        industry,
        on=["ts_code", "trade_date"],
        how="left",
        validate="one_to_one",
    )
    result["market_cap"] = pd.to_numeric(result["total_mv"], errors="coerce")
    return result.drop(columns=["total_mv"])


def _winsorized_zscore(values: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce").astype(float)
    lower = numeric.quantile(0.01)
    upper = numeric.quantile(0.99)
    clipped = numeric.clip(lower=lower, upper=upper)
    standard_deviation = clipped.std(ddof=0)
    if not math.isfinite(float(standard_deviation)) or standard_deviation <= 0:
        return pd.Series(np.nan, index=values.index, dtype=float)
    return (clipped - clipped.mean()) / standard_deviation


def residualize_candidates(
    frame: pd.DataFrame,
    *,
    candidate_names: tuple[str, ...],
    include_baseline_score: bool,
    minimum_cross_section: int = 30,
) -> pd.DataFrame:
    required = {
        "ts_code",
        "trade_date",
        "source_formation_date",
        "industry",
        "market_cap",
        *candidate_names,
        *(("baseline_score",) if include_baseline_score else ()),
    }
    if missing := required - set(frame.columns):
        raise FundamentalEffectError(f"F1-1 residual input lacks {sorted(missing)}")
    ordered = frame.sort_values(["trade_date", "ts_code"], kind="stable").reset_index(drop=True)
    outputs: list[pd.DataFrame] = []
    for _, group in ordered.groupby("trade_date", sort=True):
        base = group.loc[
            group["industry"].notna()
            & pd.to_numeric(group["market_cap"], errors="coerce").gt(0)
        ].copy()
        if include_baseline_score:
            base = base.loc[pd.to_numeric(base["baseline_score"], errors="coerce").notna()].copy()
        if len(base) < minimum_cross_section:
            continue
        log_cap = np.log(pd.to_numeric(base["market_cap"], errors="raise"))
        continuous = {"log_market_cap": _winsorized_zscore(log_cap)}
        if include_baseline_score:
            continuous["baseline_score"] = _winsorized_zscore(base["baseline_score"])
        industries = pd.get_dummies(
            base["industry"].astype(str),
            prefix="industry",
            drop_first=True,
            dtype=float,
        )
        design = pd.concat(
            [
                pd.Series(1.0, index=base.index, name="intercept"),
                pd.DataFrame(continuous, index=base.index),
                industries,
            ],
            axis=1,
        )
        design_values = design.to_numpy(dtype=float)
        day = base.loc[:, ["ts_code", "trade_date", "source_formation_date"]].copy()
        any_candidate = False
        for candidate in candidate_names:
            raw = pd.to_numeric(base[candidate], errors="coerce")
            valid = raw.notna()
            residual = pd.Series(np.nan, index=base.index, dtype=float)
            if int(valid.sum()) >= minimum_cross_section and raw.loc[valid].nunique() >= 2:
                candidate_matrix = design_values[valid.to_numpy()]
                values = _winsorized_zscore(raw.loc[valid]).to_numpy(dtype=float)
                finite = np.isfinite(values)
                if int(finite.sum()) >= minimum_cross_section:
                    candidate_matrix = candidate_matrix[finite]
                    values = values[finite]
                    with threadpool_limits(limits=1, user_api="blas"):
                        coefficients, *_ = np.linalg.lstsq(candidate_matrix, values, rcond=None)
                        fitted = candidate_matrix @ coefficients
                    valid_index = raw.loc[valid].index[finite]
                    residual.loc[valid_index] = np.round(
                        values - fitted,
                        decimals=SERIALIZATION_DECIMALS,
                    )
                    any_candidate = True
            day[candidate] = residual
        if any_candidate:
            outputs.append(day)
    if not outputs:
        raise FundamentalEffectError("no F1-1 cross-section passed residualization")
    result = pd.concat(outputs, ignore_index=True).sort_values(
        ["trade_date", "ts_code"], kind="stable"
    )
    if result.duplicated(["trade_date", "ts_code"]).any():
        raise FundamentalEffectError("F1-1 residual output contains duplicate keys")
    return result.reset_index(drop=True)


def formalize_panel(
    core: pd.DataFrame,
    incremental: pd.DataFrame,
    *,
    oos_start: str,
    oos_end: str,
) -> pd.DataFrame:
    outside = core.loc[~core["trade_date"].astype(str).between(oos_start, oos_end)].copy()
    formal = pd.concat([outside, incremental], ignore_index=True).sort_values(
        ["trade_date", "ts_code"], kind="stable"
    )
    if formal.duplicated(["trade_date", "ts_code"]).any():
        raise FundamentalEffectError("F1-1 formal panel contains duplicate keys")
    return formal.reset_index(drop=True)


def _coverage(frame: pd.DataFrame, candidates: tuple[str, ...]) -> dict[str, float]:
    return {name: float(frame[name].notna().mean()) for name in candidates}


def build_residual_panels(
    protocol: FundamentalEffectProtocol,
    input_identity: dict[str, object],
    runtime: EffectRuntime,
    *,
    project_root: Path = PROJECT_ROOT,
) -> dict[str, object]:
    candidates = tuple(spec.name for spec in protocol.candidates)
    bindings = protocol.document["input_bindings"]
    feature_path = protocol.project_path(
        str(bindings["fundamental_feature_panel"]["path"]), project_root=project_root
    )
    prediction_path = protocol.project_path(
        str(bindings["alpha158_predictions"]["path"]), project_root=project_root
    )
    features = pd.read_parquet(feature_path)
    frames = {source: load_latest_api(source) for source in protocol.required_apis}
    open_days = _open_days(frames["tushare.trade_cal"], "19000101", "20260731")
    expanded = expand_monthly_features(
        features,
        open_days,
        start_date="20160701",
        end_date="20260630",
        candidate_names=candidates,
    )
    exposed = attach_pit_exposures(
        expanded,
        frames["tushare.daily_basic"],
        frames["tushare.index_member_all"],
    )
    core = residualize_candidates(
        exposed,
        candidate_names=candidates,
        include_baseline_score=False,
    )
    predictions = pd.read_parquet(prediction_path)
    required_prediction = {"window", "ts_code", "trade_date", "instrument", "baseline_score"}
    if missing := required_prediction - set(predictions.columns):
        raise FundamentalEffectError(f"Alpha158 prediction cache lacks {sorted(missing)}")
    predictions["trade_date"] = predictions["trade_date"].astype(str)
    if predictions["ts_code"].astype(str).str.endswith(".BJ").any():
        raise FundamentalEffectError(".BJ returned in Alpha158 predictions")
    if predictions.duplicated(["trade_date", "ts_code"]).any():
        raise FundamentalEffectError("Alpha158 predictions contain duplicate daily keys")
    expected_instrument = predictions["ts_code"].map(ts_code_to_qlib)
    if not expected_instrument.eq(predictions["instrument"].astype(str)).all():
        raise FundamentalEffectError("Alpha158 prediction code mapping differs")
    incremental_input = exposed.merge(
        predictions.loc[:, ["trade_date", "ts_code", "baseline_score"]],
        on=["trade_date", "ts_code"],
        how="inner",
        validate="one_to_one",
    )
    incremental = residualize_candidates(
        incremental_input,
        candidate_names=candidates,
        include_baseline_score=True,
    )
    formal = formalize_panel(core, incremental, oos_start="20190101", oos_end="20241231")
    output_root = protocol.project_path(
        str(protocol.document["outputs"]["ignored_root"]), project_root=project_root
    )
    core_path, core_sha, core_reused = write_content_addressed_parquet(
        core,
        output_root,
        stem=f"{runtime.artifact_prefix}-core-residuals-v1",
    )
    formal_path, formal_sha, formal_reused = write_content_addressed_parquet(
        formal,
        output_root,
        stem=f"{runtime.artifact_prefix}-formal-residuals-v1",
    )
    data_snapshot = sha256_json(
        {
            "input_snapshot_sha256": input_identity["input_snapshot_sha256"],
            "policy_sha256": protocol.policy_sha256,
            "core_sha256": core_sha,
            "formal_sha256": formal_sha,
        }
    )
    diagnostics = {
        "open_day_count": int(expanded["trade_date"].nunique()),
        "first_trade_date": str(expanded["trade_date"].min()),
        "last_trade_date": str(expanded["trade_date"].max()),
        "expanded_rows": int(len(expanded)),
        "security_count": int(expanded["ts_code"].nunique()),
        "minimum_daily_members": int(expanded.groupby("trade_date")["ts_code"].nunique().min()),
        "maximum_daily_members": int(expanded.groupby("trade_date")["ts_code"].nunique().max()),
        "future_formation_rows": int(
            expanded["source_formation_date"].gt(expanded["trade_date"]).sum()
        ),
        "bse_rows": int(expanded["ts_code"].str.endswith(".BJ").sum()),
        "industry_coverage": float(exposed["industry"].notna().mean()),
        "market_cap_coverage": float(exposed["market_cap"].notna().mean()),
        "raw_candidate_coverage": _coverage(exposed, candidates),
        "core_candidate_coverage": _coverage(core, candidates),
        "formal_candidate_coverage": _coverage(formal, candidates),
        "incremental_input_rows": int(len(incremental_input)),
        "incremental_rows": int(len(incremental)),
    }
    gates = {
        "no_future_formation": diagnostics["future_formation_rows"] == 0,
        "bse_absent": diagnostics["bse_rows"] == 0,
        "daily_universe_minimum": diagnostics["minimum_daily_members"] >= 700,
        "industry_coverage": diagnostics["industry_coverage"] >= 0.90,
        "market_cap_coverage": diagnostics["market_cap_coverage"] >= 0.90,
        "core_coverage": min(diagnostics["core_candidate_coverage"].values()) >= 0.90,
        "formal_coverage": min(diagnostics["formal_candidate_coverage"].values()) >= 0.90,
    }
    if not all(gates.values()):
        raise FundamentalEffectError(f"F1-1 label-free panel gates failed: {gates}")
    report: dict[str, object] = {
        "schema_version": runtime.residual_schema,
        "protocol_id": protocol.document["protocol_id"],
        "protocol_sha256": protocol.sha256,
        "policy_sha256": protocol.policy_sha256,
        "code_snapshot_sha256": code_snapshot_sha256(),
        "code_git_head": git_head(),
        "input_identity": input_identity,
        "residual_data_snapshot_sha256": data_snapshot,
        "diagnostics": diagnostics,
        "gates": gates,
        "artifacts": {
            "core": {
                "path": core_path.relative_to(project_root).as_posix(),
                "sha256": core_sha,
                "row_count": int(len(core)),
            },
            "formal": {
                "path": formal_path.relative_to(project_root).as_posix(),
                "sha256": formal_sha,
                "row_count": int(len(formal)),
            },
        },
        "labels_read": False,
        "rank_ic_computed": False,
        "returns_computed": False,
        "model_training_run": False,
        "network_requests": 0,
        "status": "PASS",
    }
    report_path, report_sha, report_reused = write_json_once(
        output_root / "residual_build_report.json",
        report,
    )
    return {
        **report,
        "report_path": report_path.relative_to(project_root).as_posix(),
        "report_sha256": report_sha,
        "report_reused": report_reused,
        "artifact_reuse": {"core": core_reused, "formal": formal_reused},
    }
