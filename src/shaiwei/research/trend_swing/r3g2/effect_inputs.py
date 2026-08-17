"""Strict frozen-input adapter and discovery/holdout value firewall for R3G-2."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import math
from typing import Any

import duckdb
import pandas as pd

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.trend_swing.r3g2.contract import EffectProtocol, R3G2Error, sha256_file
from shaiwei.research.trend_swing.r4_contract import load_r3_manifest
from shaiwei.research.trend_swing.recovery_market import prepare_market_and_sector
from shaiwei.research.trend_swing.recovery_store import configure_store, prepare_core_tables
from shaiwei.research.trend_swing.v5_r3g1_contract import R3G1Scope
from shaiwei.research.trend_swing.v5_r3g1_features import prepare_r3g1_features
from shaiwei.research.trend_swing.v5_r3g1_runner import (
    load_role_rows,
    project_effect_events,
)
from shaiwei.research.trend_swing.v5_r3g_contract import R3GScope, registered_candidates


RELEASE_PROTOCOL_PATH = PROJECT_ROOT / "config/ts_v5_r3g2_effect_release_v1.yaml"
W7_PREDICTION = PROJECT_ROOT / (
    "data/research/trend_swing/ts-v5-r3g2-w7-lineage-recovery/first_pass/predictions.parquet"
)


@dataclass(frozen=True)
class PreparedPartition:
    events: pd.DataFrame
    bars: pd.DataFrame
    benchmark: pd.DataFrame
    calendar: tuple[str, ...]


def _release_document() -> dict[str, Any]:
    import yaml

    document = yaml.safe_load(RELEASE_PROTOCOL_PATH.read_text(encoding="utf-8"))
    if document.get("status") != "RESULT_BLIND_EFFECT_ENGINEERING_AND_RELEASE_PREPARATION_ONLY":
        raise R3G2Error("R3G-2 release protocol status differs")
    for row in document["predecessors"].values():
        if not isinstance(row, dict) or not {"path", "sha256"} <= set(row):
            continue
        path = PROJECT_ROOT / row["path"]
        if not path.is_file() or sha256_file(path) != row["sha256"]:
            raise R3G2Error(f"R3G-2 release predecessor differs: {path.name}")
    return document


def _score_paths(protocol: EffectProtocol) -> tuple[Path, ...]:
    reusable = protocol.document["ranking_lineage"]["clean_m6_lineage"]["reusable_predictions"]
    return tuple(PROJECT_ROOT / reusable[name]["path"] for name in ("W2", "W3", "W4", "W5", "W6")) + (
        W7_PREDICTION,
    )


def _normalize_prediction(frame: pd.DataFrame, *, include_values: bool) -> pd.DataFrame:
    required = {"datetime", "instrument"} | ({"score"} if include_values else set())
    if required - set(frame.columns):
        raise R3G2Error("R3G-2 score artifact schema differs")
    columns = ["datetime", "instrument"] + (["score"] if include_values else [])
    result = frame[columns].copy()
    result["score_date"] = pd.to_datetime(result.pop("datetime"), errors="raise").dt.strftime("%Y%m%d")
    result["ts_code"] = result.pop("instrument").astype(str).map(_tushare_code)
    if include_values:
        result["score"] = pd.to_numeric(result["score"], errors="raise").astype(float)
        if not result["score"].map(math.isfinite).all():
            raise R3G2Error("R3G-2 score values are nonfinite")
    if result.duplicated(["score_date", "ts_code"]).any():
        raise R3G2Error("R3G-2 score keys are duplicated within an artifact")
    return result


def _tushare_code(value: str) -> str:
    match = re.fullmatch(r"(SH|SZ)(\d{6})", value.strip().upper())
    if match is not None:
        return f"{match.group(2)}.{match.group(1)}"
    if re.fullmatch(r"\d{6}\.(SH|SZ)", value.strip().upper()) is not None:
        return value.strip().upper()
    raise R3G2Error("R3G-2 score instrument code format differs")


def load_scores(protocol: EffectProtocol, *, include_values: bool) -> pd.DataFrame:
    columns = ["datetime", "instrument"] + (["score"] if include_values else [])
    frames = [
        _normalize_prediction(pd.read_parquet(path, columns=columns), include_values=include_values)
        for path in _score_paths(protocol)
    ]
    result = pd.concat(frames, ignore_index=True).sort_values(["score_date", "ts_code"])
    if result.duplicated(["score_date", "ts_code"]).any():
        raise R3G2Error("R3G-2 W2-W7 score keys overlap")
    if include_values:
        if not result["score"].map(math.isfinite).all():
            raise R3G2Error("R3G-2 score values are nonfinite")
    return result


def _connection(temporary: Path) -> duckdb.DuckDBPyConnection:
    scope = R3G1Scope.load()
    manifest = load_r3_manifest(
        PROJECT_ROOT / scope.document["frozen_inputs"]["r3_manifest_path"]
    )
    connection = duckdb.connect(":memory:")
    configure_store(connection, temporary)
    context = scope.document["frozen_inputs"]["source_context"]
    prepare_core_tables(
        connection, manifest, start_date=str(context["start"]), end_date=str(context["end"])
    )
    prepare_market_and_sector(connection)
    prepare_r3g1_features(connection)
    return connection


def _candidate() -> Any:
    candidates = registered_candidates(R3GScope.load())
    found = [row for row in candidates if row.candidate.primary_mechanism.value == "BREAKOUT_RETEST"]
    if len(found) != 1:
        raise R3G2Error("R3G-2 BREAKOUT_RETEST registry identity differs")
    return found[0]


def _role(partition: str) -> tuple[str, str, str]:
    values = {
        "discovery": ("selectable_discovery", "20210104", "20231229"),
        "holdout": ("frozen_stability_holdout", "20240102", "20251231"),
    }
    try:
        return values[partition]
    except KeyError as error:
        raise R3G2Error(f"R3G-2 partition is invalid: {partition}") from error


def _bound_events(protocol: EffectProtocol, role: str) -> pd.DataFrame:
    source = PROJECT_ROOT / protocol.document["predecessors"]["r3g1_events"]["path"]
    frame = pd.read_parquet(source)
    selected = set(protocol.selected_point_hashes)
    frame = frame.loc[frame["role"].eq(role) & frame["point_hash"].isin(selected)].copy()
    frame = frame.rename(columns={"next_open_date": "execution_date"})
    keys = ["point_hash", "ts_code", "signal_date", "execution_date"]
    if frame.empty or frame.duplicated(keys).any() or frame["ts_code"].str.endswith(".BJ").any():
        raise R3G2Error("R3G-2 bound event keys are empty, duplicated, or contain BSE")
    return frame[keys].sort_values(keys).reset_index(drop=True)


def _rederive_events(
    connection: duckdb.DuckDBPyConnection, protocol: EffectProtocol, partition: str
) -> pd.DataFrame:
    role, start, end = _role(partition)
    rows = load_role_rows(connection, start, end)
    registered = _candidate()
    points = [protocol.document["selected_effect_points"]["primary_anchor"]]
    points.extend(protocol.document["selected_effect_points"]["sensitivity_neighbours"])
    events: list[dict[str, Any]] = []
    for point in points:
        values = {key: str(value) for key, value in point["parameters"].items()}
        events.extend(project_effect_events(rows, registered, values, role))
    frame = pd.DataFrame(events).rename(columns={"next_open_date": "execution_date"})
    keys = ["point_hash", "ts_code", "signal_date", "execution_date"]
    if frame.empty or frame.duplicated(keys).any() or frame["ts_code"].str.endswith(".BJ").any():
        raise R3G2Error("R3G-2 rederived event keys are empty, duplicated, or contain BSE")
    bound = _bound_events(protocol, role)
    if not frame[keys].sort_values(keys).reset_index(drop=True).equals(bound):
        raise R3G2Error("R3G-2 rederived event keys differ from R3G-1")
    return frame.sort_values(keys).reset_index(drop=True)


def _calendar(connection: duckdb.DuckDBPyConnection, start: str, end: str) -> tuple[str, ...]:
    rows = connection.execute(
        "SELECT trade_date FROM open_days WHERE trade_date BETWEEN ? AND ? ORDER BY trade_date",
        [start, end],
    ).fetchall()
    result = tuple(str(row[0]) for row in rows)
    if not result:
        raise R3G2Error("R3G-2 partition calendar is empty")
    return result


def _score_date(signal_date: str, calendar: tuple[str, ...]) -> str:
    signal = pd.Timestamp(signal_date)
    monday = signal - pd.Timedelta(days=signal.weekday())
    boundary = monday.strftime("%Y%m%d")
    eligible = [day for day in calendar if day < boundary]
    if not eligible:
        raise R3G2Error("R3G-2 prior-week score observation is unavailable")
    return eligible[-1]


def _rankable_events(
    frame: pd.DataFrame,
    scores: pd.DataFrame,
    full_calendar: tuple[str, ...],
    partition_calendar: tuple[str, ...],
) -> tuple[pd.DataFrame, dict[str, float]]:
    indexes = {day: index for index, day in enumerate(partition_calendar)}
    keep = []
    for row in frame.itertuples(index=False):
        execution_index = indexes.get(str(row.execution_date))
        keep.append(execution_index is not None and execution_index + 15 < len(partition_calendar))
    frame = frame.loc[keep].copy()
    frame["score_date"] = frame["signal_date"].map(lambda value: _score_date(str(value), full_calendar))
    merged = frame.merge(scores, on=["score_date", "ts_code"], how="left", validate="many_to_one")
    coverage = {
        point: float(rows["score" if "score" in rows else "score_date"].notna().mean())
        for point, rows in merged.groupby("point_hash", sort=True)
    }
    if set(coverage) != set(frame["point_hash"]) or min(coverage.values(), default=0.0) < 0.95:
        raise R3G2Error("R3G-2 event-key score coverage is below 95 percent")
    if "score" in merged:
        merged = merged.loc[merged["score"].notna()].copy()
        merged["signal_rank"] = merged.groupby(["point_hash", "execution_date"])["score"].rank(
            method="first", ascending=False
        )
        merged = merged.sort_values(
            ["point_hash", "execution_date", "score", "ts_code"],
            ascending=[True, True, False, True],
        )
        merged["signal_rank"] = merged.groupby(["point_hash", "execution_date"]).cumcount() + 1
    return merged, coverage


def _bars(
    connection: duckdb.DuckDBPyConnection,
    codes: list[str],
    start: str,
    end: str,
) -> pd.DataFrame:
    connection.register("effect_codes", pd.DataFrame({"ts_code": sorted(set(codes))}))
    query = """
        WITH enriched AS (
          SELECT p.*,
            p.adj_open/p.adj_factor AS raw_open,
            p.adj_high/p.adj_factor AS raw_high,
            p.adj_low/p.adj_factor AS raw_low,
            p.adj_close/p.adj_factor AS raw_close,
            lag(p.adj_close/p.adj_factor) OVER(PARTITION BY p.ts_code ORDER BY p.trade_date)
              AS prior_raw_close,
            median(p.amount_rmb) OVER(PARTITION BY p.ts_code ORDER BY p.trade_date
              ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING) AS amount_median20_rmb,
            count(*) OVER(PARTITION BY p.ts_code ORDER BY p.trade_date
              ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING) AS amount_history_count
          FROM all_price_bars p JOIN effect_codes c USING(ts_code)
        ), weekly AS (
          SELECT e.*,w.week_low AS latest_complete_week_low
          FROM enriched e ASOF LEFT JOIN r4_stock_week w
            ON e.ts_code=w.ts_code AND e.trade_date>w.week_end
        )
        SELECT w.*,coalesce(m.ts_code IS NOT NULL,false) AS security_eligible,
          coalesce(i.industry,'') AS industry,
          w.market_rank-o.market_rank+1 AS listing_session_age
        FROM weekly w
        LEFT JOIN member_bars m USING(ts_code,trade_date)
        LEFT JOIN industry_hits i USING(ts_code,trade_date)
        LEFT JOIN lifecycle l USING(ts_code)
        LEFT JOIN open_days o ON o.trade_date=(
          SELECT min(x.trade_date) FROM open_days x WHERE x.trade_date>=l.list_date)
        WHERE w.trade_date BETWEEN ? AND ? AND w.amount_history_count>=20
        ORDER BY w.trade_date,w.ts_code
    """
    frame = connection.execute(query, [start, end]).fetchdf()
    connection.unregister("effect_codes")
    if frame.empty:
        raise R3G2Error("R3G-2 execution bars are empty")
    return frame


def _benchmark(protocol: EffectProtocol, calendar: tuple[str, ...]) -> pd.DataFrame:
    path = PROJECT_ROOT / protocol.document["benchmark"]["path"]
    frame = pd.read_parquet(path, columns=["trade_date", "close"])
    frame["trade_date"] = frame["trade_date"].astype(str)
    frame = frame.sort_values("trade_date")
    frame["benchmark_return"] = pd.to_numeric(frame["close"], errors="raise").pct_change()
    result = frame.loc[frame["trade_date"].isin(calendar), ["trade_date", "benchmark_return"]]
    if len(result) != len(calendar) or result["benchmark_return"].isna().any():
        raise R3G2Error("R3G-2 H00906 benchmark coverage differs")
    return result.reset_index(drop=True)


class RealInputAdapter:
    """Build each partition only when its value firewall grants access."""

    def __init__(self, protocol: EffectProtocol, temporary: Path) -> None:
        self.protocol = protocol
        self.temporary = temporary
        self._preflight: dict[str, Any] | None = None

    def preflight(self) -> dict[str, Any]:
        self.protocol.validate_authorized_effect_inputs()
        _release_document()
        connection = _connection(self.temporary / "preflight")
        try:
            full = _calendar(connection, "20160101", "20251231")
            score_keys = load_scores(self.protocol, include_values=False)
            partitions: dict[str, Any] = {}
            for name in ("discovery", "holdout"):
                _, start, end = _role(name)
                calendar = _calendar(connection, start, end)
                events = _rederive_events(connection, self.protocol, name)
                keys = score_keys.assign(score=True)
                ranked, coverage = _rankable_events(events, keys, full, calendar)
                partitions[name] = {
                    "rederived_event_count": len(events),
                    "purged_rankable_event_count": len(ranked),
                    "score_key_coverage": coverage,
                    "calendar_day_count": len(calendar),
                }
        finally:
            connection.close()
        self._preflight = {
            "schema_version": "ts-v5-r3g2-pre-effect-key-preflight-v1",
            "protocol_sha256": self.protocol.sha256,
            "release_protocol_sha256": sha256_file(RELEASE_PROTOCOL_PATH),
            "partitions": partitions,
            "score_values_read": False,
            "post_entry_outcomes_read": False,
            "benchmark_values_read": False,
            "strategy_effect_attempt_count": 0,
            "verdict": "GO_PRE_EFFECT_KEYS_ONLY",
        }
        return self._preflight

    def load_partition(self, partition: str) -> PreparedPartition:
        if self._preflight is None:
            raise R3G2Error("R3G-2 real values cannot load before key-only preflight")
        _, start, end = _role(partition)
        connection = _connection(self.temporary / partition)
        try:
            full = _calendar(connection, "20160101", "20251231")
            calendar = _calendar(connection, start, end)
            events = _rederive_events(connection, self.protocol, partition)
            events, _ = _rankable_events(
                events, load_scores(self.protocol, include_values=True), full, calendar
            )
            bars = _bars(connection, events["ts_code"].astype(str).tolist(), start, end)
        finally:
            connection.close()
        return PreparedPartition(
            events=events,
            bars=bars,
            benchmark=_benchmark(self.protocol, calendar),
            calendar=calendar,
        )
