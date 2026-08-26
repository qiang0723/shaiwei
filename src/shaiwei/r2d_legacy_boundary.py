"""Fail-closed evidence for the legacy scheduler's pre-cutoff boundary."""

from __future__ import annotations

import csv
from datetime import datetime, time
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import Field

from shaiwei import daily_early_release_guard as base
from shaiwei.ledger import DAILY_RUNS, PAPER_RUNS, SHADOW_RUNS


class LegacyNoopBoundary(base.FrozenModel):
    mode: Literal["PRIOR_DAY_NOOP"]
    status: Literal["noop"]
    detail_trade_date: str = Field(pattern=r"^[0-9]{8}$")
    updated_on_target_date_not_before: time
    require_target_daily_rows: Literal[0]
    require_target_shadow_rows: Literal[0]
    require_target_paper_rows: Literal[0]


def _count_rows(path: Path, field: str, value: str) -> int:
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None or field not in reader.fieldnames:
                raise base.GuardError(f"{path.name} lacks the required {field} field")
            return sum(1 for row in reader if row.get(field) == value)
    except OSError as error:
        raise base.GuardError(f"{path.name} is unreadable") from error


def target_write_counts(
    target_trade_date: str,
    *,
    daily_path: Path = DAILY_RUNS,
    shadow_path: Path = SHADOW_RUNS,
    paper_path: Path = PAPER_RUNS,
) -> dict[str, int]:
    """Count all target-date attempts, including failed or partial attempts."""
    return {
        "daily": _count_rows(daily_path, "target_trade_date", target_trade_date),
        "shadow": _count_rows(shadow_path, "signal_trade_date", target_trade_date),
        "paper": _count_rows(paper_path, "execution_trade_date", target_trade_date),
    }


def validate_noop_boundary(
    boundary: LegacyNoopBoundary,
    *,
    target_trade_date: str,
    timezone: str,
    health: dict[str, object],
    counts: dict[str, int],
) -> dict[str, object]:
    if health.get("status") != boundary.status:
        raise base.GuardError("legacy scheduler health is not the frozen noop state")
    if health.get("detail") != boundary.detail_trade_date:
        raise base.GuardError("legacy noop detail differs from the frozen prior date")
    if boundary.detail_trade_date >= target_trade_date:
        raise base.GuardError("legacy noop detail does not precede the target date")
    try:
        updated = datetime.fromisoformat(str(health.get("updated_at", "")))
    except ValueError as error:
        raise base.GuardError("legacy scheduler health timestamp is invalid") from error
    if updated.tzinfo is None:
        raise base.GuardError("legacy scheduler health timestamp is timezone-naive")
    local = updated.astimezone(ZoneInfo(timezone))
    if (
        local.strftime("%Y%m%d") != target_trade_date
        or local.time().replace(tzinfo=None)
        < boundary.updated_on_target_date_not_before
    ):
        raise base.GuardError("legacy noop evidence is outside the target boundary")
    expected = {
        "daily": boundary.require_target_daily_rows,
        "shadow": boundary.require_target_shadow_rows,
        "paper": boundary.require_target_paper_rows,
    }
    if counts != expected:
        raise base.GuardError("legacy scheduler has already written the target date")
    return {
        "mode": boundary.mode,
        "status": boundary.status,
        "detail": boundary.detail_trade_date,
        "updated_at": updated.isoformat(),
        "target_write_counts": counts,
    }
