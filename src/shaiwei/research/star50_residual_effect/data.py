"""PIT feature extension, labels, frozen predictions, and neutralization for M4-1."""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.star50_residual.compute import (
    CANDIDATES,
    ResidualInputs,
    build_interval_returns,
    fit_candidates,
)
from shaiwei.research.star50_residual_effect.contract import (
    EffectProtocol,
    ResidualEffectError,
    project_path,
)


@dataclass(frozen=True)
class EffectInputs:
    members: pd.DataFrame
    market: pd.DataFrame
    benchmark: pd.DataFrame
    calendar: tuple[str, ...]
    discovery_reference: pd.DataFrame
    predictions: dict[str, pd.DataFrame]


def _date_key(value: Any) -> str:
    return str(value).replace("-", "")[:8]


def _source_code(instrument: str) -> str:
    value = str(instrument).upper()
    if len(value) == 8 and value[:2] in {"SH", "SZ"} and value[2:].isdigit():
        return f"{value[2:]}.{value[:2]}"
    raise ResidualEffectError(f"unsupported M4-1 instrument: {instrument}")


def _load_prediction(path: Path, purpose: str, expected_rows: int) -> pd.DataFrame:
    frame = pd.read_parquet(path)
    if set(frame.columns) != {"datetime", "instrument", "score"} or len(frame) != expected_rows:
        raise ResidualEffectError(f"M4-1 prediction schema/rows differ: {purpose}")
    frame["trade_date"] = pd.to_datetime(frame["datetime"]).dt.strftime("%Y%m%d")
    frame["ts_code"] = frame["instrument"].map(_source_code)
    frame["baseline_score"] = pd.to_numeric(frame["score"], errors="coerce")
    frame = frame[["trade_date", "ts_code", "baseline_score"]].copy()
    if (
        frame.duplicated(["trade_date", "ts_code"]).any()
        or frame["baseline_score"].isna().any()
        or not np.isfinite(frame["baseline_score"].to_numpy(dtype=float)).all()
        or frame["ts_code"].str.endswith(".BJ").any()
    ):
        raise ResidualEffectError(f"M4-1 invalid corrected prediction input: {purpose}")
    return frame.sort_values(["trade_date", "ts_code"]).reset_index(drop=True)


def load_inputs(
    protocol: EffectProtocol,
    *,
    project_root: Path = PROJECT_ROOT,
) -> EffectInputs:
    """Load only protocol-bound local inputs after an execution release is active."""
    protocol.verify_upstream(project_root=project_root)
    upstream = protocol.document["upstream_contract"]
    clock = protocol.document["feature_and_label_clock"]
    start = _date_key(clock["discovery"][0])
    end = _date_key(clock["extension_end"])
    warmup = _date_key(clock["input_warmup_start"])

    members = pd.read_parquet(project_path(upstream["official_member_days_path"], project_root=project_root))
    market = pd.read_parquet(project_path(upstream["market_path"], project_root=project_root))
    benchmark = pd.read_parquet(project_path(upstream["benchmark_path"], project_root=project_root))
    for frame in (members, market, benchmark):
        frame["trade_date"] = frame["trade_date"].astype(str).map(_date_key)
        frame["ts_code"] = frame["ts_code"].astype(str)
    members = members.loc[members["trade_date"].between(start, end)].copy()
    member_codes = set(members["ts_code"])
    market = market.loc[
        market["trade_date"].between(warmup, end) & market["ts_code"].isin(member_codes)
    ].copy()
    benchmark = benchmark.loc[
        benchmark["trade_date"].between(warmup, end)
        & benchmark["ts_code"].eq(protocol.document["identity"]["benchmark_source_code"])
    ].copy()
    for frame, keys, name in (
        (members, ["trade_date", "ts_code"], "member days"),
        (market, ["trade_date", "ts_code"], "market"),
        (benchmark, ["trade_date"], "benchmark"),
    ):
        if frame.empty or frame.duplicated(keys).any():
            raise ResidualEffectError(f"M4-1 {name} is empty or duplicated")
        if frame["ts_code"].str.endswith(".BJ").any():
            raise ResidualEffectError(f"M4-1 {name} contains forbidden .BJ")
    counts = members.groupby("trade_date")["ts_code"].nunique()
    if not counts.eq(50).all():
        raise ResidualEffectError("M4-1 official member count differs from 50")
    benchmark = benchmark.sort_values("trade_date").reset_index(drop=True)
    calendar = tuple(benchmark["trade_date"].astype(str))
    if not set(counts.index.astype(str)).issubset(calendar):
        raise ResidualEffectError("M4-1 member date is absent from benchmark calendar")

    discovery = pd.read_parquet(
        project_path(upstream["m4_discovery_feature_path"], project_root=project_root)
    )
    discovery["trade_date"] = discovery["trade_date"].astype(str).map(_date_key)
    discovery["ts_code"] = discovery["ts_code"].astype(str)
    prediction_frames = {
        str(row["purpose"]): _load_prediction(
            project_path(str(row["path"]), project_root=project_root),
            str(row["purpose"]),
            int(row["rows"]),
        )
        for row in upstream["corrected_prediction_inputs"]
    }
    return EffectInputs(
        members=members.sort_values(["trade_date", "ts_code"]).reset_index(drop=True),
        market=market.sort_values(["ts_code", "trade_date"]).reset_index(drop=True),
        benchmark=benchmark,
        calendar=calendar,
        discovery_reference=discovery.sort_values(["trade_date", "ts_code"]).reset_index(drop=True),
        predictions=prediction_frames,
    )


