"""One-shot host orchestrator for the R2C Docker named-volume lock fixture."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import time
from typing import Callable

from shaiwei.config import PROJECT_ROOT
from shaiwei.release import LOCK_AUTHORITY_LABEL, REVISION_LABEL, SNAPSHOT_LABEL
from shaiwei.runtime_lock_fixture_payloads import (
    HOLDER,
    LEDGER,
    MISSING_MOUNT,
    PROBE,
    READONLY_MOUNT,
    RESOURCE_RULES,
)
from shaiwei.storage.runtime_mount_contract import (
    LOCK_AUTHORITY,
    LOCK_VOLUME_DESTINATION,
    LOCK_VOLUME_NAME,
    RuntimeMountContractError,
    validate_scheduler_mounts,
)


ACTION = "R2C_RUNTIME_LOCK_NAMED_VOLUME_FIXTURE_ONCE"
SCHEMA = "shaiwei-runtime-lock-docker-fixture-report-v1"
OUTPUT_PREFIX = PROJECT_ROOT / ".release" / "runtime-lock-fixture-r2c"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_GIT_REVISION = re.compile(r"^[0-9a-f]{40}$")


class FixtureError(RuntimeError):
    pass


@dataclass(frozen=True)
class FixtureSpec:
    image: str
    expected_head: str
    expected_snapshot: str
    scope_sha256: str
    output_root: Path
    lock_volume: str = LOCK_VOLUME_NAME

    def validate(self) -> None:
        if _GIT_REVISION.fullmatch(self.expected_head) is None:
            raise FixtureError("expected Git HEAD is invalid")
        if _SHA256.fullmatch(self.expected_snapshot) is None:
            raise FixtureError("expected code snapshot is invalid")
        if _SHA256.fullmatch(self.scope_sha256) is None:
            raise FixtureError("scope SHA-256 is invalid")
        expected_image = f"shaiwei:scheduler-{self.expected_snapshot[:16]}"
        if self.image != expected_image:
            raise FixtureError("candidate tag differs from the content-addressed tag")
        if self.lock_volume != LOCK_VOLUME_NAME:
            raise FixtureError("lock volume differs from the frozen authority")
        resolved, prefix = self.output_root.resolve(strict=False), OUTPUT_PREFIX.resolve(strict=False)
        if resolved.parent != prefix or resolved.name != self.scope_sha256[:16]:
            raise FixtureError("fixture output root is outside the one-shot scope")
        if self.output_root.exists():
            raise FixtureError("fixture scope already has evidence and cannot be rerun")


class DockerClient:
    def __init__(self, runner: Callable[..., subprocess.CompletedProcess[str]] | None = None):
        self._runner = runner or subprocess.run
        self.command_count = 0

    def run(self, argv: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
        self.command_count += 1
        try:
            return self._runner(
                argv,
                cwd=PROJECT_ROOT,
                check=check,
                capture_output=True,
                text=True,
                timeout=120,
            )
        except subprocess.CalledProcessError as error:
            detail = (error.stderr or error.stdout or "").strip()
            raise FixtureError(f"Docker fixture command failed: {argv[:3]}: {detail}") from error


def _security_args() -> list[str]:
    return [
        "--network", "none", "--read-only", "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges", "--pids-limit", "128",
        "--memory", "2g", "--cpus", "2", "--tmpfs", "/tmp:rw,noexec,nosuid,size=256m,mode=1777",
    ]


def _runtime_args(spec: FixtureSpec, *, lock_mode: str = "rw") -> list[str]:
    if lock_mode not in {"rw", "ro"}:
        raise FixtureError("unknown fixture lock mount mode")
    lock_mount = f"type=volume,src={spec.lock_volume},dst={LOCK_VOLUME_DESTINATION}"
    if lock_mode == "ro":
        lock_mount += ",readonly"
    return [
        *_security_args(),
        "--env", f"SHAIWEI_LOCK_AUTHORITY={LOCK_AUTHORITY}",
        "--env", f"SHAIWEI_LOCK_ROOT={LOCK_VOLUME_DESTINATION}",
        "--mount",
        lock_mount,
        "--mount", f"type=bind,src={spec.output_root},dst=/fixture",
    ]


def _candidate_run(
    client: DockerClient,
    spec: FixtureSpec,
    command: list[str],
    *,
    lock_mode: str = "rw",
    extra: list[str] | None = None,
) -> subprocess.CompletedProcess[str]:
    argv = ["docker", "run", "--rm", *_runtime_args(spec, lock_mode=lock_mode)]
    return client.run([*argv, *(extra or []), spec.image, *command])


def _image_identity(client: DockerClient, spec: FixtureSpec) -> dict[str, str]:
    template = (
        "{{.Id}}\t{{index .Config.Labels \"" + SNAPSHOT_LABEL + "\"}}\t"
        "{{index .Config.Labels \"" + REVISION_LABEL + "\"}}\t"
        "{{index .Config.Labels \"" + LOCK_AUTHORITY_LABEL + "\"}}"
    )
    line = client.run(["docker", "image", "inspect", "--format", template, spec.image]).stdout.strip()
    parts = line.split("\t")
    if len(parts) != 4:
        raise FixtureError("candidate image identity is incomplete")
    identity = dict(zip(("image_id", "snapshot", "head", "lock_authority"), parts, strict=True))
    if identity["snapshot"] != spec.expected_snapshot or identity["head"] != spec.expected_head:
        raise FixtureError("candidate image labels differ from the frozen identity")
    if identity["lock_authority"] != LOCK_AUTHORITY or not identity["image_id"].startswith("sha256:"):
        raise FixtureError("candidate image lock authority or image ID is invalid")
    code = (
        "import json; from shaiwei.provenance import code_snapshot_sha256,git_head; "
        "print(json.dumps({'snapshot':code_snapshot_sha256(),'head':git_head()}))"
    )
    runtime = json.loads(client.run([
        "docker", "run", "--rm", *_security_args(), spec.image, "python", "-c", code,
    ]).stdout.strip())
    if runtime != {"snapshot": spec.expected_snapshot, "head": spec.expected_head}:
        raise FixtureError("candidate runtime identity differs from the frozen identity")
    return identity


def _thread_concurrency(client: DockerClient, spec: FixtureSpec) -> None:
    test = "tests/test_interprocess_lock.py::test_thread_layer_serializes_even_when_flock_is_ineffective"
    _candidate_run(client, spec, ["python", "-m", "pytest", "-q", "-p", "no:cacheprovider", test])


def _timeline_processes(client: DockerClient, spec: FixtureSpec) -> None:
    test = "tests/test_scheduler_timeline.py::test_independent_processes_produce_one_valid_chain"
    _candidate_run(client, spec, ["python", "-m", "pytest", "-q", "-p", "no:cacheprovider", test])


def _wait_for(path: Path) -> None:
    deadline = time.monotonic() + 15
    while not path.exists():
        if time.monotonic() > deadline:
            raise FixtureError(f"container gate timed out: {path.name}")
        time.sleep(0.02)


def _require_container_absent(client: DockerClient, name: str) -> None:
    command = ["docker", "container", "inspect", "--format", "{{.Id}}", name]
    result = client.run(command, check=False)
    if result.returncode == 0:
        raise FixtureError(f"fixture container name already exists: {name}")


def _start_holder(
    client: DockerClient, spec: FixtureSpec, name: str, resource: str, mode: str
) -> tuple[str, Path]:
    ready = spec.output_root / f"{name}.ready"
    release = spec.output_root / f"{name}.release"
    _require_container_absent(client, name)
    container_id = client.run([
        "docker", "run", "-d", "--name", name, *_runtime_args(spec), spec.image,
        "python", "-c", HOLDER, resource, mode, f"/fixture/{ready.name}",
        f"/fixture/{release.name}",
    ]).stdout.strip()
    try:
        _wait_for(ready)
    except Exception:
        client.run(["docker", "rm", "-f", name], check=False)
        raise
    return container_id, release


def _probe(client: DockerClient, spec: FixtureSpec, resource: str, mode: str, expected: str) -> None:
    _candidate_run(client, spec, ["python", "-c", PROBE, resource, mode, expected])


def _container_matrix(client: DockerClient, spec: FixtureSpec) -> None:
    names: list[str] = []
    try:
        ex_name = f"shaiwei-r2c-ex-{spec.scope_sha256[:10]}"
        _container, release = _start_holder(client, spec, ex_name, "runtime:daily-cycle", "exclusive")
        names.append(ex_name)
        _probe(client, spec, "runtime:daily-cycle", "exclusive", "busy")
        _probe(client, spec, "runtime:daily-cycle", "shared", "busy")
        release.write_text("release", encoding="utf-8")
        client.run(["docker", "wait", ex_name])

        sh_name = f"shaiwei-r2c-sh-{spec.scope_sha256[:10]}"
        _container, release = _start_holder(
            client, spec, sh_name, "runtime:scheduler-timeline:20991230", "shared"
        )
        names.append(sh_name)
        _probe(client, spec, "runtime:scheduler-timeline:20991230", "shared", "acquired")
        _probe(client, spec, "runtime:scheduler-timeline:20991230", "exclusive", "busy")
        release.write_text("release", encoding="utf-8")
        client.run(["docker", "wait", sh_name])
    finally:
        for name in names:
            client.run(["docker", "rm", "-f", name], check=False)


def _sigkill_release(client: DockerClient, spec: FixtureSpec) -> None:
    name = f"shaiwei-r2c-kill-{spec.scope_sha256[:10]}"
    try:
        _container, _release = _start_holder(client, spec, name, "runtime:shadow-cycle", "exclusive")
        client.run(["docker", "kill", "--signal", "KILL", name])
        client.run(["docker", "wait", name], check=False)
        inspect_code = (
            "from pathlib import Path; p=Path('/run/shaiwei-locks'); "
            "rows=[x.read_text().strip() for x in p.glob('*.lock')]; "
            "assert 'runtime:shadow-cycle' in rows; print(len(rows))"
        )
        _candidate_run(client, spec, ["python", "-c", inspect_code])
        _probe(client, spec, "runtime:shadow-cycle", "exclusive", "acquired")
    finally:
        client.run(["docker", "rm", "-f", name], check=False)


def _ledger_concurrency(client: DockerClient, spec: FixtureSpec) -> None:
    _candidate_run(
        client,
        spec,
        ["python", "-c", LEDGER],
        extra=["--mount", f"type=bind,src={spec.output_root},dst=/workspace/ledger"],
    )


def _missing_mount(client: DockerClient, spec: FixtureSpec) -> None:
    client.run([
        "docker", "run", "--rm", *_security_args(),
        "--env", f"SHAIWEI_LOCK_AUTHORITY={LOCK_AUTHORITY}",
        "--env", f"SHAIWEI_LOCK_ROOT={LOCK_VOLUME_DESTINATION}", spec.image,
        "python", "-c", MISSING_MOUNT,
    ])


def _readonly_mount(client: DockerClient, spec: FixtureSpec) -> None:
    _candidate_run(client, spec, ["python", "-c", READONLY_MOUNT], lock_mode="ro")


def _resource_failures(client: DockerClient, spec: FixtureSpec) -> None:
    _candidate_run(client, spec, ["python", "-c", RESOURCE_RULES])


def _wrong_volume_metadata(client: DockerClient, spec: FixtureSpec) -> None:
    wrong = f"shaiwei_r2c_wrong_{spec.scope_sha256[:12]}"
    name = f"shaiwei-r2c-wrong-{spec.scope_sha256[:10]}"
    command = ["docker", "volume", "inspect", "--format", "{{.Name}}", wrong]
    existing = client.run(command, check=False)
    if existing.returncode == 0:
        raise FixtureError("scope-specific wrong-volume name already exists")
    _require_container_absent(client, name)
    client.run(["docker", "volume", "create", wrong])
    container_created = False
    try:
        container = client.run([
            "docker", "run", "-d", "--name", name, *_security_args(),
            "--mount", f"type=volume,src={wrong},dst={LOCK_VOLUME_DESTINATION}",
            spec.image, "python", "-c", "import time; time.sleep(30)",
        ]).stdout.strip()
        container_created = True
        mounts = json.loads(client.run([
            "docker", "inspect", "--format", "{{json .Mounts}}", container,
        ]).stdout)
        lock_mount = next(x for x in mounts if x.get("Destination") == LOCK_VOLUME_DESTINATION)
        synthetic = [
            {"Destination": path, "RW": True, "Type": "bind"}
            for path in ("/workspace/data", "/workspace/ledger", "/workspace/logs")
        ]
        try:
            validate_scheduler_mounts([*synthetic, lock_mount], lock_required=True)
        except RuntimeMountContractError:
            pass
        else:
            raise FixtureError("real wrong-volume metadata passed the release contract")
    finally:
        if container_created:
            client.run(["docker", "rm", "-f", name], check=False)
        client.run(["docker", "volume", "rm", wrong], check=False)


def _write_tree_manifest(root: Path) -> str:
    rows = []
    for path in sorted(x for x in root.rglob("*") if x.is_file() and x.name != "tree.json"):
        rows.append({
            "path": path.relative_to(root).as_posix(),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "bytes": path.stat().st_size,
        })
    payload = json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    (root / "tree.json").write_text(
        json.dumps({"files": rows, "tree_sha256": digest}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return digest


def execute(spec: FixtureSpec, *, client: DockerClient | None = None) -> dict[str, object]:
    spec.validate()
    spec.output_root.mkdir(parents=True)
    claim = {
        "action": ACTION,
        "claimed_at": datetime.now(timezone.utc).isoformat(),
        "expected_head": spec.expected_head,
        "expected_snapshot": spec.expected_snapshot,
        "image": spec.image,
        "scope_sha256": spec.scope_sha256,
    }
    (spec.output_root / "claim.json").write_text(
        json.dumps(claim, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    docker = client or DockerClient()
    cases: list[dict[str, str]] = []
    identity: dict[str, str] = {}
    checks: list[tuple[str, Callable[[], object]]] = [
        ("exact_image_label_and_runtime_identity", lambda: identity.update(_image_identity(docker, spec))),
        ("eight_threads_with_noop_flock", lambda: _thread_concurrency(docker, spec)),
        ("four_independent_timeline_processes", lambda: _timeline_processes(docker, spec)),
        ("two_container_exclusive_shared_nonblocking_matrix", lambda: _container_matrix(docker, spec)),
        ("sigkill_releases_kernel_lock_without_lockfile_deletion", lambda: _sigkill_release(docker, spec)),
        ("eight_process_canonical_ledger_append_and_collision", lambda: _ledger_concurrency(docker, spec)),
        ("missing_mount_fails_closed", lambda: _missing_mount(docker, spec)),
        ("readonly_mount_fails_closed", lambda: _readonly_mount(docker, spec)),
        ("real_wrong_volume_metadata_rejected_by_release_contract", lambda: _wrong_volume_metadata(docker, spec)),
        ("unknown_resource_order_and_reentrancy_fail_closed", lambda: _resource_failures(docker, spec)),
    ]
    failure = ""
    for name, check in checks:
        try:
            check()
            cases.append({"case": name, "status": "PASS"})
        except Exception as error:  # evidence must survive every fail-closed path
            failure = type(error).__name__
            cases.append({"case": name, "status": "FAIL", "error_type": failure})
            break
    report: dict[str, object] = {
        "schema_version": SCHEMA,
        "action": ACTION,
        "scope_sha256": spec.scope_sha256,
        "candidate": identity,
        "command_count": docker.command_count,
        "cases": cases,
        "verdict": "PASS" if not failure and len(cases) == len(checks) else "FAIL",
        "error_type": failure,
        "production_authorization": "none",
    }
    report_path = spec.output_root / "report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report["report_sha256"] = hashlib.sha256(report_path.read_bytes()).hexdigest()
    report["evidence_tree_sha256"] = _write_tree_manifest(spec.output_root)
    if report["verdict"] != "PASS":
        raise FixtureError(f"R2C fixture failed closed: {failure}")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True)
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--expected-snapshot", required=True)
    parser.add_argument("--scope-sha256", required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args(argv)
    report = execute(FixtureSpec(**vars(args)))
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
