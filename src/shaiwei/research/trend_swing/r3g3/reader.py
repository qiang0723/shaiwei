"""Narrow reader for the sealed R3G-2 discovery artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from shaiwei.research.trend_swing.r3g3.contract import (
    SCENARIOS,
    DiagnosticProtocol,
    read_json,
    verify_parent_sources,
)
from shaiwei.research.trend_swing.r3g3.evidence import R3G3Error


NAV_COLUMNS = {
    "trade_date", "nav", "daily_return", "benchmark_return", "active_return",
    "cash_ratio", "gross_weight", "maximum_security_weight", "maximum_industry_weight",
    "position_count", "corporate_action_overlap_count",
}
ORDER_COLUMNS = {
    "trade_date", "ts_code", "side", "batch", "reason", "status", "filled_notional",
    "capacity_limited",
}
TRADE_COLUMNS = {
    "trade_date", "episode_id", "ts_code", "industry", "side", "batch", "reason",
    "gross_notional", "fees", "closed_trade", "closed_trade_pnl",
}


@dataclass(frozen=True)
class PointInputs:
    nav: pd.DataFrame
    orders: pd.DataFrame
    trades: pd.DataFrame
    summaries: dict[str, dict[str, Any]]


@dataclass(frozen=True)
class DiagnosticInputs:
    identity: dict[str, Any]
    points: dict[str, PointInputs]


def _frame(path: Path, required: set[str], label: str, start: str, end: str) -> pd.DataFrame:
    try:
        frame = pd.read_parquet(path)
    except (OSError, ValueError) as error:
        raise R3G3Error(f"R3G-3 {label} artifact is unreadable") from error
    if set(frame.columns) != required or frame.empty:
        raise R3G3Error(f"R3G-3 {label} schema or rows differ")
    dates = frame["trade_date"].astype(str)
    if dates.lt(start).any() or dates.gt(end).any():
        raise R3G3Error(f"R3G-3 {label} escapes the discovery window")
    return frame


def load_inputs(protocol: DiagnosticProtocol, root: Path) -> DiagnosticInputs:
    identity = verify_parent_sources(protocol, root)
    boundary = protocol.document["allowed_read_boundary"]
    start, end = boundary["start"], boundary["end"]
    points: dict[str, PointInputs] = {}
    for role, point_hash in protocol.points:
        point = root / "discovery" / point_hash
        base = point / "base_1x"
        nav = _frame(base / "nav.parquet", NAV_COLUMNS, "NAV", start, end)
        orders = _frame(base / "orders.parquet", ORDER_COLUMNS, "orders", start, end)
        trades = _frame(base / "trades.parquet", TRADE_COLUMNS, "trades", start, end)
        if (
            nav["trade_date"].astype(str).duplicated().any()
            or orders["ts_code"].astype(str).str.endswith(".BJ").any()
            or trades["ts_code"].astype(str).str.endswith(".BJ").any()
        ):
            raise R3G3Error("R3G-3 discovery artifact key boundary differs")
        summaries = {scenario: read_json(point / scenario / "summary.json") for scenario in SCENARIOS}
        points[role] = PointInputs(nav, orders, trades, summaries)
    return DiagnosticInputs(identity=identity, points=points)

