"""Versioned R2D approval binding and durable, single-use execution claims."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from shaiwei.release_metadata import confined
from shaiwei.storage.interprocess_lock import LockBusy, LockOrderError, _lock_path, logical_lock
from shaiwei.storage.lock_resources import R2D_RELEASE_EXECUTION


class ContractError(ValueError):
    pass


class Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ExecutionScope(Frozen):
    schema_version: Literal["r2d-execution-scope-v1"]
    action: Literal["START_CURRENT_ONCE"]
    protocol_path: str = Field(pattern=r"^config/r2d_[a-z0-9_]+\.yaml$")
    protocol_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    protocol: dict
    git_head: str = Field(pattern=r"^[0-9a-f]{40}$")
    origin_main: str = Field(pattern=r"^[0-9a-f]{40}$")
    state_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    audit_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    legacy_container_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    compose_project: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]*$")
    rollback_policy: Literal["FORBID_AFTER_DISPATCH"]
    health_max_age_seconds: Literal[3600]


class ScopeEnvelope(Frozen):
    scope_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    scope: ExecutionScope


class Approval(Frozen):
    schema_version: Literal["r2d-execution-approval-v1"]
    scope_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    approval_text: str


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def scope_hash(scope: ExecutionScope) -> str:
    return hashlib.sha256(canonical(scope.model_dump(mode="json"))).hexdigest()


def approval_text(digest: str) -> str:
    return (
        f"批准 scope {digest} 在冻结窗口内仅执行一次 start_current；"
        "启动派发后禁止自动回滚，不授权其他生产动作。"
    )


def load_scope(root: Path, path: str) -> ScopeEnvelope:
    if Path(path).suffix != ".json":
        raise ContractError("execution scope must be a JSON file")
    try:
        envelope = ScopeEnvelope.model_validate_json(confined(root, path).read_bytes())
    except (OSError, ValueError) as error:
        raise ContractError("execution scope is invalid") from error
    if scope_hash(envelope.scope) != envelope.scope_sha256:
        raise ContractError("execution scope hash differs")
    return envelope


def validate_approval(root: Path, path: str, envelope: ScopeEnvelope) -> str:
    if Path(path).suffix != ".json":
        raise ContractError("approval must be a JSON file")
    try:
        approval = Approval.model_validate_json(confined(root, path).read_bytes())
    except (OSError, ValueError) as error:
        raise ContractError("exact approval is missing or invalid") from error
    if (approval.scope_sha256 != envelope.scope_sha256
            or approval.approval_text != approval_text(envelope.scope_sha256)):
        raise ContractError("exact approval does not match scope")
    return hashlib.sha256(approval.approval_text.encode()).hexdigest()


def _sync_directory(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def write_once(path: Path, document: dict) -> None:
    # Caller confines parent; O_EXCL also rejects pre-existing symlinks.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(canonical(document) + b"\n")
        stream.flush()
        os.fsync(stream.fileno())
    _sync_directory(path.parent)


class ExecutionClaim:
    def __init__(self, directory: Path, envelope: ScopeEnvelope, approval_sha: str):
        self.directory, self.envelope = directory, envelope
        self.digest = envelope.scope_sha256
        self.dispatched = False
        self.result: dict | None = None
        write_once(directory / f"{self.digest}.claim.json", {
            "schema_version": "r2d-execution-claim-v1", "scope_sha256": self.digest,
            "approval_text_sha256": approval_sha, "status": "CLAIMED",
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "scope": envelope.scope.model_dump(mode="json"),
            "candidate": envelope.scope.protocol["candidate"],
        })

    def dispatch_barrier(self) -> None:
        write_once(self.directory / f"{self.digest}.write-barrier.json", {
            "schema_version": "r2d-write-barrier-v1", "scope_sha256": self.digest,
            "candidate": self.envelope.scope.protocol["candidate"],
            "target_trade_date": self.envelope.scope.protocol["target_trade_date"],
            "state": "MAY_HAVE_WRITTEN", "automatic_rollback_allowed": False,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        })
        self.dispatched = True

    def finish(self, status: str, error_class: str | None = None) -> None:
        write_once(self.directory / f"{self.digest}.receipt.json", {
            "schema_version": "r2d-execution-receipt-v1", "scope_sha256": self.digest,
            "status": status, "dispatch_barrier_written": self.dispatched,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "result": self.result, "error_class": error_class,
            "automatic_rollback_allowed": False,
        })


@contextmanager
def execution_claim(root: Path, envelope: ScopeEnvelope, approval_sha: str):
    directory = confined(root, ".release/r2d-executions")
    directory.mkdir(parents=True, exist_ok=True)
    _sync_directory(directory.parent)
    lock_path = _lock_path(directory, R2D_RELEASE_EXECUTION)
    confined(root, lock_path.relative_to(root).as_posix())
    try:
        with logical_lock(R2D_RELEASE_EXECUTION, blocking=False, lock_root=directory):
            try:
                claim = ExecutionClaim(directory, envelope, approval_sha)
            except FileExistsError as error:
                raise ContractError("scope already consumed; no retry") from error
            try:
                yield claim
            except BaseException as error:
                claim.finish("UNKNOWN_AFTER_DISPATCH" if claim.dispatched else "BLOCKED_BEFORE_DISPATCH",
                             type(error).__name__)
                raise
            else:
                claim.finish("STARTED" if claim.dispatched else "BLOCKED_BEFORE_DISPATCH")
    except (LockBusy, LockOrderError) as error:
        raise ContractError("another R2D execution is in progress") from error
