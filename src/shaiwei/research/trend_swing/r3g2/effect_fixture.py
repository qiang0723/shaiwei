"""Pure synthetic positive and discovery-reject fixtures for R3G-2 effect."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from shaiwei.research.trend_swing.r3g2.contract import EffectProtocol
from shaiwei.research.trend_swing.r3g2.effect_inputs import PreparedPartition


def _calendar(start: str, end: str) -> tuple[str, ...]:
    return tuple(pd.bdate_range(start, end).strftime("%Y%m%d"))


def _event_indexes(calendar: tuple[str, ...], minimum_each_year: int) -> list[int]:
    output: list[int] = []
    years = sorted({day[:4] for day in calendar})
    for year in years:
        indexes = [index for index, day in enumerate(calendar) if day.startswith(year)]
        step = max(1, len(indexes) // (minimum_each_year + 2))
        choices = indexes[step : step * (minimum_each_year + 1) : step]
        output.extend(index for index in choices if index + 4 < len(calendar))
    return output


def _bars(calendar: tuple[str, ...], events: list[tuple[int, str]]) -> pd.DataFrame:
    event_by_code = {code: index for index, code in events}
    rows: list[dict[str, Any]] = []
    for code, event_index in sorted(event_by_code.items()):
        previous = 100.0
        for index, day in enumerate(calendar):
            if index < event_index:
                open_price, high, close = 100.0, 100.0, 100.0
            elif index == event_index:
                open_price, high, close = 100.0, 101.0, 101.0
            elif index == event_index + 1:
                open_price, high, close = 101.0, 101.0, 101.0
            elif index == event_index + 2:
                open_price, high, close = 100.0, 116.0, 115.0
            else:
                open_price, high, close = 115.0, 116.0, 115.0
            rows.append(
                {
                    "trade_date": day,
                    "ts_code": code,
                    "raw_open": open_price,
                    "raw_high": high,
                    "raw_low": min(open_price, close),
                    "raw_close": close,
                    "adj_open": open_price,
                    "adj_high": high,
                    "adj_low": min(open_price, close),
                    "adj_close": close,
                    "prior_raw_close": previous,
                    "volume_shares": 10_000_000.0,
                    "amount_median20_rmb": 1_000_000_000.0,
                    "adj_factor": 1.0,
                    "latest_complete_week_low": 91.83673469387755,
                    "security_eligible": True,
                    "listing_session_age": 100,
                    "industry": "SYNTHETIC",
                }
            )
            previous = close
    return pd.DataFrame(rows)


def _partition(protocol: EffectProtocol, partition: str, *, losing: bool = False) -> PreparedPartition:
    start, end, per_year = (
        ("2021-01-04", "2023-12-29", 12)
        if partition == "discovery"
        else ("2024-01-02", "2025-12-31", 10)
    )
    calendar = _calendar(start, end)
    indexes = _event_indexes(calendar, per_year)
    code_events = [(index, f"60{number:04d}.SH") for number, index in enumerate(indexes)]
    rows: list[dict[str, Any]] = []
    for point in protocol.selected_point_hashes:
        for rank, (index, code) in enumerate(code_events, start=1):
            rows.append(
                {
                    "point_hash": point,
                    "ts_code": code,
                    "signal_date": calendar[index - 1],
                    "execution_date": calendar[index],
                    "score_date": calendar[max(0, index - 5)],
                    "score": float(len(code_events) - rank),
                    "signal_rank": 1,
                    "industry": "SYNTHETIC",
                    "frozen_reference_adjusted": 99.0,
                    "initial_stop_adjusted": 90.0,
                }
            )
    benchmark_return = 0.002 if losing else 0.0
    return PreparedPartition(
        events=pd.DataFrame(rows),
        bars=_bars(calendar, code_events),
        benchmark=pd.DataFrame(
            {"trade_date": calendar, "benchmark_return": [benchmark_return] * len(calendar)}
        ),
        calendar=calendar,
    )


@dataclass
class SyntheticAdapter:
    protocol: EffectProtocol
    temporary: Path
    losing_discovery: bool = False
    holdout_load_count: int = 0

    def preflight(self) -> dict[str, Any]:
        return {
            "schema_version": "ts-v5-r3g2-pre-effect-key-preflight-v1",
            "protocol_sha256": self.protocol.sha256,
            "release_protocol_sha256": "synthetic",
            "partitions": {"discovery": {"synthetic": True}, "holdout": {"synthetic": True}},
            "score_values_read": False,
            "post_entry_outcomes_read": False,
            "benchmark_values_read": False,
            "strategy_effect_attempt_count": 0,
            "verdict": "GO_PRE_EFFECT_KEYS_ONLY",
        }

    def load_partition(self, partition: str) -> PreparedPartition:
        if partition == "holdout":
            self.holdout_load_count += 1
        return _partition(
            self.protocol,
            partition,
            losing=self.losing_discovery and partition == "discovery",
        )
