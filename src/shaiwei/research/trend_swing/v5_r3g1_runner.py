"""Deterministic event projection for TS-v5-R3G-1."""

from __future__ import annotations

from decimal import Decimal
import hashlib
import json
from typing import Any, Mapping, Sequence

import duckdb

from shaiwei.research.provider_contract import D1ControlError
from shaiwei.research.trend_swing.v5_r3g1_inputs import daily_input, next_open_input
from shaiwei.research.trend_swing.v5_r3g_contract import RegisteredCandidate
from shaiwei.research.trend_swing.v5_r3g_state import (
    Episode,
    EpisodeStatus,
    advance_without_security_bar,
    execute_next_open,
    transition,
)


def load_role_rows(
    connection: duckdb.DuckDBPyConnection,
    start: str,
    end: str,
) -> tuple[dict[str, Any], ...]:
    result = connection.execute(
        """
        SELECT *,market_rank-min(market_rank) OVER()+1 AS role_sequence
        FROM r3g1_stream WHERE trade_date BETWEEN ? AND ? ORDER BY ts_code,trade_date
        """,
        [start, end],
    )
    columns = [item[0] for item in result.description]
    return tuple(dict(zip(columns, values, strict=True)) for values in result.fetchall())


def project_events(
    rows: Sequence[Mapping[str, Any]],
    registered: RegisteredCandidate,
    point: Mapping[str, str],
    role: str,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    active_code, episode, signal = "", Episode(), None
    point_hash = _point_hash(point)
    for original in rows:
        row = dict(original)
        code = str(row["ts_code"])
        if code != active_code:
            active_code, episode, signal = code, Episode(), None
        if episode.status == EpisodeStatus.CONFIRMED:
            if bool(row["has_bar"]):
                row["same_adjustment_factor"] = Decimal(str(row["adj_factor"])) == Decimal(
                    str(signal["adj_factor"])
                )
                try:
                    terminal = execute_next_open(
                        registered.candidate,
                        episode,
                        next_open_input(registered.candidate, point, signal, row),
                    )
                except (D1ControlError, KeyError, TypeError, ValueError, ArithmeticError):
                    terminal = Episode(status=EpisodeStatus.CANCELLED)
                if terminal.status == EpisodeStatus.EXECUTED:
                    events.append(_event(role, registered, point_hash, code, signal, row))
            episode, signal = Episode(), None
        if not bool(row["has_bar"]):
            if episode.status == EpisodeStatus.ARMED:
                episode = advance_without_security_bar(
                    registered.candidate,
                    point,
                    episode,
                    sequence=int(row["role_sequence"]),
                    market_sector_gate=bool(row["f_daily"]),
                )
                if episode.status == EpisodeStatus.CANCELLED:
                    episode = Episode()
            continue
        try:
            episode = transition(
                registered.candidate,
                point,
                episode,
                daily_input(registered.candidate, point, row),
            )
        except (D1ControlError, KeyError, TypeError, ValueError, ArithmeticError):
            episode = Episode()
            continue
        if episode.status == EpisodeStatus.CONFIRMED:
            signal = row
        elif episode.status == EpisodeStatus.CANCELLED:
            episode = Episode()
    return events


def _event(
    role: str,
    registered: RegisteredCandidate,
    point_hash: str,
    code: str,
    signal: Mapping[str, Any],
    row: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "role": role,
        "candidate_ordinal": registered.ordinal,
        "mechanism": registered.candidate.primary_mechanism.value,
        "point_hash": point_hash,
        "ts_code": code,
        "signal_date": str(signal["trade_date"]),
        "next_open_date": str(row["trade_date"]),
        "event_status": "LEGAL_ENTRY_EVENT",
    }


def _point_hash(point: Mapping[str, str]) -> str:
    encoded = json.dumps(dict(sorted(point.items())), separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()
