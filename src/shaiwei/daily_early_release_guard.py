"""Date-bound, fail-closed production guard for the daily early-readiness release."""

from __future__ import annotations

import argparse
from datetime import date, datetime, time
import json
from pathlib import Path
from typing import Any, Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, model_validator
import yaml

from shaiwei import release
from shaiwei.config import PROJECT_ROOT
from shaiwei.release_guard import GuardEnvironment, SchedulerIdentity


PROTOCOL_PATH = PROJECT_ROOT / "config" / "daily_early_readiness_release_guard_v2.yaml"


class GuardError(RuntimeError):
    """A frozen release precondition or recovery condition failed."""


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ReleaseIdentity(FrozenModel):
    image: str = Field(pattern=r"^shaiwei:scheduler-[0-9a-f]{16}$")
    image_id: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    code_snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    git_head: str = Field(pattern=r"^[0-9a-f]{40}$")


class ForwardIdentity(FrozenModel):
    account_id: Literal["model_baseline", "model_top20"]
    execution_trade_date: str = Field(pattern=r"^[0-9]{8}$")
    code_snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class GuardWindow(FrozenModel):
    not_before: time
    expires_at: time

    @model_validator(mode="after")
    def validate_order(self) -> "GuardWindow":
        if self.not_before >= self.expires_at:
            raise ValueError("release guard window must be increasing")
        return self


class GuardRequirements(FrozenModel):
    clean_worktree: Literal[True]
    head_equals_origin_main: Literal[True]
    release_audit_chain_pass: Literal[True]
    candidate_runtime_identity_exact_match: Literal[True]
    running_release_exact_match: Literal[True]
    both_accounts_latest_forward_exact_match: Literal[True]
    target_is_only_new_trade_date: Literal[True]
    scheduler_healthy_before_promotion: Literal[True]
    promote_and_start_exactly_once: Literal[True]
    failed_start_restores_previous_release: Literal[True]
    run_daily_manually: Literal[False]
    build_candidate: Literal[False]
    mutate_model_signal_or_gate: Literal[False]


class GuardProtocol(FrozenModel):
    schema_version: Literal["daily-early-readiness-release-guard-v1"]
    guard_id: str = Field(pattern=r"^daily-early-readiness-release-guard-[0-9]{8}$")
    timezone: Literal["Asia/Shanghai"]
    target_trade_date: str = Field(pattern=r"^[0-9]{8}$")
    window: GuardWindow
    candidate: ReleaseIdentity
    expected_running_release: ReleaseIdentity
    expected_latest_forward: tuple[ForwardIdentity, ...]
    requirements: GuardRequirements

    @model_validator(mode="after")
    def validate_protocol(self) -> "GuardProtocol":
        if self.guard_id.rsplit("-", 1)[-1] != self.target_trade_date:
            raise ValueError("release guard ID date must equal target_trade_date")
        accounts = [item.account_id for item in self.expected_latest_forward]
        if len(accounts) != 2 or set(accounts) != {"model_baseline", "model_top20"}:
            raise ValueError("release guard must bind exactly the Top30 and Top20 accounts")
        if self.candidate.image_id == self.expected_running_release.image_id:
            raise ValueError("candidate and running release must be distinct")
        return self


class EarlyGuardEnvironment(GuardEnvironment):
    """Narrow host mutations added to the existing targeted release adapter."""

    def promote_and_start(self, image: str) -> dict[str, object]:
        return release.promote(image, start=True)

    def rollback_and_start(self) -> dict[str, object]:
        return release.rollback(start=True)


def load_protocol(path: Path = PROTOCOL_PATH) -> GuardProtocol:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    return GuardProtocol.model_validate(document)


def _identity(document: dict[str, Any] | None) -> dict[str, str]:
    source = document or {}
    return {
        field: str(source.get(field, ""))
        for field in ("image", "image_id", "code_snapshot_sha256", "git_head")
    }


