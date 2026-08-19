"""Real-input adapter for TS-B: full parent 180-event holdout set."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import pandas as pd

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.trend_swing.r3g2.effect_inputs import (
    PreparedPartition,
    _bars,
    _benchmark,
    _calendar,
    _candidate,
    _connection,
    _normalize_prediction,
    _rankable_events,
)
from shaiwei.research.trend_swing.v5_r3g1_runner import load_role_rows, project_effect_events
from shaiwei.research.trend_swing.ts_b.contract import PARENT_POINT_HASH, TSBError, TSBScope


HOLDOUT_ROLE = ("frozen_stability_holdout", "20240102", "20251231")


def load_scores_w6_w7(scope: TSBScope, *, include_values: bool) -> pd.DataFrame:
    """Load only the bound W6 (2024) and sealed W7 (2025) scores."""
    lineage = scope.document["ranking_lineage"]
    paths = [
        PROJECT_ROOT / lineage["clean_m6_lineage"]["reusable_predictions"]["W6"]["path"],
        PROJECT_ROOT / lineage["frozen_w7_extension"]["path"],
    ]
    columns = ["datetime", "instrument"] + (["score"] if include_values else [])
    frames = [
        _normalize_prediction(
            pd.read_parquet(path, columns=columns), include_values=include_values
        )
        for path in paths
    ]
    result = pd.concat(frames, ignore_index=True).sort_values(["score_date", "ts_code"])
    if result.duplicated(["score_date", "ts_code"]).any():
        raise TSBError("TS-B W6/W7 score keys overlap")
    if include_values and not result["score"].map(math.isfinite).all():
        raise TSBError("TS-B score values are nonfinite")
    return result


def _rederive_holdout_events(connection: Any, scope: TSBScope) -> pd.DataFrame:
    role, start, end = HOLDOUT_ROLE
    rows = load_role_rows(connection, start, end)
    events = project_effect_events(rows, _candidate(), scope.candidate_parameters(), role)
    frame = pd.DataFrame(events).rename(columns={"next_open_date": "execution_date"})
    keys = ["point_hash", "ts_code", "signal_date", "execution_date"]
    if frame.empty or frame.duplicated(keys).any() or frame["ts_code"].str.endswith(".BJ").any():
        raise TSBError("TS-B rederived event keys are empty, duplicated, or contain BSE")
    source = PROJECT_ROOT / scope.document["predecessors"]["r3g1_events"]["path"]
    bound = pd.read_parquet(source)
    bound = bound.loc[
        bound["role"].eq(role) & bound["point_hash"].eq(PARENT_POINT_HASH)
    ].rename(columns={"next_open_date": "execution_date"})[keys]
    if not frame[keys].sort_values(keys).reset_index(drop=True).equals(
        bound.sort_values(keys).reset_index(drop=True)
    ):
        raise TSBError("TS-B rederived event keys differ from R3G-1")
    return frame.sort_values(keys).reset_index(drop=True)


class TSBAdapter:
    """Build the holdout partition only; discovery and 2026 are physically unreachable."""

    def __init__(self, scope: TSBScope, temporary: Path) -> None:
        self.scope = scope
        self.temporary = temporary
        self._preflight: dict[str, Any] | None = None

    def preflight(self) -> dict[str, Any]:
        connection = _connection(self.temporary / "preflight")
        try:
            full = _calendar(connection, "20160101", "20251231")
            _, start, end = HOLDOUT_ROLE
            calendar = _calendar(connection, start, end)
            events = _rederive_holdout_events(connection, self.scope)
            score_keys = load_scores_w6_w7(self.scope, include_values=False).assign(score=True)
            ranked, coverage = _rankable_events(events, score_keys, full, calendar)
        finally:
            connection.close()
        self._preflight = {
            "schema_version": "ts-b-pre-effect-key-preflight-v1",
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
            "discovery_2021_2023_read": False,
            "strategy_effect_attempt_count": 0,
            "verdict": "GO_PRE_EFFECT_KEYS_ONLY",
        }
        return self._preflight

    def load_partition(self, partition: str) -> PreparedPartition:
        if partition != "holdout":
            raise TSBError("TS-B discovery and 2026 reads are forbidden by this protocol")
        if self._preflight is None:
            raise TSBError("TS-B real values cannot load before key-only preflight")
        _, start, end = HOLDOUT_ROLE
        connection = _connection(self.temporary / partition)
        try:
            full = _calendar(connection, "20160101", "20251231")
            calendar = _calendar(connection, start, end)
            events = _rederive_holdout_events(connection, self.scope)
            events, _ = _rankable_events(
                events, load_scores_w6_w7(self.scope, include_values=True), full, calendar
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
