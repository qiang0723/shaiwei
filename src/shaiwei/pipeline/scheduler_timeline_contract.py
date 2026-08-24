"""Frozen contract types and loader for scheduler phase timelines."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

from shaiwei.config import PROJECT_ROOT

CONTRACT_PATH = PROJECT_ROOT / "config" / "r2_1r0_scheduler_timeline_v1.yaml"


class TimelineError(RuntimeError):
    """Raised when scheduler timing evidence cannot be trusted or persisted."""


@dataclass(frozen=True)
class PhaseRule:
    warn_after_seconds: float
    account_required: bool


@dataclass(frozen=True)
class TimelineContract:
    event_schema_version: str
    timezone: str
    directory: str
    filename_pattern: str
    phases: dict[str, PhaseRule]
    accounts: frozenset[str]
    event_kinds: frozenset[str]
    phase_statuses: frozenset[str]
    notification_statuses: frozenset[str]
    phase_outcomes: frozenset[str]
    cycle_outcomes: frozenset[str]


def _require_mapping(value: object, name: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise TimelineError(f"{name} must be a mapping")
    return value


def _require_string(value: object, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise TimelineError(f"{name} must be a non-empty string")
    return value


def _string_set(value: object, name: str) -> frozenset[str]:
    if not isinstance(value, list) or not value or any(not isinstance(item, str) for item in value):
        raise TimelineError(f"{name} must be a non-empty string list")
    result = frozenset(value)
    if len(result) != len(value):
        raise TimelineError(f"{name} contains duplicates")
    return result


def load_timeline_contract(path: Path = CONTRACT_PATH) -> TimelineContract:
    """Load and strictly validate the frozen R2-1R0 timeline contract."""
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise TimelineError("scheduler timeline contract is unreadable") from error
    root = _require_mapping(document, "contract")
    storage = _require_mapping(root.get("storage"), "storage")
    if storage.get("directory") != "logs/scheduler":
        raise TimelineError("timeline storage directory differs from frozen contract")
    if storage.get("filename_pattern") != "timeline_{cycle_started_local_date}.jsonl":
        raise TimelineError("timeline filename pattern differs from frozen contract")
    for flag in (
        "append_only",
        "exclusive_file_lock",
        "fsync_each_event",
        "sha256_chain",
        "cross_midnight_cycle_stays_in_start_file",
    ):
        if storage.get(flag) is not True:
            raise TimelineError(f"timeline storage invariant disabled: {flag}")

    phase_document = _require_mapping(root.get("phases"), "phases")
    phases: dict[str, PhaseRule] = {}
    for phase, raw_rule in phase_document.items():
        if not isinstance(phase, str):
            raise TimelineError("phase names must be strings")
        rule = _require_mapping(raw_rule, f"phase {phase}")
        if set(rule) != {"warn_after_seconds", "account_required"}:
            raise TimelineError(f"phase {phase} has unexpected fields")
        budget = rule["warn_after_seconds"]
        if not isinstance(budget, (int, float)) or isinstance(budget, bool) or budget <= 0:
            raise TimelineError(f"phase {phase} budget must be positive")
        if not isinstance(rule["account_required"], bool):
            raise TimelineError(f"phase {phase} account_required must be boolean")
        phases[phase] = PhaseRule(float(budget), rule["account_required"])

    expected_phases = {
        "CYCLE",
        "DAILY",
        "READINESS_PROBE",
        "DAILY_COLLECTION",
        "SHADOW",
        "PAPER",
        "PAPER_EXECUTE",
        "PAPER_VERIFY",
        "PAPER_ACCEPTANCE",
    }
    if set(phases) != expected_phases:
        raise TimelineError("timeline phase inventory differs from frozen contract")
    expected_rules = {
        "CYCLE": PhaseRule(7200.0, False),
        "DAILY": PhaseRule(2700.0, False),
        "READINESS_PROBE": PhaseRule(1200.0, False),
        "DAILY_COLLECTION": PhaseRule(1800.0, False),
        "SHADOW": PhaseRule(3600.0, False),
        "PAPER": PhaseRule(1800.0, False),
        "PAPER_EXECUTE": PhaseRule(300.0, True),
        "PAPER_VERIFY": PhaseRule(300.0, True),
        "PAPER_ACCEPTANCE": PhaseRule(300.0, True),
    }
    if phases != expected_rules:
        raise TimelineError("phase budgets or account rules differ from frozen contract")
    events = _require_mapping(root.get("events"), "events")
    behavior = _require_mapping(root.get("behavior"), "behavior")
    if behavior.get("hard_timeout_or_kill_authorized") is not False:
        raise TimelineError("R2-1R0 must not authorize hard timeouts")
    if root.get("contract_id") != "r2-1r0-scheduler-continuity-engineering-v1":
        raise TimelineError("contract_id differs from frozen contract")
    if root.get("status") != "FROZEN_ENGINEERING_ONLY":
        raise TimelineError("timeline contract status is not frozen")

    contract = TimelineContract(
        event_schema_version=_require_string(
            root.get("event_schema_version"), "event_schema_version"
        ),
        timezone=_require_string(root.get("timezone"), "timezone"),
        directory=str(storage["directory"]),
        filename_pattern=str(storage["filename_pattern"]),
        phases=phases,
        accounts=_string_set(root.get("accounts"), "accounts"),
        event_kinds=_string_set(events.get("event_kinds"), "event_kinds"),
        phase_statuses=_string_set(events.get("phase_statuses"), "phase_statuses"),
        notification_statuses=_string_set(
            events.get("notification_statuses"), "notification_statuses"
        ),
        phase_outcomes=_string_set(events.get("phase_outcomes"), "phase_outcomes"),
        cycle_outcomes=_string_set(events.get("cycle_outcomes"), "cycle_outcomes"),
    )
    expected_enums = {
        "accounts": frozenset({"model_baseline", "model_top20"}),
        "event_kinds": frozenset({"PHASE", "DURATION_WARNING_NOTIFICATION"}),
        "phase_statuses": frozenset(
            {"STARTED", "COMPLETED", "COMPLETED_WITH_WARN", "FAILED"}
        ),
        "notification_statuses": frozenset({"PASS", "FAIL", "DISABLED"}),
        "phase_outcomes": frozenset(
            {"READY", "NOT_READY", "PASS", "NOOP", "WAITING_SOURCE"}
        ),
        "cycle_outcomes": frozenset(
            {"PASS", "NOOP", "WAITING_SOURCE", "WAITING_LOCK", "FAILED", "STOPPED"}
        ),
    }
    for field, expected in expected_enums.items():
        if getattr(contract, field) != expected:
            raise TimelineError(f"{field} differs from frozen contract")
    if contract.event_schema_version != "shaiwei-scheduler-phase-event-v1":
        raise TimelineError("event schema version differs from frozen contract")
    if contract.timezone != "Asia/Shanghai":
        raise TimelineError("timezone differs from frozen contract")
    try:
        ZoneInfo(contract.timezone)
    except Exception as error:
        raise TimelineError("timeline timezone is invalid") from error
    return contract
