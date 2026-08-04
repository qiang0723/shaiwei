"""PIT input loading and deterministic STAR50 residual feature construction."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.star50_residual.contract import ResidualGateError, ResidualProtocol


CANDIDATES = (
    "residual_momentum_35_skip5",
    "residual_reversal_5",
    "negative_idiosyncratic_volatility_40",
)


@dataclass(frozen=True)
class ResidualInputs:
    members: pd.DataFrame
    market: pd.DataFrame
    benchmark: pd.DataFrame
    calendar: tuple[str, ...]


def _key(value: Any) -> str:
    return str(value).replace("-", "")[:8]


def _assert_no_bse(frame: pd.DataFrame, column: str, label: str) -> None:
    if frame[column].astype(str).str.endswith(".BJ", na=False).any():
        raise ResidualGateError(f"{label} contains forbidden .BJ securities")


def load_inputs(
    protocol: ResidualProtocol,
    *,
    project_root: Path = PROJECT_ROOT,
) -> ResidualInputs:
    """Read only the frozen feature inputs; no label or result artifact is addressed."""
    protocol.verify_upstream(project_root=project_root)
    doc = protocol.document
    clock = doc["data_clock"]
    start, end = (_key(value) for value in clock["discovery_signal_period"])
    warmup = _key(clock["input_warmup_start"])

    members = pd.read_parquet(
        protocol.path_for("official_member_days_path", project_root=project_root),
        columns=["trade_date", "ts_code", "has_market_bar", "industry", "total_mv"],
        filters=[("trade_date", ">=", start), ("trade_date", "<=", end)],
    )
    members["trade_date"] = members["trade_date"].astype(str).map(_key)
    members = members.loc[members["trade_date"].between(start, end)].copy()
    members["ts_code"] = members["ts_code"].astype(str)

    codes = set(members["ts_code"])
    market = pd.read_parquet(
        protocol.path_for("market_path", project_root=project_root),
        columns=["ts_code", "trade_date", "close"],
        filters=[("trade_date", ">=", warmup), ("trade_date", "<=", end)],
    )
    market["trade_date"] = market["trade_date"].astype(str).map(_key)
    market["ts_code"] = market["ts_code"].astype(str)
    market = market.loc[
        market["trade_date"].between(warmup, end) & market["ts_code"].isin(codes)
    ].copy()

    benchmark = pd.read_parquet(
        protocol.path_for("benchmark_path", project_root=project_root),
        columns=["ts_code", "trade_date", "close"],
        filters=[("trade_date", ">=", warmup), ("trade_date", "<=", end)],
    )
    benchmark["trade_date"] = benchmark["trade_date"].astype(str).map(_key)
    benchmark["ts_code"] = benchmark["ts_code"].astype(str)
    benchmark = benchmark.loc[
        benchmark["trade_date"].between(warmup, end)
        & benchmark["ts_code"].eq(doc["identity"]["benchmark_source_code"])
    ].copy()

    for frame, keys, label in (
        (members, ["trade_date", "ts_code"], "member days"),
        (market, ["trade_date", "ts_code"], "market"),
        (benchmark, ["trade_date"], "benchmark"),
    ):
        if frame.empty or frame.duplicated(keys).any():
            raise ResidualGateError(f"M4-0 {label} is empty or has duplicate keys")
    _assert_no_bse(members, "ts_code", "member days")
    _assert_no_bse(market, "ts_code", "market")
    if benchmark["close"].isna().any() or (pd.to_numeric(benchmark["close"]) <= 0).any():
        raise ResidualGateError("M4-0 benchmark contains non-positive or missing closes")

    counts = members.groupby("trade_date")["ts_code"].nunique()
    if len(counts) != int(clock["expected_signal_trade_days"]):
        raise ResidualGateError("M4-0 signal trade-day count differs")
    if not counts.eq(int(clock["expected_official_members_per_day"])).all():
        raise ResidualGateError("M4-0 official member count differs from 50")
    if len(members) != int(clock["expected_member_days"]):
        raise ResidualGateError("M4-0 official member-day count differs")

    benchmark = benchmark.sort_values("trade_date").reset_index(drop=True)
    calendar = tuple(benchmark["trade_date"].astype(str))
    signal_dates = tuple(counts.index.astype(str))
    if any(date not in set(calendar) for date in signal_dates):
        raise ResidualGateError("M4-0 signal date is absent from benchmark calendar")
    return ResidualInputs(
        members=members.sort_values(["trade_date", "ts_code"]).reset_index(drop=True),
        market=market.sort_values(["ts_code", "trade_date"]).reset_index(drop=True),
        benchmark=benchmark,
        calendar=calendar,
    )


def build_interval_returns(inputs: ResidualInputs) -> dict[str, pd.DataFrame]:
    """Create stock and benchmark returns over identical tradable endpoints."""
    benchmark_close = inputs.benchmark.set_index("trade_date")["close"].astype(float)
    calendar_position = {date: index for index, date in enumerate(inputs.calendar)}
    intervals: dict[str, pd.DataFrame] = {}
    for code, raw in inputs.market.groupby("ts_code", sort=True):
        frame = raw[["trade_date", "close"]].copy().sort_values("trade_date")
        frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
        frame = frame.loc[frame["close"].gt(0)].copy()
        frame["start_date"] = frame["trade_date"].shift(1)
        frame["start_close"] = frame["close"].shift(1)
        frame["benchmark_end_close"] = frame["trade_date"].map(benchmark_close)
        frame["benchmark_start_close"] = frame["start_date"].map(benchmark_close)
        frame = frame.dropna().copy()
        frame["stock_return"] = np.log(frame["close"] / frame["start_close"])
        frame["benchmark_return"] = np.log(
            frame["benchmark_end_close"] / frame["benchmark_start_close"]
        )
        frame["start_position"] = frame["start_date"].map(calendar_position)
        frame["end_position"] = frame["trade_date"].map(calendar_position)
        frame = frame.replace([np.inf, -np.inf], np.nan).dropna()
        intervals[str(code)] = frame[
            [
                "start_date",
                "trade_date",
                "start_position",
                "end_position",
                "stock_return",
                "benchmark_return",
            ]
        ].reset_index(drop=True)
    return intervals


def fit_candidates(
    stock_returns: np.ndarray,
    benchmark_returns: np.ndarray,
    *,
    benchmark_variance_minimum: float,
    residual_scale_minimum: float,
) -> dict[str, float] | None:
    """Apply the frozen single-index construction to exactly 40 intervals."""
    y = np.asarray(stock_returns, dtype=np.float64)
    x = np.asarray(benchmark_returns, dtype=np.float64)
    if y.shape != (40,) or x.shape != (40,) or not (np.isfinite(y).all() and np.isfinite(x).all()):
        return None
    centered_x = x - x.mean()
    denominator = float(np.dot(centered_x, centered_x))
    if denominator / len(x) < benchmark_variance_minimum:
        return None
    beta = float(np.dot(centered_x, y - y.mean()) / denominator)
    alpha = float(y.mean() - beta * x.mean())
    residuals = y - alpha - beta * x
    residual_scale = float(np.sqrt(np.dot(residuals, residuals) / (len(x) - 2)))
    if not np.isfinite(residual_scale) or residual_scale <= residual_scale_minimum:
        return None
    adjusted = y - beta * x
    values = {
        "residual_momentum_35_skip5": float(adjusted[:-5].sum() / residual_scale),
        "residual_reversal_5": float(-adjusted[-5:].sum() / residual_scale),
        "negative_idiosyncratic_volatility_40": -residual_scale,
        "alpha": alpha,
        "beta": beta,
        "residual_std": residual_scale,
    }
    return values if all(np.isfinite(value) for value in values.values()) else None


def compute_feature_frame(
    inputs: ResidualInputs,
    protocol: ResidualProtocol,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return finite features and the frozen structural coverage denominator."""
    clock = protocol.document["data_clock"]
    regression = protocol.document["regression_contract"]
    window = int(clock["endpoint_window_trade_days"])
    observations = int(clock["regression_observations_exact"])
    if observations != 40 or window < observations:
        raise ResidualGateError("M4-0 regression/window contract differs")
    positions = {date: index for index, date in enumerate(inputs.calendar)}
    intervals = build_interval_returns(inputs)

    denominator = inputs.members.loc[
        inputs.members["has_market_bar"].astype(bool)
        & inputs.members["industry"].notna()
        & inputs.members["industry"].astype(str).str.strip().ne("")
        & pd.to_numeric(inputs.members["total_mv"], errors="coerce").gt(0),
        ["trade_date", "ts_code"],
    ].copy()
    rows: list[dict[str, Any]] = []
    for member in denominator.itertuples(index=False):
        signal_position = positions[str(member.trade_date)]
        window_start = signal_position - window + 1
        if window_start < 0:
            continue
        available = intervals.get(str(member.ts_code))
        if available is None:
            continue
        selected = available.loc[
            available["end_position"].le(signal_position)
            & available["start_position"].ge(window_start)
        ].tail(observations)
        if len(selected) != observations or str(selected.iloc[-1]["trade_date"]) != str(member.trade_date):
            continue
        values = fit_candidates(
            selected["stock_return"].to_numpy(),
            selected["benchmark_return"].to_numpy(),
            benchmark_variance_minimum=float(regression["benchmark_variance_minimum"]),
            residual_scale_minimum=float(regression["residual_scale_minimum"]),
        )
        if values is None:
            continue
        rows.append(
            {
                "trade_date": str(member.trade_date),
                "ts_code": str(member.ts_code),
                **{candidate: values[candidate] for candidate in CANDIDATES},
                "alpha": values["alpha"],
                "beta": values["beta"],
                "residual_std": values["residual_std"],
                "window_start": str(selected.iloc[0]["start_date"]),
                "window_end": str(selected.iloc[-1]["trade_date"]),
                "observation_count": observations,
            }
        )
    features = pd.DataFrame(rows)
    if features.empty:
        features = pd.DataFrame(
            columns=[
                "trade_date",
                "ts_code",
                *CANDIDATES,
                "alpha",
                "beta",
                "residual_std",
                "window_start",
                "window_end",
                "observation_count",
            ]
        )
    return (
        features.sort_values(["trade_date", "ts_code"]).reset_index(drop=True),
        denominator.sort_values(["trade_date", "ts_code"]).reset_index(drop=True),
    )
