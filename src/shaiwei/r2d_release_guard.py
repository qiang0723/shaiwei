"""Two-phase, result-blind production guard for the R2D named-lock release."""

from __future__ import annotations

import argparse
from datetime import date, datetime, time
import hashlib
import json
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import Field, model_validator
import yaml

from shaiwei import daily_early_release_guard as base
from shaiwei import release
from shaiwei.config import PROJECT_ROOT
from shaiwei.release_build_context import (
    ControllerIdentity,
    ControllerIdentityError,
    collect_controller_evidence,
    validate_controller_evidence,
)
from shaiwei.release_guard import validate_controlled_git_state
from shaiwei.storage.runtime_mount_contract import LOCK_AUTHORITY


PROTOCOL_PATH = PROJECT_ROOT / "config" / "r2d_scheduler_release_guard_v1.yaml"


class FixtureEvidence(base.FrozenModel):
    release_scope_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    report_path: str = Field(pattern=r"^\.release/[A-Za-z0-9_./-]+\.json$")
    report_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    tree_path: str = Field(pattern=r"^\.release/[A-Za-z0-9_./-]+\.json$")
    tree_file_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    tree_content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    receipt_path: str = Field(pattern=r"^\.release/[A-Za-z0-9_./-]+\.json$")
    receipt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class GuardProtocol(base.FrozenModel):
    schema_version: Literal["r2d-scheduler-release-guard-v1"]
    guard_id: str = Field(pattern=r"^r2d-scheduler-release-guard-[0-9]{8}$")
    timezone: Literal["Asia/Shanghai"]
    prepare_date: str = Field(pattern=r"^[0-9]{8}$")
    prepare_window: base.GuardWindow
    target_trade_date: str = Field(pattern=r"^[0-9]{8}$")
    start_window: base.GuardWindow
    candidate: base.ReleaseIdentity
    expected_running_release: base.ReleaseIdentity
    expected_latest_forward: tuple[base.ForwardIdentity, ...]
    expected_legacy_mounts_before_prepare: tuple[str, ...]
    predecessor_fixture: FixtureEvidence
    controller_identity: ControllerIdentity

    @model_validator(mode="after")
    def validate_protocol(self) -> "GuardProtocol":
        if self.guard_id.rsplit("-", 1)[-1] != self.target_trade_date:
            raise ValueError("R2D guard ID date must equal target trade date")
        if self.prepare_date >= self.target_trade_date:
            raise ValueError("R2D prepare date must precede the target trade date")
        if self.candidate.lock_authority != LOCK_AUTHORITY:
            raise ValueError("R2D candidate lacks the named-volume lock authority")
        if self.expected_running_release.lock_authority != "legacy-bind-flock-v0":
            raise ValueError("R2D running release lacks the explicit legacy authority")
        if self.candidate.image_id == self.expected_running_release.image_id:
            raise ValueError("R2D candidate and running release must be distinct")
        accounts = [item.account_id for item in self.expected_latest_forward]
        if len(accounts) != 2 or set(accounts) != {"model_baseline", "model_top20"}:
            raise ValueError("R2D must bind exactly the Top30 and Top20 accounts")
        if set(self.expected_legacy_mounts_before_prepare) != {
            "/workspace/data",
            "/workspace/ledger",
            "/workspace/logs",
        }:
            raise ValueError("R2D legacy pre-prepare mounts differ from the frozen contract")
        return self


class R2DEnvironment(base.EarlyGuardEnvironment):
    def promote_no_start(self, image: str) -> dict[str, object]:
        return release.promote(image, start=False)

    def scheduler_health(self) -> dict[str, object]:
        path = PROJECT_ROOT / "logs" / "scheduler" / "health.json"
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise base.GuardError("scheduler health evidence is unreadable") from error
        if not isinstance(document, dict):
            raise base.GuardError("scheduler health evidence is not an object")
        return document

    def controller_evidence(self, identity: ControllerIdentity) -> dict[str, object]:
        return collect_controller_evidence(PROJECT_ROOT, self._run, identity)


