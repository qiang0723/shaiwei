"""Build, promote, inspect, and roll back immutable scheduler release images."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import uuid
from datetime import datetime, timezone

from shaiwei.config import PROJECT_ROOT
from shaiwei.provenance import code_snapshot_sha256, git_head


STATE_DIR = PROJECT_ROOT / ".release"
STATE_PATH = STATE_DIR / "scheduler_state.json"
AUDIT_PATH = PROJECT_ROOT / "logs" / "releases" / "scheduler_releases.jsonl"
CURRENT_ALIAS = "shaiwei:scheduler-current"
PREVIOUS_ALIAS = "shaiwei:scheduler-previous"
CONTENT_TAG_PREFIX = "shaiwei:scheduler-"
SNAPSHOT_LABEL = "io.shaiwei.code_snapshot_sha256"
STATE_SCHEMA = "shaiwei-scheduler-release-state-v1"
AUDIT_SCHEMA = "shaiwei-scheduler-release-audit-v1"


class ReleaseError(RuntimeError):
    pass


def _run(argv: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            argv,
            cwd=PROJECT_ROOT,
            check=check,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as error:
        detail = (error.stderr or error.stdout or "").strip()
        raise ReleaseError(f"command failed: {' '.join(argv)}: {detail}") from error


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _write_json_atomic(path: Path, document: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(
            json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        with temporary.open("rb") as handle:
            os.fsync(handle.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _validate_audit_chain(path: Path | None = None) -> list[dict[str, object]]:
    path = path or AUDIT_PATH
    if not path.is_file():
        return []
    records: list[dict[str, object]] = []
    previous = ""
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        try:
            record = json.loads(line)
        except json.JSONDecodeError as error:
            raise ReleaseError(f"release audit line {line_number} is invalid JSON") from error
        if not isinstance(record, dict) or record.get("schema_version") != AUDIT_SCHEMA:
            raise ReleaseError(f"release audit line {line_number} has an invalid schema")
        if record.get("previous_record_sha256") != previous:
            raise ReleaseError(f"release audit chain breaks at line {line_number}")
        expected = str(record.get("record_sha256", ""))
        unsigned = {key: value for key, value in record.items() if key != "record_sha256"}
        actual = hashlib.sha256(_canonical(unsigned)).hexdigest()
        if expected != actual:
            raise ReleaseError(f"release audit hash differs at line {line_number}")
        previous = actual
        records.append(record)
    return records


def _append_audit(event: str, details: dict[str, object]) -> dict[str, object]:
    records = _validate_audit_chain()
    previous = str(records[-1]["record_sha256"]) if records else ""
    unsigned: dict[str, object] = {
        "schema_version": AUDIT_SCHEMA,
        "event": event,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "git_head": git_head(),
        "previous_record_sha256": previous,
        "details": details,
    }
    record = {
        **unsigned,
        "record_sha256": hashlib.sha256(_canonical(unsigned)).hexdigest(),
    }
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with AUDIT_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return record


def _load_state(path: Path | None = None) -> dict[str, object] | None:
    path = path or STATE_PATH
    if not path.is_file():
        return None
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ReleaseError("scheduler release state is invalid JSON") from error
    if not isinstance(document, dict) or document.get("schema_version") != STATE_SCHEMA:
        raise ReleaseError("scheduler release state schema is invalid")
    return document


def _image_document(image: str) -> dict[str, object]:
    result = _run(["docker", "image", "inspect", image])
    try:
        documents = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise ReleaseError(f"docker returned invalid image metadata: {image}") from error
    if not isinstance(documents, list) or len(documents) != 1 or not isinstance(documents[0], dict):
        raise ReleaseError(f"docker image metadata is ambiguous: {image}")
    return documents[0]


def _image_metadata(image: str) -> dict[str, str]:
    document = _image_document(image)
    config = document.get("Config")
    labels = config.get("Labels", {}) if isinstance(config, dict) else {}
    if not isinstance(labels, dict):
        labels = {}
    image_id = str(document.get("Id", ""))
    snapshot = str(labels.get(SNAPSHOT_LABEL, ""))
    if not image_id.startswith("sha256:") or len(snapshot) != 64:
        raise ReleaseError(f"image lacks immutable scheduler release metadata: {image}")
    return {"image": image, "image_id": image_id, "code_snapshot_sha256": snapshot}


def _image_runtime_snapshot(image: str) -> str:
    code = "from shaiwei.provenance import code_snapshot_sha256; print(code_snapshot_sha256())"
    result = _run(
        [
            "docker",
            "run",
            "--rm",
            "--read-only",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=64m",
            "--entrypoint",
            "python",
            image,
            "-c",
            code,
        ]
    )
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if not lines or len(lines[-1]) != 64:
        raise ReleaseError(f"image did not return a valid runtime snapshot: {image}")
    return lines[-1]


def verify_image(image: str) -> dict[str, str]:
    metadata = _image_metadata(image)
    runtime_snapshot = _image_runtime_snapshot(image)
    if runtime_snapshot != metadata["code_snapshot_sha256"]:
        raise ReleaseError("image label and verified runtime snapshot differ")
    return metadata


def _require_clean_worktree() -> None:
    if _run(["git", "status", "--porcelain"]).stdout.strip():
        raise ReleaseError("release build requires a clean Git worktree")


def build_image() -> dict[str, object]:
    _require_clean_worktree()
    snapshot = code_snapshot_sha256()
    image = f"{CONTENT_TAG_PREFIX}{snapshot[:16]}"
    _run(
        [
            "docker",
            "build",
            "--label",
            f"{SNAPSHOT_LABEL}={snapshot}",
            "--label",
            f"org.opencontainers.image.revision={git_head()}",
            "--tag",
            image,
            ".",
        ]
    )
    metadata = verify_image(image)
    if metadata["code_snapshot_sha256"] != snapshot:
        raise ReleaseError("built image snapshot differs from the clean worktree")
    record = _append_audit("BUILD_PASS", metadata)
    return {**metadata, "audit_record_sha256": record["record_sha256"]}


def _tag(source: str, target: str) -> None:
    _run(["docker", "tag", source, target])


def _state_for(
    current: dict[str, str],
    previous: dict[str, str] | None,
) -> dict[str, object]:
    return {
        "schema_version": STATE_SCHEMA,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "current": current,
        "previous": previous,
    }


def _compose_container_id() -> str:
    container_id = _run(["docker", "compose", "ps", "-q", "scheduler"]).stdout.strip()
    if not container_id:
        raise ReleaseError("scheduler container is not running")
    return container_id


def _container_contract(expected: dict[str, str]) -> dict[str, object]:
    container_id = _compose_container_id()
    result = _run(["docker", "inspect", container_id])
    try:
        documents = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise ReleaseError("scheduler inspect output is invalid JSON") from error
    document = documents[0]
    if str(document.get("Image")) != expected["image_id"]:
        raise ReleaseError("scheduler container is not running the promoted image ID")
    host = document.get("HostConfig")
    if not isinstance(host, dict) or host.get("ReadonlyRootfs") is not True:
        raise ReleaseError("scheduler root filesystem is not read-only")
    mounts = document.get("Mounts")
    if not isinstance(mounts, list):
        raise ReleaseError("scheduler mounts are missing")
    destinations = {
        str(mount.get("Destination")): mount
        for mount in mounts
        if isinstance(mount, dict)
    }
    expected_destinations = {
        "/workspace/data",
        "/workspace/ledger",
        "/workspace/logs",
    }
    if set(destinations) != expected_destinations:
        raise ReleaseError("scheduler mounts differ from the explicit production allowlist")
    if any(mount.get("RW") is not True for mount in destinations.values()):
        raise ReleaseError("scheduler persistence mounts must remain writable")
    if any(str(mount.get("Destination")) == "/workspace" for mount in mounts):
        raise ReleaseError("scheduler still mounts a host directory over /workspace")
    runtime_snapshot = _run(
        [
            "docker",
            "exec",
            container_id,
            "python",
            "-c",
            "from shaiwei.provenance import code_snapshot_sha256; print(code_snapshot_sha256())",
        ]
    ).stdout.strip()
    if runtime_snapshot != expected["code_snapshot_sha256"]:
        raise ReleaseError("running scheduler snapshot differs from the promoted release")
    return {
        "container_id": container_id,
        "image_id": expected["image_id"],
        "code_snapshot_sha256": runtime_snapshot,
        "read_only_rootfs": True,
        "mount_destinations": sorted(destinations),
    }


def _wait_scheduler_contract(
    expected: dict[str, str],
    *,
    timeout_seconds: int = 60,
) -> dict[str, object]:
    deadline = time.monotonic() + timeout_seconds
    last_error = ""
    while time.monotonic() < deadline:
        try:
            contract = _container_contract(expected)
            container_id = str(contract["container_id"])
            health = _run(
                [
                    "docker",
                    "exec",
                    container_id,
                    "python",
                    "-m",
                    "shaiwei.pipeline.scheduler",
                    "--healthcheck",
                ],
                check=False,
            )
            if health.returncode == 0:
                return contract
            last_error = "scheduler healthcheck is not ready"
        except ReleaseError as error:
            last_error = str(error)
        time.sleep(1)
    raise ReleaseError(f"scheduler did not satisfy the release contract: {last_error}")


def start_current() -> dict[str, object]:
    state = _load_state()
    if state is None or not isinstance(state.get("current"), dict):
        raise ReleaseError("no promoted scheduler release exists")
    expected = dict(state["current"])
    _tag(str(expected["image"]), CURRENT_ALIAS)
    _run(
        [
            "docker",
            "compose",
            "up",
            "-d",
            "--force-recreate",
            "--no-deps",
            "scheduler",
        ]
    )
    contract = _wait_scheduler_contract(expected)
    record = _append_audit("START_PASS", contract)
    return {**contract, "audit_record_sha256": record["record_sha256"]}


def promote(image: str, *, start: bool) -> dict[str, object]:
    candidate = verify_image(image)
    state = _load_state()
    previous_current = (
        dict(state["current"])
        if state is not None and isinstance(state.get("current"), dict)
        else None
    )
    _tag(image, CURRENT_ALIAS)
    if previous_current is not None:
        _tag(str(previous_current["image"]), PREVIOUS_ALIAS)
    new_state = _state_for(candidate, previous_current)
    _write_json_atomic(STATE_PATH, new_state)
    details: dict[str, object] = {
        "current": candidate,
        "previous": previous_current,
        "started": start,
    }
    try:
        contract = start_current() if start else None
    except Exception:
        if previous_current is not None:
            _tag(str(previous_current["image"]), CURRENT_ALIAS)
            _write_json_atomic(STATE_PATH, state)
        else:
            STATE_PATH.unlink(missing_ok=True)
        _append_audit("PROMOTE_FAILED_ROLLED_BACK", details)
        raise
    record = _append_audit("PROMOTE_PASS", {**details, "contract": contract})
    return {
        **details,
        "contract": contract,
        "audit_record_sha256": record["record_sha256"],
    }


def rollback(*, start: bool) -> dict[str, object]:
    state = _load_state()
    if (
        state is None
        or not isinstance(state.get("current"), dict)
        or not isinstance(state.get("previous"), dict)
    ):
        raise ReleaseError("rollback requires distinct current and previous releases")
    current = dict(state["current"])
    previous = verify_image(str(dict(state["previous"])["image"]))
    _tag(str(previous["image"]), CURRENT_ALIAS)
    _tag(str(current["image"]), PREVIOUS_ALIAS)
    rolled_back = _state_for(previous, current)
    _write_json_atomic(STATE_PATH, rolled_back)
    details: dict[str, object] = {
        "current": previous,
        "previous": current,
        "started": start,
    }
    try:
        contract = start_current() if start else None
    except Exception:
        _tag(str(current["image"]), CURRENT_ALIAS)
        _write_json_atomic(STATE_PATH, state)
        _append_audit("ROLLBACK_FAILED_RESTORED", details)
        raise
    record = _append_audit("ROLLBACK_PASS", {**details, "contract": contract})
    return {
        **details,
        "contract": contract,
        "audit_record_sha256": record["record_sha256"],
    }


def status() -> dict[str, object]:
    records = _validate_audit_chain()
    return {
        "status": "PASS",
        "state": _load_state(),
        "audit_record_count": len(records),
        "audit_tip_sha256": records[-1]["record_sha256"] if records else "",
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("build")
    promote_parser = subparsers.add_parser("promote")
    promote_parser.add_argument("--image", required=True)
    promote_parser.add_argument("--no-start", action="store_true")
    rollback_parser = subparsers.add_parser("rollback")
    rollback_parser.add_argument("--no-start", action="store_true")
    subparsers.add_parser("start")
    subparsers.add_parser("status")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.command == "build":
        document = build_image()
    elif args.command == "promote":
        document = promote(args.image, start=not args.no_start)
    elif args.command == "rollback":
        document = rollback(start=not args.no_start)
    elif args.command == "start":
        document = start_current()
    else:
        document = status()
    print(json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
