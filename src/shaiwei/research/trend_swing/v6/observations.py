"""Reconstruct frozen parent events and capture result-blind entry observations."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping, Sequence

import duckdb

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.provider_contract import D1ControlError
from shaiwei.research.trend_swing.v5_r3g1_features import prepare_r3g1_features
from shaiwei.research.trend_swing.v5_r3g1_inputs import daily_input, next_open_input
from shaiwei.research.trend_swing.v5_r3g_contract import R3GScope, RegisteredCandidate, registered_candidates
from shaiwei.research.trend_swing.v5_r3g_state import (
    Episode,
    EpisodeStatus,
    advance_without_security_bar,
    execute_next_open,
    transition,
)
from shaiwei.research.trend_swing.v6.contract import V6Scope


PARENT_POINT = {
    "BREAKOUT_LOOKBACK_WEEKS": "4",
    "MAXIMUM_WAIT_DAYS": "10",
    "RECOVERY_CONFIRMATION_DAYS": "1",
    "RETEST_TOLERANCE_ATR": "1.5",
}
PARENT_POINT_HASH = "81833a47b1edb59455c997c422bb36b63454f1da84e29696269c9c950e019784"


def parent_candidate() -> RegisteredCandidate:
    matches = [
        item for item in registered_candidates(R3GScope.load())
        if item.candidate.primary_mechanism.value == "BREAKOUT_RETEST"
    ]
    if len(matches) != 1 or PARENT_POINT not in matches[0].grid:
        raise D1ControlError("TS-v6 frozen parent candidate or point is unavailable")
    return matches[0]


def prepare_v6_stream(connection: duckdb.DuckDBPyConnection) -> None:
    prepare_r3g1_features(connection)
    connection.execute(
        """
        CREATE TEMP TABLE v6_return_base AS
        SELECT ts_code,trade_date,
          adj_close/lag(adj_close,10) OVER(PARTITION BY ts_code ORDER BY trade_date)-1.0
            AS pre_entry_return_10d
        FROM r3g1_daily_roll
        """
    )
    connection.execute(
        """
        CREATE TEMP TABLE v6_return_rank AS
        SELECT *,percent_rank() OVER(
          PARTITION BY trade_date ORDER BY pre_entry_return_10d
        ) AS pre_entry_10d_return_percentile
        FROM v6_return_base WHERE pre_entry_return_10d IS NOT NULL
        """
    )
    connection.execute(
        """
        CREATE TEMP TABLE v6_stream AS
        SELECT s.*,r.pre_entry_return_10d,r.pre_entry_10d_return_percentile
        FROM r3g1_stream s LEFT JOIN v6_return_rank r USING(ts_code,trade_date)
        """
    )


def load_role_rows(
    connection: duckdb.DuckDBPyConnection, start: str, end: str
) -> tuple[dict[str, Any], ...]:
    result = connection.execute(
        """
        SELECT *,market_rank-min(market_rank) OVER()+1 AS role_sequence
        FROM v6_stream WHERE trade_date BETWEEN ? AND ? ORDER BY ts_code,trade_date
        """,
        [start, end],
    )
    columns = [item[0] for item in result.description]
    return tuple(dict(zip(columns, values, strict=True)) for values in result.fetchall())


def _decimal(value: Any, label: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (TypeError, ValueError) as exc:
        raise D1ControlError(f"TS-v6 {label} is invalid") from exc
    if not result.is_finite():
        raise D1ControlError(f"TS-v6 {label} is non-finite")
    return result


def _observation(
    role: str,
    code: str,
    armed: Mapping[str, Any],
    signal: Mapping[str, Any],
    next_open: Mapping[str, Any],
) -> dict[str, Any]:
    amount, median = _decimal(armed["amount_rmb"], "retest amount"), _decimal(
        armed["amount_median20_lagged"], "prior amount median"
    )
    high, low, close = (
        _decimal(signal["adj_high"], "signal high"),
        _decimal(signal["adj_low"], "signal low"),
        _decimal(signal["adj_close"], "signal close"),
    )
    percentile = _decimal(
        signal["pre_entry_10d_return_percentile"], "10-day return percentile"
    )
    if (
        amount < 0
        or median <= 0
        or high <= low
        or not low <= close <= high
        or not Decimal("0") <= percentile <= Decimal("1")
    ):
        raise D1ControlError("TS-v6 result-blind observation violates feature invariants")
    return {
        "role": role,
        "point_hash": PARENT_POINT_HASH,
        "ts_code": code,
        "signal_date": str(signal["trade_date"]),
        "next_open_date": str(next_open["trade_date"]),
        "pullback_amount_ratio": float(amount / median),
        "recovery_close_location": float((close - low) / (high - low)),
        "pre_entry_10d_return_percentile": float(percentile),
    }


def project_parent_observations(
    rows: Sequence[Mapping[str, Any]], registered: RegisteredCandidate, role: str
) -> list[dict[str, Any]]:
    observations: list[dict[str, Any]] = []
    active_code, episode, armed, signal = "", Episode(), None, None
    for original in rows:
        row = dict(original)
        code = str(row["ts_code"])
        if code != active_code:
            active_code, episode, armed, signal = code, Episode(), None, None
        if episode.status == EpisodeStatus.CONFIRMED:
            if bool(row["has_bar"]):
                row["same_adjustment_factor"] = Decimal(str(row["adj_factor"])) == Decimal(
                    str(signal["adj_factor"])
                )
                try:
                    terminal = execute_next_open(
                        registered.candidate,
                        episode,
                        next_open_input(registered.candidate, PARENT_POINT, signal, row),
                    )
                except (D1ControlError, TypeError, ValueError, ArithmeticError):
                    terminal = Episode(status=EpisodeStatus.CANCELLED)
                if terminal.status == EpisodeStatus.EXECUTED:
                    if armed is None or signal is None:
                        raise D1ControlError("TS-v6 parent episode observation is incomplete")
                    observations.append(_observation(role, code, armed, signal, row))
            episode, armed, signal = Episode(), None, None
        if not bool(row["has_bar"]):
            if episode.status == EpisodeStatus.ARMED:
                episode = advance_without_security_bar(
                    registered.candidate,
                    PARENT_POINT,
                    episode,
                    sequence=int(row["role_sequence"]),
                    market_sector_gate=bool(row["f_daily"]),
                )
                if episode.status == EpisodeStatus.CANCELLED:
                    episode, armed = Episode(), None
            continue
        before = episode.status
        try:
            episode = transition(
                registered.candidate,
                PARENT_POINT,
                episode,
                daily_input(registered.candidate, PARENT_POINT, row),
            )
        except (D1ControlError, TypeError, ValueError, ArithmeticError):
            episode, armed, signal = Episode(), None, None
            continue
        if before == EpisodeStatus.IDLE and episode.status in {
            EpisodeStatus.ARMED,
            EpisodeStatus.CONFIRMED,
        }:
            armed = row
        if episode.status == EpisodeStatus.CONFIRMED:
            signal = row
        elif episode.status == EpisodeStatus.CANCELLED:
            episode, armed = Episode(), None
    return observations


def frozen_parent_keys(scope: V6Scope, root: Path = PROJECT_ROOT) -> dict[str, set[tuple[str, str, str]]]:
    path = root / scope.document["frozen_inputs"]["parent_event_path"]
    connection = duckdb.connect(":memory:")
    try:
        result = connection.execute(
            """
            SELECT role,ts_code,signal_date,next_open_date
            FROM read_parquet(?) WHERE point_hash=? AND role IN (?,?)
            ORDER BY role,ts_code,signal_date,next_open_date
            """,
            [str(path), PARENT_POINT_HASH, "selectable_discovery", "frozen_stability_holdout"],
        ).fetchall()
    finally:
        connection.close()
    keys = {"selectable_discovery": set(), "frozen_stability_holdout": set()}
    for role, code, signal_date, next_open_date in result:
        if str(code).endswith(".BJ"):
            raise D1ControlError("TS-v6 frozen parent event contains .BJ")
        key = (str(code), str(signal_date), str(next_open_date))
        if key in keys[str(role)]:
            raise D1ControlError("TS-v6 frozen parent event key is duplicated")
        keys[str(role)].add(key)
    return keys


def reconcile_parent_keys(
    observations: Sequence[Mapping[str, Any]], expected: Mapping[str, set[tuple[str, str, str]]]
) -> None:
    actual = {role: set() for role in expected}
    for row in observations:
        role = str(row["role"])
        key = (str(row["ts_code"]), str(row["signal_date"]), str(row["next_open_date"]))
        if role not in actual or key in actual[role] or key[0].endswith(".BJ"):
            raise D1ControlError("TS-v6 reconstructed parent event key is invalid")
        actual[role].add(key)
    if actual != expected:
        summary = {role: (len(actual[role]), len(expected[role])) for role in expected}
        raise D1ControlError(f"TS-v6 reconstructed parent keys differ: {summary}")