def load_protocol(path: Path = PROTOCOL_PATH) -> GuardProtocol:
    return GuardProtocol.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def _validate_window(
    *,
    date_text: str,
    window: base.GuardWindow,
    timezone: str,
    now: datetime,
    phase: str,
) -> str:
    if now.tzinfo is None:
        raise base.GuardError("guard clock must be timezone-aware")
    local = now.astimezone(ZoneInfo(timezone))
    expected = date.fromisoformat(
        f"{date_text[:4]}-{date_text[4:6]}-{date_text[6:]}"
    )
    if local.date() != expected:
        raise base.GuardError(f"{phase} date does not equal the local date")
    clock = local.time().replace(tzinfo=None)
    if clock < window.not_before:
        raise base.GuardError(f"{phase} window has not opened")
    if clock >= window.expires_at:
        raise base.GuardError(f"{phase} window has expired")
    return local.isoformat(timespec="seconds")


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _validate_controller(
    protocol: GuardProtocol,
    environment: R2DEnvironment,
) -> dict[str, object]:
    identity = protocol.controller_identity
    evidence = environment.controller_evidence(identity)
    try:
        validate_controller_evidence(identity, evidence)
    except ControllerIdentityError as error:
        raise base.GuardError(str(error)) from error
    return evidence


def _fixture_json(path_text: str, expected_sha256: str) -> dict[str, object]:
    path = (PROJECT_ROOT / path_text).resolve()
    try:
        path.relative_to(PROJECT_ROOT.resolve())
        actual = _file_sha256(path)
        document = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as error:
        raise base.GuardError("fixture evidence escapes the project") from error
    except (OSError, json.JSONDecodeError) as error:
        raise base.GuardError("fixture evidence is unreadable") from error
    if actual != expected_sha256 or not isinstance(document, dict):
        raise base.GuardError("fixture evidence hash or schema differs")
    return document


def _validate_fixture(protocol: GuardProtocol) -> None:
    fixture = protocol.predecessor_fixture
    report = _fixture_json(fixture.report_path, fixture.report_sha256)
    tree = _fixture_json(fixture.tree_path, fixture.tree_file_sha256)
    receipt = _fixture_json(fixture.receipt_path, fixture.receipt_sha256)
    if (
        report.get("scope_sha256") != fixture.release_scope_sha256
        or report.get("verdict") != "PASS"
        or tree.get("tree_sha256") != fixture.tree_content_sha256
        or receipt.get("release_scope_sha256") != fixture.release_scope_sha256
        or receipt.get("report_sha256") != fixture.report_sha256
        or receipt.get("evidence_tree_file_sha256") != fixture.tree_file_sha256
        or receipt.get("evidence_tree_sha256") != fixture.tree_content_sha256
        or receipt.get("status") != "PASS"
        or receipt.get("candidate") != protocol.candidate.image
        or receipt.get("image_id") != protocol.candidate.image_id
    ):
        raise base.GuardError("fixture evidence differs from the frozen R2D boundary")


def _verify_candidate(protocol: GuardProtocol, environment: R2DEnvironment) -> None:
    try:
        verified = environment.verify_candidate(protocol.candidate.image)
    except release.ReleaseError as error:
        raise base.GuardError(str(error)) from error
    if base._identity(verified, protocol.candidate) != base._expected_identity(
        protocol.candidate
    ):
        raise base.GuardError("candidate image runtime identity differs from the protocol")


def _validate_waiting_source(
    protocol: GuardProtocol,
    environment: R2DEnvironment,
) -> dict[str, str]:
    document = environment.scheduler_health()
    if document.get("status") != "waiting_source":
        raise base.GuardError("legacy scheduler did not close its probe as waiting_source")
    if document.get("detail") != protocol.target_trade_date:
        raise base.GuardError("legacy waiting_source target differs from the frozen date")
    try:
        updated = datetime.fromisoformat(str(document.get("updated_at", "")))
    except ValueError as error:
        raise base.GuardError("legacy scheduler health timestamp is invalid") from error
    if updated.tzinfo is None:
        raise base.GuardError("legacy scheduler health timestamp is timezone-naive")
    local = updated.astimezone(ZoneInfo(protocol.timezone))
    if local.strftime("%Y%m%d") != protocol.target_trade_date or local.time() < time(16, 0):
        raise base.GuardError("legacy waiting_source evidence is outside the target boundary")
    return {"status": "waiting_source", "detail": protocol.target_trade_date, "updated_at": updated.isoformat()}


def _legacy_running(
    protocol: GuardProtocol,
    environment: R2DEnvironment,
):
    running = environment.running_scheduler()
    old = protocol.expected_running_release
    if not base._running_matches(running, old) or running.health != "healthy":
        raise base.GuardError("legacy scheduler is not the frozen healthy running release")
    return running


