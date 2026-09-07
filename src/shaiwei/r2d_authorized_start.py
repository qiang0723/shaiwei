"""Authorized, single-use R2D start orchestration with no automatic rollback."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from shaiwei import r2d_release_guard as guard
from shaiwei.config import PROJECT_ROOT
from shaiwei.r2d_execution_contract import (
    ContractError, ExecutionScope, execution_claim, load_scope, validate_approval,
)
from shaiwei.r2d_metadata_environment import SecureEnvironment
from shaiwei.release_metadata import confined, sha256

REQUIRED_COMPONENTS = {
    "src/shaiwei/release.py",
    "src/shaiwei/storage/interprocess_lock.py",
    "src/shaiwei/storage/lock_resources.py",
    "src/shaiwei/release_build_context.py",
    "src/shaiwei/release_guard.py",
    "src/shaiwei/daily_early_release_guard.py",
    "src/shaiwei/r2d_release_guard.py",
    "src/shaiwei/r2d_legacy_boundary.py",
    "src/shaiwei/r2d_fixture_evidence.py",
    "src/shaiwei/release_metadata.py",
    "src/shaiwei/r2d_execution_contract.py",
    "src/shaiwei/r2d_metadata_environment.py",
    "src/shaiwei/r2d_authorized_start.py",
}


def check_binding(root: Path, scope: ExecutionScope):
    path = confined(root, scope.protocol_path)
    if sha256(path) != scope.protocol_sha256:
        raise ContractError("protocol file hash differs")
    protocol = guard.load_protocol(path)
    if protocol.model_dump(mode="json") != scope.protocol:
        raise ContractError("scope protocol identity differs")
    if set(protocol.controller_identity.component_paths) != REQUIRED_COMPONENTS:
        raise ContractError("secure controller inventory is not frozen")
    if protocol.legacy_noop_boundary is None:
        raise ContractError("authorized start requires prior-day noop")
    if set(protocol.expected_legacy_mounts_before_prepare) != {
        "/workspace/data", "/workspace/ledger", "/workspace/logs", "/run/shaiwei-locks",
    }:
        raise ContractError("authorized start requires four frozen mounts")
    return protocol


def check_time(protocol, now: datetime):
    return guard._validate_window(
        date_text=protocol.target_trade_date, window=protocol.start_window,
        timezone=protocol.timezone, now=now, phase="start",
    )


def dynamic_gates(scope, protocol, env, clock):
    state_hash, audit_hash = env.release_hashes()
    if (state_hash, audit_hash) != (scope.state_sha256, scope.audit_sha256):
        raise ContractError("release state or audit drifted")
    git = env.git_state()
    if git.get("head") != scope.git_head or git.get("origin_main") != scope.origin_main:
        raise ContractError("execution Git binding drifted")
    guard.validate_controlled_git_state(env, error_type=ContractError)
    guard._verify_candidate(protocol, env)
    running = env.running_scheduler()
    if (running.container_id != scope.legacy_container_id
            or getattr(running, "restart_count", None) != 0
            or running.health != "healthy"
            or not guard.base._running_matches(running, protocol.expected_running_release)
            or len(running.mount_destinations) != 4):
        raise ContractError("frozen legacy container, restart or mounts differ")
    guard.base._validate_forwards(protocol, env)
    readiness = guard.base._validate_readiness(protocol, env)
    if readiness.get("status") != "PASS":
        raise ContractError("release readiness is not PASS")
    _, boundary = guard._validate_legacy_boundary(protocol, env)
    now = clock()
    checked = check_time(protocol, now)
    updated = datetime.fromisoformat(boundary["updated_at"])
    age = (now - updated).total_seconds()
    if not 0 <= age <= scope.health_max_age_seconds:
        raise ContractError("legacy heartbeat is future-dated or stale")
    return {"checked_at": checked, "container_id": running.container_id,
            "restart_count": 0, "mounts": sorted(running.mount_destinations),
            "health_age_seconds": age, "readiness": readiness,
            "legacy_noop_boundary": boundary, "forwards_verified": True}


def run(
    *, scope_path: str, approval_path: str | None = None, execute: bool = False,
    root: Path = PROJECT_ROOT, environment=None, clock=None,
):
    clock = clock or (lambda: datetime.now(ZoneInfo("Asia/Shanghai")))
    envelope = load_scope(root, scope_path)
    scope = envelope.scope
    # Missing approval fails before constructing any host adapter or querying Docker.
    approval_sha = None
    if execute:
        if not approval_path:
            raise ContractError("exact approval is required")
        approval_sha = validate_approval(root, approval_path, envelope)
    protocol = check_binding(root, scope)
    check_time(protocol, clock())
    env = environment or SecureEnvironment(root, scope.compose_project)

    def preflight():
        result = guard.start_guard(protocol, now=clock(), execute=False, environment=env)
        if result["status"] != "READY_TO_START":
            raise ContractError("transition is no longer ready")
        return dynamic_gates(scope, protocol, env, clock)

    if not execute:
        return {"status": "READY_TO_START", "mutation_invoked": False,
                "scope_sha256": envelope.scope_sha256, "gates": preflight()}
    with execution_claim(root, envelope, approval_sha) as claim:
        gates = preflight()
        # Verify file binding again inside the execution lock.
        check_binding(root, scope)
        dynamic_gates(scope, protocol, env, clock)
        claim.dispatch_barrier()

        def before_mutation():
            check_binding(root, scope)
            dynamic_gates(scope, protocol, env, clock)

        result = env.start_once(before_mutation)
        active = guard.base._verify_active(protocol, env)
        if getattr(active, "restart_count", None) != 0:
            raise ContractError("started candidate restart count differs")
        claim.result = {"status": "STARTED", "mutation_invoked": True,
                "scope_sha256": envelope.scope_sha256, "gates_before": gates,
                "container_id": active.container_id,
                "automatic_rollback_allowed": False,
                "release_audit_record_sha256": result.get("audit_record_sha256")}
        return claim.result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", required=True)
    parser.add_argument("--approval")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = run(scope_path=args.scope, approval_path=args.approval, execute=args.execute)
    except Exception as error:
        # Do not expose nested command outputs, validation input or artifact content.
        print(json.dumps({"status": "BLOCKED", "error_class": type(error).__name__}))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
