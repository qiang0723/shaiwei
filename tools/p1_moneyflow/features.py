"""Frozen T+1 money-flow feature derivation for the isolated P1 experiment."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable

import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

from tools.p1_moneyflow.contract import MONEYFLOW_FIELDS


class MoneyflowFeatureError(RuntimeError):
    pass


FORMAL_CANDIDATES = (
    "mf_net_intensity_1d",
    "mf_large_intensity_1d",
    "mf_net_intensity_5d",
    "mf_net_intensity_20d",
    "mf_net_innovation_5_20",
    "mf_net_persistence_10d",
)
RESIDUAL_SERIALIZATION_DECIMALS = 12

FEATURE_POLICY: dict[str, object] = {
    "version": "p1-moneyflow-v1",
    "source_api": "tushare.moneyflow",
    "feature_available_lag_trade_days": 1,
    "rolling_windows_trade_days": [5, 10, 20],
    "rolling_requires_consecutive_official_trade_days": True,
    "missing_policy": "leave_missing_no_fill",
    "cross_section_winsor_quantiles": [0.01, 0.99],
    "minimum_cross_section": 30,
    "source_day_quality_policy_version": "moneyflow-quality-v2",
    "failed_source_day_treatment": "quarantine_entire_day_no_fill",
    "formal_candidates": list(FORMAL_CANDIDATES),
    "formal_residual_exposures": [
        "sw_l1_industry_pit",
        "log_total_mv",
        "log_daily_amount",
        "turnover_rate",
    ],
    "oos_incremental_exposure": "alpha158_baseline_score",
}

_SOURCE_FIELDS = (
    "ts_code",
    "trade_date",
    "buy_lg_amount",
    "sell_lg_amount",
    "buy_elg_amount",
    "sell_elg_amount",
    "net_mf_amount",
)
_GROSS_FLOW_FIELDS = (
    "buy_lg_amount",
    "sell_lg_amount",
    "buy_elg_amount",
    "sell_elg_amount",
)
_CORE_EXPOSURE_FIELDS = (
    "industry",
    "market_cap",
    "amount",
    "turnover_rate",
)


def feature_policy_sha256() -> str:
    payload = json.dumps(FEATURE_POLICY, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def official_trade_dates(values: Iterable[str]) -> list[str]:
    dates = sorted({str(value) for value in values})
    if len(dates) < 2:
        raise ValueError("at least two official trade dates are required")
    parsed = pd.to_datetime(pd.Series(dates), format="%Y%m%d", errors="coerce")
    if parsed.isna().any() or parsed.dt.strftime("%Y%m%d").tolist() != dates:
        raise ValueError("official trade dates must be valid YYYYMMDD values")
    return dates


def _require_columns(frame: pd.DataFrame, required: Iterable[str], *, name: str) -> None:
    missing = set(required) - set(frame.columns)
    if missing:
        raise MoneyflowFeatureError(f"{name} missing fields: {sorted(missing)}")


def _canonical_keys(frame: pd.DataFrame, *, name: str) -> pd.DataFrame:
    result = frame.copy()
    if result.loc[:, ["ts_code", "trade_date"]].isna().any(axis=None):
        raise MoneyflowFeatureError(f"{name} contains null keys")
    result["ts_code"] = result["ts_code"].astype(str)
    result["trade_date"] = result["trade_date"].astype(str)
    if result.duplicated(["ts_code", "trade_date"]).any():
        raise MoneyflowFeatureError(f"{name} contains duplicate keys")
    if result["ts_code"].str.endswith(".BJ").any():
        raise MoneyflowFeatureError(f"{name} contains .BJ rows")
    return result


def _finite_numeric(frame: pd.DataFrame, columns: Iterable[str], *, name: str) -> None:
    for column in columns:
        original = frame[column]
        numeric = pd.to_numeric(original, errors="coerce")
        invalid = original.notna() & (numeric.isna() | ~np.isfinite(numeric))
        if invalid.any():
            raise MoneyflowFeatureError(f"{name}.{column} contains non-finite values")
        frame[column] = numeric


def _rolling_sum(frame: pd.DataFrame, column: str, window: int) -> pd.Series:
    values = (
        frame.groupby("ts_code", sort=False)[column]
        .rolling(window, min_periods=window)
        .sum()
        .reset_index(level=0, drop=True)
        .reindex(frame.index)
    )
    first_rank = frame.groupby("ts_code", sort=False)["_calendar_rank"].shift(window - 1)
    consecutive = frame["_calendar_rank"].sub(first_rank).eq(window - 1)
    return values.where(consecutive)


def _winsorize_cross_section(series: pd.Series, minimum: int) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan)
    valid = numeric.dropna()
    if len(valid) < minimum:
        return pd.Series(np.nan, index=series.index, dtype=float)
    lower, upper = valid.quantile([0.01, 0.99])
    return numeric.clip(lower=float(lower), upper=float(upper))


def build_moneyflow_features(
    moneyflow: pd.DataFrame,
    daily: pd.DataFrame,
    trade_dates: Iterable[str],
    *,
    min_cross_section: int = 30,
) -> pd.DataFrame:
    """Build six preregistered raw candidates and map source D to official D+1."""

    if min_cross_section < 2:
        raise ValueError("min_cross_section must be at least two")
    calendar = official_trade_dates(trade_dates)
    calendar_rank = {trade_date: rank for rank, trade_date in enumerate(calendar)}
    next_trade_date = {
        trade_date: calendar[index + 1]
        for index, trade_date in enumerate(calendar[:-1])
    }

    _require_columns(moneyflow, MONEYFLOW_FIELDS["moneyflow"], name="moneyflow")
    _require_columns(daily, ("ts_code", "trade_date", "amount"), name="daily")
    source = _canonical_keys(moneyflow.loc[:, _SOURCE_FIELDS], name="moneyflow")
    reference = _canonical_keys(daily.loc[:, ["ts_code", "trade_date", "amount"]], name="daily")
    _finite_numeric(source, (*_GROSS_FLOW_FIELDS, "net_mf_amount"), name="moneyflow")
    _finite_numeric(reference, ("amount",), name="daily")
    if source.loc[:, _GROSS_FLOW_FIELDS].lt(0).any(axis=None):
        raise MoneyflowFeatureError("moneyflow contains negative gross large-order amounts")
    if reference["amount"].lt(0).any():
        raise MoneyflowFeatureError("daily.amount contains negative values")

    unknown_dates = sorted(set(source["trade_date"]) - set(calendar))
    if unknown_dates:
        raise MoneyflowFeatureError(
            f"moneyflow contains non-official trade dates: {unknown_dates[:5]}"
        )
    joined = source.merge(
        reference,
        on=["ts_code", "trade_date"],
        how="inner",
        validate="one_to_one",
    )
    if joined.empty:
        raise MoneyflowFeatureError("moneyflow and daily have no common observations")
    joined["_calendar_rank"] = joined["trade_date"].map(calendar_rank)
    joined = joined.sort_values(["ts_code", "_calendar_rank"], kind="stable").reset_index(drop=True)
    joined["_daily_amount_wan"] = joined["amount"] / 10.0
    joined["_large_signed_amount"] = (
        joined["buy_lg_amount"]
        + joined["buy_elg_amount"]
        - joined["sell_lg_amount"]
        - joined["sell_elg_amount"]
    )

    positive_amount = joined["_daily_amount_wan"].gt(0)
    joined["mf_net_intensity_1d"] = (
        joined["net_mf_amount"] / joined["_daily_amount_wan"]
    ).where(positive_amount)
    joined["mf_large_intensity_1d"] = (
        joined["_large_signed_amount"] / joined["_daily_amount_wan"]
    ).where(positive_amount)

    net_5 = _rolling_sum(joined, "net_mf_amount", 5)
    amount_5 = _rolling_sum(joined, "_daily_amount_wan", 5)
    net_20 = _rolling_sum(joined, "net_mf_amount", 20)
    amount_20 = _rolling_sum(joined, "_daily_amount_wan", 20)
    joined["mf_net_intensity_5d"] = (net_5 / amount_5).where(amount_5.gt(0))
    joined["mf_net_intensity_20d"] = (net_20 / amount_20).where(amount_20.gt(0))
    joined["mf_net_innovation_5_20"] = (
        joined["mf_net_intensity_5d"] - joined["mf_net_intensity_20d"]
    )
    joined["_net_sign"] = np.sign(joined["net_mf_amount"])
    joined["mf_net_persistence_10d"] = _rolling_sum(joined, "_net_sign", 10) / 10.0

    result = joined.loc[:, ["ts_code", "trade_date", *FORMAL_CANDIDATES]].rename(
        columns={"trade_date": "source_trade_date"}
    )
    result.insert(1, "trade_date", result["source_trade_date"].map(next_trade_date))
    result = result.dropna(subset=["trade_date"]).copy()
    for candidate in FORMAL_CANDIDATES:
        result[candidate] = result.groupby("trade_date", sort=False)[candidate].transform(
            _winsorize_cross_section,
            minimum=min_cross_section,
        )
    return result.sort_values(["trade_date", "ts_code"], kind="stable").reset_index(drop=True)


def _winsorized_standard_score(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan)
    valid = numeric.dropna()
    if valid.empty:
        return numeric
    lower, upper = valid.quantile([0.01, 0.99])
    clipped = numeric.clip(float(lower), float(upper))
    standard_deviation = clipped.std(ddof=0)
    if not np.isfinite(standard_deviation) or standard_deviation <= 0:
        return pd.Series(0.0, index=series.index, dtype=float).where(clipped.notna())
    return (clipped - clipped.mean()) / standard_deviation


def residualize_moneyflow_candidates(
    features: pd.DataFrame,
    exposures: pd.DataFrame,
    *,
    min_cross_section: int = 30,
    include_baseline_score: bool = True,
) -> pd.DataFrame:
    """Build core residuals, optionally removing the frozen OOS Alpha158 score."""

    if min_cross_section < 2:
        raise ValueError("min_cross_section must be at least two")
    _require_columns(
        features,
        ("ts_code", "trade_date", "source_trade_date", *FORMAL_CANDIDATES),
        name="features",
    )
    _require_columns(
        exposures,
        (
            "ts_code",
            "trade_date",
            *_CORE_EXPOSURE_FIELDS,
            *(("baseline_score",) if include_baseline_score else ()),
        ),
        name="exposures",
    )
    feature_frame = _canonical_keys(features, name="features")
    exposure_frame = _canonical_keys(exposures, name="exposures")
    merged = feature_frame.merge(
        exposure_frame,
        on=["ts_code", "trade_date"],
        how="inner",
        validate="one_to_one",
    )
    if merged.empty:
        raise MoneyflowFeatureError("features and exposures have no common observations")
    # DuckDB joins are intentionally free to return rows in any order.  Freeze the
    # cross-sectional row order before fitting so identical inputs cannot change
    # the floating-point reduction order between runs.
    merged = merged.sort_values(["trade_date", "ts_code"], kind="stable").reset_index(drop=True)
    _finite_numeric(merged, FORMAL_CANDIDATES, name="features")
    continuous_fields = ["market_cap", "amount", "turnover_rate"]
    if include_baseline_score:
        continuous_fields.append("baseline_score")
    _finite_numeric(merged, continuous_fields, name="exposures")
    merged.loc[merged["market_cap"].le(0), "market_cap"] = np.nan
    merged.loc[merged["amount"].le(0), "amount"] = np.nan

    outputs = []
    for trade_date, group in merged.groupby("trade_date", sort=True):
        base_valid = group.loc[
            group["industry"].notna()
            & group.loc[:, continuous_fields].notna().all(axis=1)
        ].copy()
        if len(base_valid) < min_cross_section:
            continue
        base_valid["log_market_cap"] = np.log(base_valid["market_cap"])
        base_valid["log_amount"] = np.log(base_valid["amount"])
        continuous_values = {
            "log_market_cap": _winsorized_standard_score(base_valid["log_market_cap"]),
            "log_amount": _winsorized_standard_score(base_valid["log_amount"]),
            "turnover_rate": _winsorized_standard_score(base_valid["turnover_rate"]),
        }
        if include_baseline_score:
            continuous_values["baseline_score"] = _winsorized_standard_score(
                base_valid["baseline_score"]
            )
        continuous = pd.DataFrame(continuous_values, index=base_valid.index)
        industries = pd.get_dummies(
            base_valid["industry"].astype(str),
            prefix="industry",
            drop_first=True,
            dtype=float,
        )
        design = pd.concat(
            [
                pd.Series(1.0, index=base_valid.index, name="intercept"),
                continuous,
                industries,
            ],
            axis=1,
        )
        matrix = design.to_numpy(dtype=float)
        day = base_valid.loc[:, ["ts_code", "trade_date", "source_trade_date"]].copy()
        has_candidate = False
        for candidate in FORMAL_CANDIDATES:
            valid = base_valid[candidate].notna()
            residual = pd.Series(np.nan, index=base_valid.index, dtype=float)
            if int(valid.sum()) >= min_cross_section and base_valid.loc[valid, candidate].nunique() >= 2:
                candidate_matrix = matrix[valid.to_numpy()]
                values = base_valid.loc[valid, candidate].to_numpy(dtype=float)
                # LAPACK may otherwise reduce the same cross-section in a different
                # order across worker threads, which changes a few last-bit values
                # and breaks byte-identical immutable artifacts.
                with threadpool_limits(limits=1, user_api="blas"):
                    coefficients, *_ = np.linalg.lstsq(
                        candidate_matrix, values, rcond=None
                    )
                    fitted = candidate_matrix @ coefficients
                residual.loc[valid] = np.round(
                    values - fitted, decimals=RESIDUAL_SERIALIZATION_DECIMALS
                )
                has_candidate = True
            day[candidate] = residual
        if has_candidate:
            outputs.append(day)
    if not outputs:
        raise MoneyflowFeatureError("no daily cross-section passed residualization gates")
    return pd.concat(outputs, ignore_index=True).sort_values(
        ["trade_date", "ts_code"], kind="stable"
    ).reset_index(drop=True)


def audit_feature_lineage(panel: pd.DataFrame, trade_dates: Iterable[str]) -> dict[str, object]:
    """Verify every feature row is mapped from exactly the prior official trade day."""

    _require_columns(
        panel,
        ("ts_code", "trade_date", "source_trade_date", *FORMAL_CANDIDATES),
        name="feature panel",
    )
    if panel.duplicated(["ts_code", "trade_date"]).any():
        raise MoneyflowFeatureError("feature panel contains duplicate keys")
    if panel["ts_code"].astype(str).str.endswith(".BJ").any():
        raise MoneyflowFeatureError("feature panel contains .BJ rows")
    calendar = official_trade_dates(trade_dates)
    prior = {calendar[index + 1]: calendar[index] for index in range(len(calendar) - 1)}
    expected = panel["trade_date"].astype(str).map(prior)
    lineage_ok = expected.eq(panel["source_trade_date"].astype(str))
    if not lineage_ok.all():
        raise MoneyflowFeatureError("feature panel violates the frozen T+1 lineage")
    coverage = {
        candidate: {
            "non_null_count": int(panel[candidate].notna().sum()),
            "non_null_trade_dates": int(panel.loc[panel[candidate].notna(), "trade_date"].nunique()),
        }
        for candidate in FORMAL_CANDIDATES
    }
    return {
        "status": "PASS",
        "feature_policy_sha256": feature_policy_sha256(),
        "row_count": int(len(panel)),
        "trade_date_count": int(panel["trade_date"].nunique()),
        "bse_row_count": 0,
        "lineage_violation_count": 0,
        "candidate_coverage": coverage,
    }