def prepare_guard(
    protocol: GuardProtocol,
    *,
    now: datetime,
    execute: bool,
    environment: R2DEnvironment | None = None,
) -> dict[str, object]:
    env = environment or R2DEnvironment()
    checked_at = _validate_window(
        date_text=protocol.prepare_date,
        window=protocol.prepare_window,
        timezone=protocol.timezone,
        now=now,
        phase="prepare",
    )
    validate_controlled_git_state(env, error_type=base.GuardError)
    controller = _validate_controller(protocol, env)
    _validate_fixture(protocol)
    _verify_candidate(protocol, env)
    current, previous = base._release_state(env)
    running = _legacy_running(protocol, env)
    old, candidate = protocol.expected_running_release, protocol.candidate
    if set(running.mount_destinations) != set(protocol.expected_legacy_mounts_before_prepare):
        raise base.GuardError("legacy scheduler pre-prepare mounts differ from the contract")
    if (
        base._identity(current, candidate) == base._expected_identity(candidate)
        and base._identity(previous, old) == base._expected_identity(old)
    ):
        return {"status": "ALREADY_PREPARED", "checked_at": checked_at, "mutation_invoked": False}
    if base._identity(current, old) != base._expected_identity(old):
        raise base.GuardError("release state is not the frozen pre-prepare state")
    evidence = {
        "status": "READY_TO_PREPARE",
        "checked_at": checked_at,
        "controller": controller,
        "mutation_invoked": False,
    }
    if not execute:
        return evidence
    try:
        mutation = env.promote_no_start(candidate.image)
    except release.ReleaseError as error:
        raise base.GuardError(str(error)) from error
    after_current, after_previous = base._release_state(env)
    after_running = _legacy_running(protocol, env)
    if (
        base._identity(after_current, candidate) != base._expected_identity(candidate)
        or base._identity(after_previous, old) != base._expected_identity(old)
        or after_running.container_id != running.container_id
    ):
        raise base.GuardError("R2D prepare did not preserve the exact legacy container")
    return {**evidence, "status": "PREPARED", "mutation_invoked": True, "mutation": mutation}


def start_guard(
    protocol: GuardProtocol,
    *,
    now: datetime,
    execute: bool,
    environment: R2DEnvironment | None = None,
) -> dict[str, object]:
    env = environment or R2DEnvironment()
    checked_at = _validate_window(
        date_text=protocol.target_trade_date,
        window=protocol.start_window,
        timezone=protocol.timezone,
        now=now,
        phase="start",
    )
    validate_controlled_git_state(env, error_type=base.GuardError)
    controller = _validate_controller(protocol, env)
    _validate_fixture(protocol)
    _verify_candidate(protocol, env)
    current, previous = base._release_state(env)
    running = env.running_scheduler()
    old, candidate = protocol.expected_running_release, protocol.candidate
    if (
        base._identity(current, candidate) == base._expected_identity(candidate)
        and base._identity(previous, old) == base._expected_identity(old)
        and base._running_matches(running, candidate)
        and running.health == "healthy"
    ):
        return {"status": "ALREADY_ACTIVE", "checked_at": checked_at, "mutation_invoked": False}
    if not (
        base._identity(current, candidate) == base._expected_identity(candidate)
        and base._identity(previous, old) == base._expected_identity(old)
        and base._running_matches(running, old)
        and running.health == "healthy"
    ):
        raise base.GuardError("R2D start requires the exact prepared transition state")
    base._validate_forwards(protocol, env)
    readiness = base._validate_readiness(protocol, env)
    waiting = _validate_waiting_source(protocol, env)
    evidence: dict[str, object] = {
        "status": "READY_TO_START",
        "checked_at": checked_at,
        "readiness": readiness,
        "legacy_waiting_source": waiting,
        "controller": controller,
        "mutation_invoked": False,
    }
    if not execute:
        return evidence
    executed = base._execute_action(protocol, env, "RESUME_START")
    return {**evidence, "status": "STARTED", "mutation_invoked": True, "execution": executed}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("prepare", "start"), required=True)
    parser.add_argument("--execute", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        protocol = load_protocol()
        runner = prepare_guard if args.phase == "prepare" else start_guard
        document = runner(
            protocol,
            now=datetime.now(ZoneInfo(protocol.timezone)),
            execute=args.execute,
        )
    except (base.GuardError, OSError, ValueError) as error:
        print(json.dumps({"status": "BLOCKED", "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