def _running_matches(running: SchedulerIdentity, expected: ReleaseIdentity) -> bool:
    return (
        running.image_id == expected.image_id
        and running.code_snapshot_sha256 == expected.code_snapshot_sha256
        and running.git_head == expected.git_head
    )


def _validate_time(protocol: GuardProtocol, now: datetime) -> str:
    if now.tzinfo is None:
        raise GuardError("guard clock must be timezone-aware")
    local = now.astimezone(ZoneInfo(protocol.timezone))
    target = date.fromisoformat(
        f"{protocol.target_trade_date[:4]}-{protocol.target_trade_date[4:6]}-"
        f"{protocol.target_trade_date[6:]}"
    )
    if local.date() != target:
        raise GuardError("guard target date does not equal the local date")
    clock = local.time().replace(tzinfo=None)
    if clock < protocol.window.not_before:
        raise GuardError("guard window has not opened")
    if clock >= protocol.window.expires_at:
        raise GuardError("guard window has expired")
    return local.isoformat(timespec="seconds")


def _release_state(environment: EarlyGuardEnvironment) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        document = environment.release_status()
    except release.ReleaseError as error:
        raise GuardError(str(error)) from error
    if document.get("status") != "PASS":
        raise GuardError("release audit status is not PASS")
    state = document.get("state")
    if not isinstance(state, dict):
        raise GuardError("release state is missing")
    current = state.get("current")
    previous = state.get("previous")
    if not isinstance(current, dict) or not isinstance(previous, dict):
        raise GuardError("release state lacks current or previous identity")
    return current, previous


def _validate_forwards(protocol: GuardProtocol, environment: EarlyGuardEnvironment) -> None:
    for expected in protocol.expected_latest_forward:
        actual = environment.latest_forward(expected.account_id)
        for field in ("account_id", "execution_trade_date", "code_snapshot_sha256", "artifact_sha256"):
            if actual.get(field) != getattr(expected, field):
                raise GuardError(
                    f"latest {expected.account_id} FORWARD {field} differs from the frozen boundary"
                )


def _validate_readiness(protocol: GuardProtocol, environment: EarlyGuardEnvironment) -> dict[str, object]:
    try:
        readiness = environment.readiness(protocol.candidate.code_snapshot_sha256)
    except release.ReleaseError as error:
        raise GuardError(str(error)) from error
    if readiness.get("mode") != "CROSS_SNAPSHOT_WITH_NEW_DATA":
        raise GuardError("release readiness mode is not a cross-snapshot new-data start")
    if readiness.get("available_new_trade_dates") != [protocol.target_trade_date]:
        raise GuardError("release readiness does not expose the single frozen target date")
    return readiness


def _verify_active(protocol: GuardProtocol, environment: EarlyGuardEnvironment) -> SchedulerIdentity:
    current, previous = _release_state(environment)
    if _identity(current) != protocol.candidate.model_dump():
        raise GuardError("active release state differs from the frozen candidate")
    if _identity(previous) != protocol.expected_running_release.model_dump():
        raise GuardError("active release history differs from the frozen previous release")
    running = environment.running_scheduler()
    if not _running_matches(running, protocol.candidate) or running.health != "healthy":
        raise GuardError("active scheduler differs from the healthy frozen candidate")
    return running


def _restore_previous(
    protocol: GuardProtocol,
    environment: EarlyGuardEnvironment,
) -> dict[str, object]:
    current, previous = _release_state(environment)
    running = environment.running_scheduler()
    old = protocol.expected_running_release
    candidate = protocol.candidate
    if _identity(current) == old.model_dump():
        if _running_matches(running, old) and running.health == "healthy":
            return {"status": "ALREADY_RESTORED", "container_id": running.container_id}
        restored = environment.start_current()
    elif (
        _identity(current) == candidate.model_dump()
        and _identity(previous) == old.model_dump()
    ):
        restored = environment.rollback_and_start()
    else:
        raise GuardError("failed release cannot be restored from the observed release state")
    restored_current, _restored_previous = _release_state(environment)
    restored_running = environment.running_scheduler()
    if (
        _identity(restored_current) != old.model_dump()
        or not _running_matches(restored_running, old)
        or restored_running.health != "healthy"
    ):
        raise GuardError("previous release restoration did not recover the healthy scheduler")
    return {"status": "RESTORED", "release": restored, "container_id": restored_running.container_id}