def build_extended_features(inputs: EffectInputs, protocol: EffectProtocol) -> pd.DataFrame:
    """Extend the frozen M4 formula without reading labels or future observations."""
    residual_inputs = ResidualInputs(
        members=inputs.members,
        market=inputs.market[["ts_code", "trade_date", "close"]],
        benchmark=inputs.benchmark[["ts_code", "trade_date", "close"]],
        calendar=inputs.calendar,
    )
    intervals = build_interval_returns(residual_inputs)
    positions = {date: index for index, date in enumerate(inputs.calendar)}
    denominator = inputs.members.loc[
        inputs.members["has_market_bar"].astype(bool)
        & inputs.members["industry"].notna()
        & inputs.members["industry"].astype(str).str.strip().ne("")
        & pd.to_numeric(inputs.members["total_mv"], errors="coerce").gt(0),
        ["trade_date", "ts_code"],
    ]
    rows: list[dict[str, Any]] = []
    for member in denominator.itertuples(index=False):
        signal_position = positions[str(member.trade_date)]
        window_start = signal_position - 59
        available = intervals.get(str(member.ts_code))
        if window_start < 0 or available is None:
            continue
        selected = available.loc[
            available["end_position"].le(signal_position)
            & available["start_position"].ge(window_start)
        ].tail(40)
        if len(selected) != 40 or str(selected.iloc[-1]["trade_date"]) != str(member.trade_date):
            continue
        values = fit_candidates(
            selected["stock_return"].to_numpy(),
            selected["benchmark_return"].to_numpy(),
            benchmark_variance_minimum=1e-12,
            residual_scale_minimum=1e-12,
        )
        if values is None:
            continue
        rows.append(
            {
                "trade_date": str(member.trade_date),
                "ts_code": str(member.ts_code),
                **values,
                "window_start": str(selected.iloc[0]["start_date"]),
                "window_end": str(selected.iloc[-1]["trade_date"]),
                "observation_count": 40,
            }
        )
    features = pd.DataFrame(rows).sort_values(["trade_date", "ts_code"]).reset_index(drop=True)
    if features.empty or features.duplicated(["trade_date", "ts_code"]).any():
        raise ResidualEffectError("M4-1 extended feature frame is empty or duplicated")
    numeric = features[[*CANDIDATES, "alpha", "beta", "residual_std"]].to_numpy(dtype=float)
    if not np.isfinite(numeric).all() or features["ts_code"].str.endswith(".BJ").any():
        raise ResidualEffectError("M4-1 extended features contain invalid values")

    discovery_end = _date_key(protocol.document["feature_and_label_clock"]["discovery"][1])
    actual = features.loc[features["trade_date"].le(discovery_end)].reset_index(drop=True)
    reference = inputs.discovery_reference.reset_index(drop=True)
    if list(actual.columns) != list(reference.columns) or not actual.equals(reference):
        raise ResidualEffectError("M4-1 discovery extension differs from immutable M4-0 truth")
    return features


