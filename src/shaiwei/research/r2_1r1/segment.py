"""Pure R2-1R1 core: live-dual day classification, mechanical segments with resets, and the latching gate."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping

from shaiwei.research.r2_1r1.contract import TIMEZONE, Account, Contract, R21R1Error

PAIR_FIELDS = (
    "signal_trade_date",
    "execution_trade_date",
    "signal_sha256",
    "reconciliation_sha256",
    "data_snapshot_sha256",
    "code_snapshot_sha256",
)


@dataclass(frozen=True)
class AccountDay:
    """One account's PASS row for an execution day, with document facts checked by the loader."""

    row: Mapping[str, str]
    mode: str
    policy_version: str
    daily_gate: bool


@dataclass(frozen=True)
class Signal:
    rebalance_due: bool
    on_time: bool


@dataclass(frozen=True)
class DayEvidence:
    date: str
    reasons: tuple[str, ...]
    code_snapshot: str = ""
    rebalance: bool = False
    signal_on_time: bool = True

    @property
    def live(self) -> bool:
        return not self.reasons


@dataclass
class Segment:
    first: str
    code_snapshot: str
    days: list[str] = field(default_factory=list)
    rebalances: list[str] = field(default_factory=list)
    late_signal_days: list[str] = field(default_factory=list)
    latch_day: str | None = None

    @property
    def last(self) -> str:
        return self.days[-1]


def started_local_date(row: Mapping[str, str]) -> str:
    started = datetime.fromisoformat(str(row["started_at"]).replace("Z", "+00:00"))
    if started.tzinfo is None:
        raise R21R1Error("R2-1R1 paper run started_at has no timezone")
    return started.astimezone(TIMEZONE).strftime("%Y%m%d")


def _account_reasons(account: Account, days: list[AccountDay], date: str) -> tuple[list[str], AccountDay | None]:
    if not days:
        return [f"MISSING_{account.role}"], None
    if len(days) != 1:
        return [f"DUPLICATE_{account.role}"], None
    day = days[0]
    reasons = []
    started = started_local_date(day.row)
    if started < date:
        raise R21R1Error(f"R2-1R1 {account.account_id} started before its execution date {date}")
    if started > date:
        reasons.append(f"CONTROLLED_CATCHUP_{account.role}")
    if day.mode != "FORWARD":
        reasons.append(f"NOT_FORWARD_{account.role}")
    if day.row.get("operator") != "docker-scheduler":
        reasons.append(f"OPERATOR_{account.role}")
    if day.row.get("policy_sha256") != account.policy_sha256 or day.policy_version != account.policy_version:
        reasons.append(f"POLICY_IDENTITY_{account.role}")
    if not day.daily_gate:
        reasons.append(f"ACCOUNTING_FRESHNESS_OR_BSE_{account.role}")
    return reasons, day


def classify_day(
    date: str,
    contract: Contract,
    account_days: Mapping[str, list[AccountDay]],
    signals: Mapping[str, Signal],
) -> DayEvidence:
    """A day is live-dual only if every frozen predicate holds; otherwise it is a gap with its reasons."""
    reasons: list[str] = []
    chosen: dict[str, AccountDay] = {}
    for account in contract.accounts:
        found, day = _account_reasons(account, account_days.get(account.role, []), date)
        reasons.extend(found)
        if day is not None:
            chosen[account.role] = day
    if len(chosen) == 2:
        left, right = chosen["control"].row, chosen["comparison"].row
        if any(not left.get(name) or left.get(name) != right.get(name) for name in PAIR_FIELDS):
            reasons.append("PAIR_IDENTITY_MISMATCH")
    if reasons:
        return DayEvidence(date, tuple(sorted(reasons)))
    row = chosen["control"].row
    signal = signals.get(row["signal_sha256"])
    if signal is None:
        raise R21R1Error(f"R2-1R1 live-dual day {date} has no verified shadow signal")
    return DayEvidence(date, (), str(row["code_snapshot_sha256"]), signal.rebalance_due, signal.on_time)


def build_segments(days: list[DayEvidence], contract: Contract) -> list[Segment]:
    """Mechanical segments: any gap closes the segment; a code-snapshot change starts a new one."""
    segments: list[Segment] = []
    current: Segment | None = None
    for day in days:
        if not day.live:
            current = None
            continue
        if current is None or day.code_snapshot != current.code_snapshot:
            current = Segment(first=day.date, code_snapshot=day.code_snapshot)
            segments.append(current)
        current.days.append(day.date)
        if day.rebalance:
            current.rebalances.append(day.date)
        if not day.signal_on_time:
            current.late_signal_days.append(day.date)
        if current.latch_day is None and len(current.days) >= contract.minimum_days and len(current.rebalances) >= contract.minimum_rebalances:
            current.latch_day = day.date
    return segments


def latched_segment(segments: list[Segment]) -> Segment | None:
    return next((segment for segment in segments if segment.latch_day is not None), None)


def _window(segment: Segment) -> list[str]:
    return [day for day in segment.days if segment.latch_day is None or day <= segment.latch_day]


def progress(days: list[DayEvidence], contract: Contract, *, as_of: str, next_open: str | None) -> dict[str, Any]:
    """Counts only: no NAV, return, fee or position value is ever part of the progress output."""
    segments = build_segments(days, contract)
    latched = latched_segment(segments)
    current = segments[-1] if segments and days and days[-1].live and segments[-1].last == days[-1].date else None
    gaps = [{"date": day.date, "reasons": list(day.reasons)} for day in days if not day.live]
    if latched is None:
        state = "NOT_DUE"
    else:
        window = _window(latched)
        state = "OBSERVED_WITH_EXECUTION_WARN" if any(day in window for day in latched.late_signal_days) else "CHECKPOINT_OBSERVED"

    def summary(segment: Segment) -> dict[str, Any]:
        return {"first": segment.first, "last": segment.last, "live_dual_days": len(segment.days),
                "rebalance_cycles": len(segment.rebalances), "code_snapshot": segment.code_snapshot[:12],
                "latch_day": segment.latch_day}

    return {
        "schema_version": "r2-1r1-progress-v1",
        "protocol_sha256": contract.sha256,
        "as_of": as_of,
        "terminal_state": state,
        "official_open_days": len(days),
        "live_dual_days": sum(day.live for day in days),
        "gap_days": gaps,
        "reset_count": sum(1 for index, day in enumerate(days) if not day.live and (index == 0 or days[index - 1].live)),
        "segments": [summary(segment) for segment in segments],
        "current_segment": summary(current) if current else None,
        "latched_segment": summary(latched) if latched else None,
        "gate": {"minimum_segment_live_dual_days": contract.minimum_days, "minimum_segment_rebalance_cycles": contract.minimum_rebalances},
        "next_official_open_day": next_open,
        "contains_nav_or_return": False,
    }
