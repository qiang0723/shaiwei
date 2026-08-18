"""Real-input adapter for TS-v6-4: full parent 188-event discovery set."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from shaiwei.research.trend_swing.r3g2.effect_inputs import (
    PreparedPartition,
    _bars,
    _benchmark,
    _calendar,
    _connection,
    _rankable_events,
)
from shaiwei.research.trend_swing.v6_3.inputs import (
    DISCOVERY_ROLE,
    _rederive_parent_events,
    load_scores_w2_w6,
)
from shaiwei.research.trend_swing.v6_4.contract import V64Error, V64Scope


class V64Adapter:
    """Build the discovery partition only; holdout is physically unreachable here."""

    def __init__(self, scope: V64Scope, temporary: Path) -> None:
        self.scope = scope
        self.temporary = temporary
        self._preflight: dict[str, Any] | None = None

    def preflight(self) -> dict[str, Any]:
        connection = _connection(self.temporary / "preflight")
        try:
            full = _calendar(connection, "20160101", "20251231")
            _, start, end = DISCOVERY_ROLE
            calendar = _calendar(connection, start, end)
            events = _rederive_parent_events(connection, self.scope)
            score_keys = load_scores_w2_w6(self.scope, include_values=False).assign(score=True)
            ranked, coverage = _rankable_events(events, score_keys, full, calendar)
        finally:
            connection.close()
        self._preflight = {
            "schema_version": "ts-v6-4-pre-effect-key-preflight-v1",
            "protocol_sha256": self.scope.sha256,
            "partition": {
                "rederived_parent_event_count": len(events),
                "purged_rankable_event_count": len(ranked),
                "score_key_coverage": coverage,
                "calendar_day_count": len(calendar),
            },
            "score_values_read": False,
            "post_entry_outcomes_read": False,
            "benchmark_values_read": False,
            "holdout_rows_read": False,
            "strategy_effect_attempt_count": 0,
            "verdict": "GO_PRE_EFFECT_KEYS_ONLY",
        }
        return self._preflight

    def load_partition(self, partition: str) -> PreparedPartition:
        if partition != "discovery":
            raise V64Error("TS-v6-4 holdout outcomes are forbidden by this protocol")
        if self._preflight is None:
            raise V64Error("TS-v6-4 real values cannot load before key-only preflight")
        _, start, end = DISCOVERY_ROLE
        connection = _connection(self.temporary / partition)
        try:
            full = _calendar(connection, "20160101", "20251231")
            calendar = _calendar(connection, start, end)
            events = _rederive_parent_events(connection, self.scope)
            events, _ = _rankable_events(
                events, load_scores_w2_w6(self.scope, include_values=True), full, calendar
            )
            bars = _bars(connection, events["ts_code"].astype(str).tolist(), start, end)
        finally:
            connection.close()
        return PreparedPartition(
            events=events,
            bars=bars,
            benchmark=_benchmark(self.scope, calendar),
            calendar=calendar,
        )
