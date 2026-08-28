"""One-shot isolated Docker health convergence fixture for R2D-R3A."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
from types import SimpleNamespace
import subprocess
from typing import Callable

from shaiwei import daily_early_release_guard as guard
from shaiwei import release
from shaiwei.config import PROJECT_ROOT
from shaiwei.release_guard import SchedulerIdentity
from shaiwei.storage.runtime_mount_contract import LOCK_AUTHORITY


ACTION = "R2D_R3A_DOCKER_HEALTH_CONVERGENCE_FIXTURE_ONCE"
SCHEMA = "shaiwei-r2d-r3a-health-convergence-fixture-v1"
COMPOSE_PATH = PROJECT_ROOT / "compose.r2d-r3a-health-fixture.yaml"
OUTPUT_PREFIX = PROJECT_ROOT / ".release" / "r2d-r3a-health-fixture"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_GIT_HEAD = re.compile(r"^[0-9a-f]{40}$")


class FixtureError(RuntimeError):
    """The isolated release-health fixture failed closed."""


@dataclass(frozen=True)
class FixtureSpec:
    image: str
    expected_head: str
    expected_snapshot: str
    scope_sha256: str
    expected_release_state_sha256: str
    expected_release_audit_sha256: str
    output_root: Path

    def validate(self) -> None:
        if _GIT_HEAD.fullmatch(self.expected_head) is None:
            raise FixtureError("expected Git HEAD is invalid")
        if _SHA256.fullmatch(self.expected_snapshot) is None:
            raise FixtureError("expected code snapshot is invalid")
        if _SHA256.fullmatch(self.scope_sha256) is None:
            raise FixtureError("scope SHA-256 is invalid")
        if _SHA256.fullmatch(self.expected_release_state_sha256) is None:
            raise FixtureError("expected production release state SHA-256 is invalid")
        if _SHA256.fullmatch(self.expected_release_audit_sha256) is None:
            raise FixtureError("expected production release audit SHA-256 is invalid")
        if self.image != f"shaiwei:scheduler-{self.expected_snapshot[:16]}":
            raise FixtureError("candidate tag differs from the content-addressed snapshot")
        resolved = self.output_root.resolve(strict=False)
        prefix = OUTPUT_PREFIX.resolve(strict=False)
        if resolved.parent != prefix or resolved.name != self.scope_sha256[:16]:
            raise FixtureError("fixture output root is outside the one-shot scope")
        if self.output_root.exists():
            raise FixtureError("fixture scope already has evidence and cannot be rerun")
        if not COMPOSE_PATH.is_file() or COMPOSE_PATH.is_symlink():
            raise FixtureError("fixture Compose definition is missing or unsafe")


class DockerClient:
    def __init__(self, runner: Callable[..., subprocess.CompletedProcess[str]] | None = None):
        self._runner = runner or subprocess.run
        self.command_count = 0

    def run(
        self,
        argv: list[str],
        *,
        env: dict[str, str] | None = None,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        self.command_count += 1
        try:
            return self._runner(
                argv,
                cwd=PROJECT_ROOT,
                env=env,
                check=check,
                capture_output=True,
                text=True,
                timeout=120,
            )
        except subprocess.CalledProcessError as error:
            detail = (error.stderr or error.stdout or "").strip()
            raise FixtureError(f"fixture command failed: {argv[:5]}: {detail}") from error


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else ""


def _tree_manifest(root: Path) -> str:
    rows = []
    for path in sorted(item for item in root.rglob("*") if item.is_file() and item.name != "tree.json"):
        rows.append(
            {
                "path": path.relative_to(root).as_posix(),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "bytes": path.stat().st_size,
            }
        )
    payload = json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    (root / "tree.json").write_text(
        json.dumps({"files": rows, "tree_sha256": digest}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return digest


def _compose_command(project: str, *args: str) -> list[str]:
    return [
        "docker",
        "compose",
        "--env-file",
        "/dev/null",
        "--project-name",
        project,
        "--file",
        str(COMPOSE_PATH),
        *args,
    ]


def _compose_environment(spec: FixtureSpec) -> dict[str, str]:
    environment = {
        key: os.environ[key]
        for key in ("PATH", "HOME", "DOCKER_CONFIG", "DOCKER_CONTEXT", "DOCKER_HOST")
        if key in os.environ
    }
    environment.update(
        {
            "SHAIWEI_R2D_R3A_IMAGE": spec.image,
            "SHAIWEI_R2D_R3A_DATA": str(spec.output_root / "data"),
            "SHAIWEI_R2D_R3A_LEDGER": str(spec.output_root / "ledger"),
            "SHAIWEI_R2D_R3A_LOGS": str(spec.output_root / "logs"),
        }
    )
    return environment


def _docker_health(client: DockerClient, container_id: str) -> str:
    return client.run(
        [
            "docker",
            "inspect",
            "--format",
            "{{if .State.Health}}{{.State.Health.Status}}{{else}}missing{{end}}",
            container_id,
        ]
    ).stdout.strip()


class _GuardEnvironment:
    def __init__(self, candidate: guard.ReleaseIdentity, contract: dict[str, object]):
        self.candidate = candidate
        self.old = guard.ReleaseIdentity(
            image="shaiwei:scheduler-" + "0" * 16,
            image_id="sha256:" + "0" * 64,
            code_snapshot_sha256="0" * 64,
            git_head="0" * 40,
            lock_authority="legacy-bind-flock-v0",
        )
        self.contract = contract
        self.rollback_calls = 0

    def start_current(self) -> dict[str, object]:
        return self.contract

    def release_status(self) -> dict[str, object]:
        return {
            "status": "PASS",
            "state": {
                "current": self.candidate.model_dump(),
                "previous": self.old.model_dump(),
            },
        }

    def running_scheduler(self) -> SchedulerIdentity:
        return SchedulerIdentity(
            container_id=str(self.contract["container_id"]),
            image_id=str(self.contract["image_id"]),
            health=str(self.contract["health"]),
            code_snapshot_sha256=str(self.contract["code_snapshot_sha256"]),
            git_head=str(self.contract["git_head"]),
            read_only_rootfs=bool(self.contract["read_only_rootfs"]),
            mount_destinations=tuple(self.contract["mount_destinations"]),
            lock_authority=str(self.contract["lock_authority"]),
        )

    def rollback_and_start(self) -> dict[str, object]:
        self.rollback_calls += 1
        raise FixtureError("successful convergence path attempted rollback")


def _write_report(
    spec: FixtureSpec,
    *,
    candidate: dict[str, object],
    cases: list[dict[str, str]],
    command_count: int,
    production_before: dict[str, str],
    production_after: dict[str, str],
    failure: str,
) -> dict[str, object]:
    report: dict[str, object] = {
        "schema_version": SCHEMA,
        "action": ACTION,
        "scope_sha256": spec.scope_sha256,
        "candidate": candidate,
        "cases": cases,
        "command_count": command_count,
        "production_evidence_before": production_before,
        "production_evidence_after": production_after,
        "production_identity_unchanged": production_before == production_after,
        "verdict": "PASS" if not failure else "FAIL",
        "error_type": failure,
        "production_authorization": "none",
    }
    report_path = spec.output_root / "report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_sha = _sha256(report_path)
    tree_sha = _tree_manifest(spec.output_root)
    receipt = {
        "action": ACTION,
        "scope_sha256": spec.scope_sha256,
        "report_sha256": report_sha,
        "evidence_tree_sha256": tree_sha,
        "status": report["verdict"],
    }
    receipt_path = spec.output_root / "receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {**report, "report_sha256": report_sha, "evidence_tree_sha256": tree_sha}


def execute(spec: FixtureSpec, *, client: DockerClient | None = None) -> dict[str, object]:
    spec.validate()
    spec.output_root.mkdir(parents=True)
    for name in ("data", "ledger", "logs"):
        (spec.output_root / name).mkdir()
    claim = {
        "action": ACTION,
        "claimed_at": datetime.now(timezone.utc).isoformat(),
        "expected_head": spec.expected_head,
        "expected_snapshot": spec.expected_snapshot,
        "expected_release_state_sha256": spec.expected_release_state_sha256,
        "expected_release_audit_sha256": spec.expected_release_audit_sha256,
        "image": spec.image,
        "scope_sha256": spec.scope_sha256,
    }
    (spec.output_root / "claim.json").write_text(
        json.dumps(claim, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    docker = client or DockerClient()
    project = f"shaiwei-r2d-r3a-{spec.scope_sha256[:10]}"
    compose_env = _compose_environment(spec)
    production_paths = {
        "release_state": release.STATE_PATH,
        "release_audit": release.AUDIT_PATH,
    }
    before = {name: _sha256(path) for name, path in production_paths.items()}
    expected_before = {
        "release_state": spec.expected_release_state_sha256,
        "release_audit": spec.expected_release_audit_sha256,
    }
    candidate: dict[str, object] = {}
    cases: list[dict[str, str]] = []
    failure = ""
    compose_invoked = False
    try:
        if before != expected_before:
            raise FixtureError("production release evidence differs from the frozen scope")
        cases.append({"case": "production_release_evidence_matches_scope", "status": "PASS"})

        metadata = release._image_metadata(spec.image)
        if (
            metadata.get("git_head") != spec.expected_head
            or metadata.get("code_snapshot_sha256") != spec.expected_snapshot
            or metadata.get("lock_authority") != LOCK_AUTHORITY
        ):
            raise FixtureError("candidate image labels differ from the frozen identity")
        candidate.update(metadata)
        cases.append({"case": "candidate_image_labels", "status": "PASS"})

        compose_invoked = True
        docker.run(
            _compose_command(project, "up", "-d", "--pull", "never", "--no-deps", "scheduler"),
            env=compose_env,
        )
        container_id = docker.run(
            _compose_command(project, "ps", "-q", "scheduler"), env=compose_env
        ).stdout.strip()
        if not container_id:
            raise FixtureError("fixture scheduler container is missing")
        initial_health = _docker_health(docker, container_id)
        if initial_health != "starting":
            raise FixtureError("fixture did not observe Docker health starting state")
        cases.append({"case": "docker_health_starting_observed", "status": "PASS"})

        contract = release._wait_scheduler_contract(
            metadata,
            timeout_seconds=60,
            container_id=container_id,
        )
        if contract.get("health") != "healthy":
            raise FixtureError("shared release contract did not converge to healthy")
        candidate["contract"] = contract
        cases.append({"case": "shared_release_contract_converged", "status": "PASS"})

        candidate_identity = guard.ReleaseIdentity(
            image=spec.image,
            image_id=str(metadata["image_id"]),
            code_snapshot_sha256=spec.expected_snapshot,
            git_head=spec.expected_head,
            lock_authority=LOCK_AUTHORITY,
        )
        environment = _GuardEnvironment(candidate_identity, contract)
        protocol = SimpleNamespace(
            candidate=candidate_identity,
            expected_running_release=environment.old,
        )
        guard._execute_action(protocol, environment, "RESUME_START")
        if environment.rollback_calls:
            raise FixtureError("successful guard path invoked rollback")
        cases.append({"case": "guard_success_path_without_rollback", "status": "PASS"})
    except Exception as error:
        failure = type(error).__name__
        cases.append({"case": "fixture_terminal", "status": "FAIL", "error_type": failure})
    finally:
        if compose_invoked:
            docker.run(_compose_command(project, "down", "--remove-orphans"), env=compose_env, check=False)

    after = {name: _sha256(path) for name, path in production_paths.items()}
    if before != after and not failure:
        failure = "ProductionEvidenceChanged"
        cases.append(
            {"case": "production_release_evidence_unchanged", "status": "FAIL", "error_type": failure}
        )
    elif before == after:
        cases.append({"case": "production_release_evidence_unchanged", "status": "PASS"})
    report = _write_report(
        spec,
        candidate=candidate,
        cases=cases,
        command_count=docker.command_count,
        production_before=before,
        production_after=after,
        failure=failure,
    )
    if report["verdict"] != "PASS":
        raise FixtureError(f"R2D-R3A fixture failed closed: {failure}")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True)
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--expected-snapshot", required=True)
    parser.add_argument("--scope-sha256", required=True)
    parser.add_argument("--expected-release-state-sha256", required=True)
    parser.add_argument("--expected-release-audit-sha256", required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args(argv)
    report = execute(FixtureSpec(**vars(args)))
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
