"""Real-input adapter for TS-v6-3: parent event rederivation plus frozen 94-key filter."""

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
from shaiwei.research.trend_swing.v6_3.contract import PARENT_POINT_HASH, V63Error, V63Scope


DISCOVERY_ROLE = ("selectable_discovery", "20210104", "20231229")


def load_scores_w2_w6(scope: V63Scope, *, include_values: bool) -> pd.DataFrame:
    """Load only the bound W2-W6 clean-lineage scores; W7/2024+ scores stay unread."""
    reusable = scope.document["ranking_lineage"]["clean_m6_lineage"]["reusable_predictions"]
    columns = ["datetime", "instrument"] + (["score"] if include_values else [])
    frames = [
        _normalize_prediction(
            pd.read_parquet(PROJECT_ROOT / reusable[name]["path"], columns=columns),
            include_values=include_values,
        )
        for name in ("W2", "W3", "W4", "W5", "W6")
    ]
    result = pd.concat(frames, ignore_index=True).sort_values(["score_date", "ts_code"])
    if result.duplicated(["score_date", "ts_code"]).any():
        raise V63Error("TS-v6-3 W2-W6 score keys overlap")
    if include_values and not result["score"].map(math.isfinite).all():
        raise V63Error("TS-v6-3 score values are nonfinite")
    return result


def frozen_candidate_keys(scope: V63Scope) -> set[tuple[str, str, str]]:
    """The v6-1 frozen Top-94 development keys; holdout rows are forbidden here."""
    row = scope.document["predecessors"]["v6_1_ranked_events"]
    frame = pd.read_parquet(PROJECT_ROOT / row["path"])
    selected = frame.loc[
        frame["role"].eq("selectable_discovery") & frame["selected"].astype(bool)
    ]
    keys = {
        (str(item.ts_code), str(item.signal_date), str(item.next_open_date))
        for item in selected.itertuples(index=False)
    }
    if len(keys) != 94 or len(keys) != len(selected):
        raise V63Error("TS-v6-3 frozen candidate key set differs from 94")
    return keys


def _rederive_parent_events(connection: Any, scope: V63Scope) -> pd.DataFrame:
    role, start, end = DISCOVERY_ROLE
    rows = load_role_rows(connection, start, end)
    events = project_effect_events(rows, _candidate(), scope.candidate_parameters(), role)
    frame = pd.DataFrame(events).rename(columns={"next_open_date": "execution_date"})
    keys = ["point_hash", "ts_code", "signal_date", "execution_date"]
    if frame.empty or frame.duplicated(keys).any() or frame["ts_code"].str.endswith(".BJ").any():
        raise V63Error("TS-v6-3 rederived event keys are empty, duplicated, or contain BSE")
    source = PROJECT_ROOT / scope.document["predecessors"]["r3g1_events"]["path"]
    bound = pd.read_parquet(source)
    bound = bound.loc[
        bound["role"].eq(role) & bound["point_hash"].eq(PARENT_POINT_HASH)
    ].rename(columns={"next_open_date": "execution_date"})[keys]
    if not frame[keys].sort_values(keys).reset_index(drop=True).equals(
        bound.sort_values(keys).reset_index(drop=True)
    ):
        raise V63Error("TS-v6-3 rederived event keys differ from R3G-1")
    return frame.sort_values(keys).reset_index(drop=True)


def _apply_candidate_filter(frame: pd.DataFrame, scope: V63Scope) -> pd.DataFrame:
    keys = frozen_candidate_keys(scope)
    matched = frame.loc[
        frame.apply(
            lambda row: (str(row["ts_code"]), str(row["signal_date"]), str(row["execution_date"]))
            in keys,
            axis=1,
        )
    ].copy()
    observed = {
        (str(item.ts_code), str(item.signal_date), str(item.execution_date))
        for item in matched.itertuples(index=False)
    }
    if observed != keys or len(matched) != 94:
        raise V63Error(
            "BLOCKED_PRE_EFFECT: TS-v6-3 candidate set does not equal the frozen 94 keys"
        )
    return matched.reset_index(drop=True)


class V63Adapter:
    """Build the discovery partition only; holdout is physically unreachable here."""

    def __init__(self, scope: V63Scope, temporary: Path) -> None:
        self.scope = scope
        self.temporary = temporary
        self._preflight: dict[str, Any] | None = None

    def preflight(self) -> dict[str, Any]:
        self.scope  # contract bound by caller
        connection = _connection(self.temporary / "preflight")
        try:
            full = _calendar(connection, "20160101", "20251231")
            _, start, end = DISCOVERY_ROLE
            calendar = _calendar(connection, start, end)
            events = _rederive_parent_events(connection, self.scope)
            candidates = _apply_candidate_filter(events, self.scope)
            score_keys = load_scores_w2_w6(self.scope, include_values=False).assign(score=True)
            ranked, coverage = _rankable_events(candidates, score_keys, full, calendar)
        finally:
            connection.close()
        self._preflight = {
            "schema_version": "ts-v6-3-pre-effect-key-preflight-v1",
            "protocol_sha256": self.scope.sha256,
            "partition": {
                "rederived_parent_event_count": len(events),
                "candidate_event_count": len(candidates),
                "purged_rankable_candidate_count": len(ranked),
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
            raise V63Error("TS-v6-3 holdout outcomes are forbidden by this protocol")
        if self._preflight is None:
            raise V63Error("TS-v6-3 real values cannot load before key-only preflight")
        _, start, end = DISCOVERY_ROLE
        connection = _connection(self.temporary / partition)
        try:
            full = _calendar(connection, "20160101", "20251231")
            calendar = _calendar(connection, start, end)
            events = _rederive_parent_events(connection, self.scope)
            events = _apply_candidate_filter(events, self.scope)
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