def _execute_action(
    protocol: GuardProtocol,
    environment: EarlyGuardEnvironment,
    action: Literal["PROMOTE_AND_START", "RESUME_START"],
) -> dict[str, object]:
    try:
        if action == "PROMOTE_AND_START":
            mutation = environment.promote_and_start(protocol.candidate.image)
        else:
            mutation = environment.start_current()
        running = _verify_active(protocol, environment)
    except (release.ReleaseError, GuardError) as error:
        try:
            restored = _restore_previous(protocol, environment)
        except (release.ReleaseError, GuardError) as restore_error:
            raise GuardError(
                f"{action} failed and previous release restoration also failed: {restore_error}"
            ) from error
        raise GuardError(f"{action} failed; previous release restored: {restored['status']}") from error
    return {
        "mutation": mutation,
        "container_id": running.container_id,
        "candidate": protocol.candidate.model_dump(),
    }


def run_guard(
    protocol: GuardProtocol,
    *,
    now: datetime,
    execute: bool,
    environment: EarlyGuardEnvironment | None = None,
) -> dict[str, object]:
    env = environment or EarlyGuardEnvironment()
    checked_at = _validate_time(protocol, now)
    git = env.git_state()
    if git["status"]:
        raise GuardError("release guard requires a clean worktree")
    if git["head"] != git["origin_main"]:
        raise GuardError("release guard requires HEAD to equal origin/main")
    try:
        verified = env.verify_candidate(protocol.candidate.image)
    except release.ReleaseError as error:
        raise GuardError(str(error)) from error
    if _identity(verified) != protocol.candidate.model_dump():
        raise GuardError("candidate image runtime identity differs from the protocol")

    current, previous = _release_state(env)
    running = env.running_scheduler()
    candidate = protocol.candidate
    old = protocol.expected_running_release
    if (
        _identity(current) == candidate.model_dump()
        and _identity(previous) == old.model_dump()
        and _running_matches(running, candidate)
        and running.health == "healthy"
    ):
        return {
            "status": "ALREADY_ACTIVE",
            "guard_id": protocol.guard_id,
            "checked_at": checked_at,
            "container_id": running.container_id,
            "mutation_invoked": False,
        }
    if _identity(current) == old.model_dump() and _running_matches(running, old):
        action: Literal["PROMOTE_AND_START", "RESUME_START"] = "PROMOTE_AND_START"
    elif (
        _identity(current) == candidate.model_dump()
        and _identity(previous) == old.model_dump()
        and _running_matches(running, old)
    ):
        action = "RESUME_START"
    else:
        raise GuardError("release state and running scheduler are not an authorized transition state")
    if running.health != "healthy":
        raise GuardError("current scheduler is not healthy")

    _validate_forwards(protocol, env)
    readiness = _validate_readiness(protocol, env)
    evidence: dict[str, object] = {
        "status": "READY",
        "guard_id": protocol.guard_id,
        "checked_at": checked_at,
        "action": action,
        "running_before": {
            "container_id": running.container_id,
            "image_id": running.image_id,
            "code_snapshot_sha256": running.code_snapshot_sha256,
            "git_head": running.git_head,
            "health": running.health,
        },
        "readiness": readiness,
        "mutation_invoked": False,
    }
    if not execute:
        return evidence
    executed = _execute_action(protocol, env, action)
    return {
        **evidence,
        "status": "STARTED" if action == "PROMOTE_AND_START" else "RESUMED_AND_STARTED",
        "mutation_invoked": True,
        "execution": executed,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="perform the frozen promotion once")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        document = run_guard(
            load_protocol(),
            now=datetime.now(ZoneInfo("Asia/Shanghai")),
            execute=args.execute,
        )
    except (GuardError, OSError, ValueError) as error:
        print(json.dumps({"status": "BLOCKED", "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
