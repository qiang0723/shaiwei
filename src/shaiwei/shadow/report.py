"""Auditable forward-shadow operating metrics from append-only ledgers."""

from __future__ import annotations

import csv
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from shaiwei.config import PROJECT_ROOT, Settings
from shaiwei.ledger import DAILY_RUNS, SHADOW_RECONCILIATIONS, SHADOW_RUNS


def _rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _latest_by(rows: list[dict[str, str]], fields: tuple[str, ...]) -> dict[tuple[str, ...], dict[str, str]]:
    latest: dict[tuple[str, ...], dict[str, str]] = {}
    for row in sorted(rows, key=lambda value: value.get("finished_at", "")):
        latest[tuple(row[field] for field in fields)] = row
    return latest


def _recovery_count(rows: list[dict[str, str]], fields: tuple[str, ...]) -> int:
    outcomes: dict[tuple[str, ...], list[str]] = {}
    for row in sorted(rows, key=lambda value: value.get("finished_at", "")):
        outcomes.setdefault(tuple(row[field] for field in fields), []).append(row["status"])
    return sum("FAIL" in statuses and statuses[-1] == "PASS" for statuses in outcomes.values())


def build_forward_report(
    settings: Settings,
    *,
    daily_path: Path = DAILY_RUNS,
    shadow_path: Path = SHADOW_RUNS,
    reconciliation_path: Path = SHADOW_RECONCILIATIONS,
) -> dict[str, object]:
    daily_rows = _rows(daily_path)
    shadow_rows = _rows(shadow_path)
    reconciliation_rows = _rows(reconciliation_path)
    latest_signals = _latest_by(shadow_rows, ("signal_trade_date",))
    latest_reconciliations = _latest_by(
        reconciliation_rows,
        ("signal_trade_date", "execution_trade_date"),
    )
    passed_signals = [row for row in latest_signals.values() if row["status"] == "PASS"]
    passed_reconciliations = [
        row for row in latest_reconciliations.values() if row["status"] == "PASS"
    ]
    trade_count = sum(int(row["trade_count"]) for row in passed_reconciliations)
    executable_count = sum(int(row["executable_count"]) for row in passed_reconciliations)
    on_time_count = sum(row["on_time"].lower() == "true" for row in passed_signals)
    mean = lambda field: (  # noqa: E731 - compact audited aggregation
        sum(float(row[field]) for row in passed_reconciliations) / len(passed_reconciliations)
        if passed_reconciliations
        else 0.0
    )

    passed_daily_dates = sorted(
        {
            row["target_trade_date"]
            for row in daily_rows
            if row.get("status") == "PASS"
        }
    )
    reconciled_execution_dates = {
        row["execution_trade_date"] for row in passed_reconciliations
    }
    required_dates = passed_daily_dates[-settings.shadow_pipeline.trial_trade_days :]
    trial_ready = (
        len(required_dates) == settings.shadow_pipeline.trial_trade_days
        and set(required_dates) <= reconciled_execution_dates
    )
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "trial_trade_days_required": settings.shadow_pipeline.trial_trade_days,
        "trial_ready": trial_ready,
        "signal_count": len(passed_signals),
        "reconciled_trade_days": len(passed_reconciliations),
        "on_time_signal_rate": on_time_count / len(passed_signals) if passed_signals else 0.0,
        "trade_executable_rate": executable_count / trade_count if trade_count else 0.0,
        "average_turnover": mean("turnover"),
        "average_mean_abs_open_deviation": mean("mean_abs_open_deviation"),
        "average_estimated_cost": mean("estimated_cost"),
        "failure_count": sum(row.get("status") == "FAIL" for row in shadow_rows + reconciliation_rows),
        "recovery_count": _recovery_count(shadow_rows, ("signal_trade_date",))
        + _recovery_count(
            reconciliation_rows,
            ("signal_trade_date", "execution_trade_date"),
        ),
        "latest_signal_trade_date": max(
            (row["signal_trade_date"] for row in passed_signals),
            default="",
        ),
        "latest_execution_trade_date": max(
            (row["execution_trade_date"] for row in passed_reconciliations),
            default="",
        ),
    }


def write_forward_report(settings: Settings, *, path: Path | None = None) -> Path:
    output = path or PROJECT_ROOT / "logs" / "shadow" / "forward_report.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(
        json.dumps(build_forward_report(settings), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with temporary.open("rb") as handle:
        os.fsync(handle.fileno())
    os.replace(temporary, output)
    return output
