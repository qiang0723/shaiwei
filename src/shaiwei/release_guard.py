"""One-shot, fail-closed guard for the frozen Top20 scheduler release window."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import date, datetime, time
import json
from pathlib import Path
import subprocess
from typing import Any, Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, model_validator
import yaml

from shaiwei.config import PROJECT_ROOT
from shaiwei.ledger import PAPER_RUNS
from shaiwei import release
from shaiwei.release_build_context import controlled_source_status
from shaiwei.storage.runtime_mount_contract import (
    LOCK_VOLUME_DESTINATION,
    RuntimeMountContractError,
    validate_scheduler_mounts,
)


PROTOCOL_PATH = PROJECT_ROOT / "config" / "paper_top20_release_guard_v2.yaml"


class GuardError(RuntimeError):
    """A pre-start condition blocked the one-shot release."""


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ReleaseIdentity(FrozenModel):
    image: str
    image_id: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    code_snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    git_head: str = Field(pattern=r"^[0-9a-f]{40}$")


class RunningIdentity(FrozenModel):
    image_id: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    code_snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ForwardIdentity(FrozenModel):
    account_id: Literal["model_baseline"]
    execution_trade_date: str = Field(pattern=r"^[0-9]{8}$")
    code_snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class GuardWindow(FrozenModel):
    not_before: time
    expires_at: time


class GuardRequirements(FrozenModel):
    clean_worktree: Literal[True]
    head_equals_origin_main: Literal[True]
    release_audit_chain_pass: Literal[True]
    promoted_candidate_exact_match: Literal[True]
    target_is_only_new_trade_date: Literal[True]
    scheduler_healthy_before_start: Literal[True]
    start_current_once: Literal[True]
    run_daily_manually: Literal[False]
    promote_or_build: Literal[False]
    mutate_model_signal_or_gate: Literal[False]


class GuardProtocol(FrozenModel):
    schema_version: Literal["paper-top20-release-guard-v1"]
    guard_id: str = Field(pattern=r"^paper-top20-release-guard-[0-9]{8}$")
    timezone: Literal["Asia/Shanghai"]
    target_trade_date: str = Field(pattern=r"^[0-9]{8}$")
    window: GuardWindow
    candidate: ReleaseIdentity
    expected_running_release: RunningIdentity
    expected_latest_forward: ForwardIdentity
    requirements: GuardRequirements

    @model_validator(mode="after")
    def validate_guard_date(self) -> "GuardProtocol":
        if self.guard_id.rsplit("-", 1)[-1] != self.target_trade_date:
            raise ValueError("release guard ID date must equal target_trade_date")
        return self


@dataclass(frozen=True)
class SchedulerIdentity:
    container_id: str
    image_id: str
    health: str
    code_snapshot_sha256: str
    git_head: str
    read_only_rootfs: bool | None = None
    mount_destinations: tuple[str, ...] = ()
    lock_authority: str = ""


class GuardEnvironment:
    """Narrow host adapter; tests replace this object without touching Docker or Git."""

    def git_state(self) -> dict[str, object]:
        status = self._run(["git", "status", "--porcelain"]).stdout.strip()
        controlled = controlled_source_status(PROJECT_ROOT)
        return {"status": status, **controlled}

    def release_status(self) -> dict[str, object]:
        return release.status()

    def verify_candidate(self, image: str) -> dict[str, str]:
        return release.verify_image(image)

    def running_scheduler(self) -> SchedulerIdentity:
        container_id = self._run(["docker", "compose", "ps", "-q", "scheduler"]).stdout.strip()
        if not container_id:
            raise GuardError("scheduler container is not running")
        targeted = self._run(
            [
                "docker",
                "inspect",
                "--format",
                "{{.Image}}|{{if .State.Health}}{{.State.Health.Status}}{{else}}missing{{end}}|"
                "{{.HostConfig.ReadonlyRootfs}}|{{json .Mounts}}",
                container_id,
            ]
        ).stdout.strip()
        try:
            image_id, health, readonly_text, mounts_text = targeted.split("|", 3)
            mounts = json.loads(mounts_text)
        except (ValueError, json.JSONDecodeError) as error:
            raise GuardError("scheduler targeted identity is invalid") from error
        has_lock_mount = any(
            isinstance(item, dict) and item.get("Destination") == LOCK_VOLUME_DESTINATION
            for item in mounts
        )
        try:
            destinations = validate_scheduler_mounts(
                mounts,
                lock_required=has_lock_mount,
            )
        except RuntimeMountContractError as error:
            raise GuardError(str(error)) from error
        try:
            image_metadata = release._image_metadata(image_id)
        except release.ReleaseError as error:
            raise GuardError(str(error)) from error
        command = (
            "import json; from shaiwei.provenance import code_snapshot_sha256,git_head; "
            "print(json.dumps({'code_snapshot_sha256':code_snapshot_sha256(),'git_head':git_head()}))"
        )
        payload = self._run(["docker", "exec", container_id, "python", "-c", command]).stdout.strip()
        try:
            runtime = json.loads(payload)
        except json.JSONDecodeError as error:
            raise GuardError("scheduler runtime identity is invalid JSON") from error
        return SchedulerIdentity(
            container_id=container_id,
            image_id=image_id,
            health=health,
            code_snapshot_sha256=str(runtime.get("code_snapshot_sha256", "")),
            git_head=str(runtime.get("git_head", "")),
            read_only_rootfs=readonly_text.lower() == "true",
            mount_destinations=tuple(destinations),
            lock_authority=str(
                image_metadata.get("lock_authority", "legacy-bind-flock-v0")
            ),
        )

    def latest_forward(self, account_id: str) -> dict[str, str]:
        if not PAPER_RUNS.is_file():
            raise GuardError("paper runs ledger is missing")
        with PAPER_RUNS.open(newline="", encoding="utf-8") as handle:
            rows = [
                row
                for row in csv.DictReader(handle)
                if row.get("status") == "PASS" and row.get("account_id") == account_id
            ]
        if not rows:
            raise GuardError("latest baseline FORWARD evidence is missing")
        return max(
            rows,
            key=lambda row: (row.get("execution_trade_date", ""), row.get("finished_at", "")),
        )

    def readiness(self, snapshot: str) -> dict[str, object]:
        return release.release_start_readiness(snapshot)

    def start_current(self) -> dict[str, object]:
        return release.start_current()

    @staticmethod
    def _run(argv: list[str]) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(
                argv,
                cwd=PROJECT_ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as error:
            detail = (error.stderr or error.stdout or "").strip()
            raise GuardError(f"command failed: {' '.join(argv)}: {detail}") from error


def validate_controlled_git_state(
    environment: GuardEnvironment,
    *,
    error_type: type[Exception] = GuardError,
) -> None:
    """Require pushed controlled source while allowing runtime evidence to remain dirty."""
    git = environment.git_state()
    changes = git.get("controlled_changes")
    if changes is None:
        if git.get("status"):
            raise error_type("release guard requires a clean worktree")
    elif tuple(changes):
        raise error_type("release guard requires a clean controlled source tree")
    if git.get("head") != git.get("origin_main"):
        raise error_type("release guard requires HEAD to equal origin/main")


def load_protocol(path: Path = PROTOCOL_PATH) -> GuardProtocol:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    return GuardProtocol.model_validate(document)


def _identity(document: dict[str, Any]) -> dict[str, str]:
    return {
        field: str(document.get(field, ""))
        for field in ("image", "image_id", "code_snapshot_sha256", "git_head")
    }


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


def run_guard(
    protocol: GuardProtocol,
    *,
    now: datetime,
    execute: bool,
    environment: GuardEnvironment | None = None,
) -> dict[str, object]:
    env = environment or GuardEnvironment()
    checked_at = _validate_time(protocol, now)
    git_state = env.git_state()
    if git_state["status"]:
        raise GuardError("release guard requires a clean worktree")
    if git_state["head"] != git_state["origin_main"]:
        raise GuardError("release guard requires HEAD to equal origin/main")

    try:
        release_document = env.release_status()
    except release.ReleaseError as error:
        raise GuardError(str(error)) from error
    if release_document.get("status") != "PASS":
        raise GuardError("release audit status is not PASS")
    state = release_document.get("state")
    current = state.get("current") if isinstance(state, dict) else None
    previous = state.get("previous") if isinstance(state, dict) else None
    if not isinstance(current, dict) or _identity(current) != protocol.candidate.model_dump():
        raise GuardError("promoted release differs from the frozen candidate")
    try:
        verified = env.verify_candidate(protocol.candidate.image)
    except release.ReleaseError as error:
        raise GuardError(str(error)) from error
    if _identity(verified) != protocol.candidate.model_dump():
        raise GuardError("candidate image runtime identity differs from the protocol")

    running = env.running_scheduler()
    if (
        running.image_id == protocol.candidate.image_id
        and running.code_snapshot_sha256 == protocol.candidate.code_snapshot_sha256
        and running.git_head == protocol.candidate.git_head
        and running.health == "healthy"
    ):
        return {
            "status": "ALREADY_ACTIVE",
            "guard_id": protocol.guard_id,
            "checked_at": checked_at,
            "container_id": running.container_id,
            "candidate": protocol.candidate.model_dump(),
            "start_invoked": False,
        }
    if running.health != "healthy":
        raise GuardError("current scheduler is not healthy")
    if running.image_id != protocol.expected_running_release.image_id:
        raise GuardError("running scheduler image differs from the frozen old release")
    if running.code_snapshot_sha256 != protocol.expected_running_release.code_snapshot_sha256:
        raise GuardError("running scheduler snapshot differs from the frozen old release")
    previous_identity = _identity(previous) if isinstance(previous, dict) else {}
    if previous_identity.get("image_id") != protocol.expected_running_release.image_id:
        raise GuardError("release history does not bind the frozen old image")
    if (
        previous_identity.get("code_snapshot_sha256")
        != protocol.expected_running_release.code_snapshot_sha256
    ):
        raise GuardError("release history does not bind the frozen old snapshot")
    if running.git_head != previous_identity.get("git_head"):
        raise GuardError("running scheduler Git identity differs from release history")

    forward = env.latest_forward(protocol.expected_latest_forward.account_id)
    expected_forward = protocol.expected_latest_forward
    if forward.get("execution_trade_date") != expected_forward.execution_trade_date:
        raise GuardError("latest baseline execution date differs from the frozen boundary")
    if forward.get("code_snapshot_sha256") != expected_forward.code_snapshot_sha256:
        raise GuardError("latest baseline snapshot differs from the frozen boundary")

    try:
        readiness = env.readiness(protocol.candidate.code_snapshot_sha256)
    except release.ReleaseError as error:
        raise GuardError(str(error)) from error
    if readiness.get("mode") != "CROSS_SNAPSHOT_WITH_NEW_DATA":
        raise GuardError("release readiness mode is not a cross-snapshot new-data start")
    if readiness.get("available_new_trade_dates") != [protocol.target_trade_date]:
        raise GuardError("release readiness does not expose the single frozen target date")

    evidence: dict[str, object] = {
        "status": "READY",
        "guard_id": protocol.guard_id,
        "checked_at": checked_at,
        "candidate": protocol.candidate.model_dump(),
        "running_before": {
            "container_id": running.container_id,
            "image_id": running.image_id,
            "code_snapshot_sha256": running.code_snapshot_sha256,
            "git_head": running.git_head,
            "health": running.health,
        },
        "latest_forward_execution_date": forward["execution_trade_date"],
        "readiness": readiness,
        "start_invoked": False,
    }
    if not execute:
        return evidence
    try:
        started = env.start_current()
    except release.ReleaseError as error:
        raise GuardError(f"frozen release start failed: {error}") from error
    return {
        **evidence,
        "status": "STARTED",
        "start_invoked": True,
        "start_evidence": started,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="start the frozen current release once")
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