def build_labels(inputs: EffectInputs, protocol: EffectProtocol) -> pd.DataFrame:
    """Build the frozen next-open to t+11-open label on the official benchmark calendar."""
    calendar = list(inputs.calendar)
    next_date = {day: calendar[i + 1] for i, day in enumerate(calendar[:-11])}
    exit_date = {day: calendar[i + 11] for i, day in enumerate(calendar[:-11])}
    base = inputs.members[["trade_date", "ts_code"]].copy()
    base["entry_date"] = base["trade_date"].map(next_date)
    base["exit_date"] = base["trade_date"].map(exit_date)
    opens = inputs.market[["trade_date", "ts_code", "open"]].copy()
    opens["open"] = pd.to_numeric(opens["open"], errors="coerce")
    entry = opens.rename(columns={"trade_date": "entry_date", "open": "entry_open"})
    exit_frame = opens.rename(columns={"trade_date": "exit_date", "open": "exit_open"})
    labeled = base.merge(entry, on=["entry_date", "ts_code"], how="left", validate="many_to_one")
    labeled = labeled.merge(
        exit_frame, on=["exit_date", "ts_code"], how="left", validate="many_to_one"
    )
    valid = (
        labeled["entry_open"].gt(0)
        & labeled["exit_open"].gt(0)
        & labeled["entry_date"].notna()
        & labeled["exit_date"].notna()
    )
    labeled["label"] = np.where(
        valid,
        labeled["exit_open"] / labeled["entry_open"] - 1.0,
        np.nan,
    )
    if labeled.duplicated(["trade_date", "ts_code"]).any():
        raise ResidualEffectError("M4-1 labels contain duplicate keys")
    return labeled[["trade_date", "ts_code", "entry_date", "exit_date", "label"]]


def _winsorized_zscore(values: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce").astype(float)
    clipped = numeric.clip(lower=numeric.quantile(0.01), upper=numeric.quantile(0.99))
    scale = float(clipped.std(ddof=0))
    if not math.isfinite(scale) or scale <= 0:
        return pd.Series(np.nan, index=values.index, dtype=float)
    return (clipped - clipped.mean()) / scale


def neutralize(
    features: pd.DataFrame,
    members: pd.DataFrame,
    *,
    predictions: pd.DataFrame | None,
    minimum_cross_section: int = 30,
) -> pd.DataFrame:
    """Daily PIT industry/cap residuals, optionally incremental to Alpha158."""
    exposures = members[["trade_date", "ts_code", "industry", "total_mv"]]
    frame = features.merge(exposures, on=["trade_date", "ts_code"], how="inner", validate="one_to_one")
    if predictions is not None:
        frame = frame.merge(
            predictions,
            on=["trade_date", "ts_code"],
            how="inner",
            validate="one_to_one",
        )
    outputs: list[pd.DataFrame] = []
    for trade_date, raw in frame.groupby("trade_date", sort=True):
        day = raw.loc[
            raw["industry"].notna() & pd.to_numeric(raw["total_mv"], errors="coerce").gt(0)
        ].copy()
        if predictions is not None:
            day = day.loc[pd.to_numeric(day["baseline_score"], errors="coerce").notna()].copy()
        if len(day) < minimum_cross_section:
            continue
        continuous = {"log_total_mv": _winsorized_zscore(np.log(day["total_mv"].astype(float)))}
        if predictions is not None:
            continuous["baseline_score"] = _winsorized_zscore(day["baseline_score"])
        design = pd.concat(
            [
                pd.Series(1.0, index=day.index, name="intercept"),
                pd.DataFrame(continuous, index=day.index),
                pd.get_dummies(day["industry"].astype(str), drop_first=True, dtype=float),
            ],
            axis=1,
        ).to_numpy(dtype=float)
        result = day[["trade_date", "ts_code"]].copy()
        for candidate in CANDIDATES:
            values = _winsorized_zscore(day[candidate]).to_numpy(dtype=float)
            if not np.isfinite(values).all():
                result[candidate] = np.nan
                continue
            with threadpool_limits(limits=1, user_api="blas"):
                coefficients, *_ = np.linalg.lstsq(design, values, rcond=None)
            result[candidate] = np.round(values - design @ coefficients, 12)
        outputs.append(result)
    if not outputs:
        raise ResidualEffectError("M4-1 neutralization produced no valid cross-section")
    result = pd.concat(outputs, ignore_index=True).sort_values(
        ["trade_date", "ts_code"], kind="stable"
    )
    if result.duplicated(["trade_date", "ts_code"]).any():
        raise ResidualEffectError("M4-1 neutralized panel contains duplicate keys")
    return result.reset_index(drop=True)
