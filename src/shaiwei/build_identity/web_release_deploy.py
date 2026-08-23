"""Local-only promotion, rollback drill, and runtime checks for Web releases."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
from typing import Mapping

from shaiwei.build_identity.registry import PROJECT_ROOT
from shaiwei.build_identity.web_release_build import (
    load_and_verify_candidate,
)
from shaiwei.build_identity.web_release_config import (
    WebReleaseConfig,
    WebReleaseError,
    load_web_release_config,
)
from shaiwei.build_identity.web_release_runtime import (
    WEB_SERVICES,
    container_identity,
    scheduler_identity,
    validate_container_contract,
    verify_read_only_http,
    wait_and_verify_runtime,
)
from shaiwei.build_identity.web_release_state import (
    STATE_SCHEMA,
    archive_release_state,
    load_release_state,
    release_images,
    write_release_state,
)


AUDIT_SCHEMA = "shaiwei-web-component-release-audit-v1"


def _run(
    argv: list[str],
    *,
    root: Path,
    check: bool = True,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        argv,
        cwd=root,
        capture_output=True,
        text=True,
        env=env,
    )
    if check and result.returncode:
        detail = (result.stderr or result.stdout).strip()[-4000:]
        raise WebReleaseError(f"command failed: {' '.join(argv)}: {detail}")
    return result


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _audit_records(path: Path) -> list[dict[str, object]]:
    if not path.is_file():
        return []
    records: list[dict[str, object]] = []
    previous = ""
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        try:
            record = json.loads(line)
        except json.JSONDecodeError as error:
            raise WebReleaseError(f"Web release audit line is invalid: {line_number}") from error
        if not isinstance(record, dict) or record.get("schema_version") != AUDIT_SCHEMA:
            raise WebReleaseError(f"Web release audit schema differs: {line_number}")
        expected = record.get("record_sha256")
        unsigned = {key: value for key, value in record.items() if key != "record_sha256"}
        actual = hashlib.sha256(_canonical(unsigned)).hexdigest()
        if record.get("previous_record_sha256") != previous or expected != actual:
            raise WebReleaseError(f"Web release audit chain differs: {line_number}")
        previous = actual
        records.append(record)
    return records


def _append_audit(path: Path, event: str, details: Mapping[str, object]) -> str:
    records = _audit_records(path)
    previous = str(records[-1]["record_sha256"]) if records else ""
    unsigned: dict[str, object] = {
        "schema_version": AUDIT_SCHEMA,
        "event": event,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "previous_record_sha256": previous,
        "details": dict(details),
    }
    record = {**unsigned, "record_sha256": hashlib.sha256(_canonical(unsigned)).hexdigest()}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return str(record["record_sha256"])


def _candidate_images(candidate: Mapping[str, object]) -> dict[str, dict[str, str]]:
    attestation = candidate.get("attestation")
    if not isinstance(attestation, dict) or not isinstance(attestation.get("images"), list):
        raise WebReleaseError("Web candidate images are invalid")
    return {
        str(row["role"]): {
            "reference": str(row["image_reference"]),
            "image_id": str(row["image_id"]),
        }
        for row in attestation["images"]
    }


def _service_image_ids(images: Mapping[str, Mapping[str, str]]) -> dict[str, str]:
    return {
        "web-query": images["web-runtime"]["image_id"],
        "web-ui": images["web-runtime"]["image_id"],
        "research-control": images["research-control"]["image_id"],
    }


def _compose_env(images: Mapping[str, Mapping[str, str]]) -> dict[str, str]:
    return {
        **os.environ,
        "SHAIWEI_WEB_RUNTIME_IMAGE": images["web-runtime"]["reference"],
        "SHAIWEI_WEB_CONTROL_IMAGE": images["research-control"]["reference"],
    }


def _deploy(
    root: Path,
    config: WebReleaseConfig,
    images: Mapping[str, Mapping[str, str]],
) -> dict[str, dict[str, object]]:
    _run(
        [
            "docker",
            "compose",
            "-f",
            config.compose_path,
            "--profile",
            "web",
            "up",
            "-d",
            "--no-build",
            "--force-recreate",
            *WEB_SERVICES,
        ],
        root=root,
        env=_compose_env(images),
    )
    return wait_and_verify_runtime(root, config, _service_image_ids(images))


def _legacy_images(root: Path, config: WebReleaseConfig) -> tuple[dict[str, dict[str, str]], dict[str, str]]:
    identities = {service: container_identity(root, config, service) for service in WEB_SERVICES}
    if identities["web-query"]["image_id"] != identities["web-ui"]["image_id"]:
        raise WebReleaseError("legacy Web query and UI image identities differ")
    for service, identity in identities.items():
        validate_container_contract(service, identity, str(identity["image_id"]))
    roles = {
        "web-runtime": str(identities["web-query"]["image_id"]),
        "research-control": str(identities["research-control"]["image_id"]),
    }
    images: dict[str, dict[str, str]] = {}
    for role, image_id in roles.items():
        reference = f"shaiwei:{role}-legacy-{image_id.removeprefix('sha256:')[:16]}"
        _run(["docker", "image", "tag", image_id, reference], root=root)
        images[role] = {"reference": reference, "image_id": image_id}
    container_ids = {service: str(identity["container_id"]) for service, identity in identities.items()}
    return images, container_ids


def _deployed_baseline(
    root: Path,
    config: WebReleaseConfig,
    state: Mapping[str, object],
) -> tuple[dict[str, dict[str, str]], dict[str, str]]:
    images = release_images(state)
    identities = wait_and_verify_runtime(root, config, _service_image_ids(images), timeout_seconds=15)
    verify_read_only_http(config, critical=False)
    if scheduler_identity(root) != state.get("scheduler_identity"):
        raise WebReleaseError("scheduler identity differs from previous Web release state")
    containers = {service: str(identity["container_id"]) for service, identity in identities.items()}
    return images, containers


def promote_with_rollback_drill(*, root: Path | None = None) -> dict[str, object]:
    project_root = (root or PROJECT_ROOT).resolve()
    config = load_web_release_config(root=project_root)
    candidate = load_and_verify_candidate(root=project_root)
    scheduler_before = candidate.get("scheduler_identity_before")
    if scheduler_identity(project_root) != scheduler_before:
        raise WebReleaseError("scheduler changed after Web candidate build")
    state_path, audit_path = project_root / config.state_path, project_root / config.audit_path
    previous_state = load_release_state(state_path, required=False)
    if previous_state is None:
        previous_images, previous_containers = _legacy_images(project_root, config)
        generation = 1
        start_event = "MIGRATION_STARTED"
    else:
        previous_images, previous_containers = _deployed_baseline(
            project_root,
            config,
            previous_state,
        )
        generation = int(previous_state.get("release_generation", 1)) + 1
        start_event = "SUCCESSOR_STARTED"
    candidate_images = _candidate_images(candidate)
    _append_audit(
        audit_path,
        start_event,
        {
            "candidate_sha256": candidate["candidate_sha256"],
            "previous_candidate_sha256": (
                previous_state.get("current_candidate_sha256") if previous_state else None
            ),
            "previous_container_ids": previous_containers,
            "previous_image_ids": {
                role: row["image_id"] for role, row in previous_images.items()
            },
            "release_generation": generation,
        },
    )
    candidate_started = True
    state_written = False
    try:
        promoted = _deploy(project_root, config, candidate_images)
        verify_read_only_http(config)
        _append_audit(audit_path, "CANDIDATE_PROMOTED", {"container_ids": {
            key: value["container_id"] for key, value in promoted.items()
        }})
        rolled_back = _deploy(project_root, config, previous_images)
        verify_read_only_http(config, critical=False)
        _append_audit(audit_path, "PREVIOUS_ROLLBACK_VERIFIED", {"container_ids": {
            key: value["container_id"] for key, value in rolled_back.items()
        }})
        final = _deploy(project_root, config, candidate_images)
        verify_read_only_http(config)
        _append_audit(audit_path, "CANDIDATE_REPROMOTED", {"container_ids": {
            key: value["container_id"] for key, value in final.items()
        }})
        scheduler_after = scheduler_identity(project_root)
        if scheduler_after != scheduler_before:
            raise WebReleaseError("scheduler identity changed during Web release")
        audit_tail = _audit_records(audit_path)[-1]["record_sha256"]
        state: dict[str, object] = {
            "schema_version": STATE_SCHEMA,
            "current_candidate_sha256": candidate["candidate_sha256"],
            "current_release_identity_sha256": candidate["attestation"]["attestation_sha256"],
            "current_images": candidate_images,
            "previous_images": previous_images,
            "previous_candidate_sha256": (
                previous_state.get("current_candidate_sha256") if previous_state else None
            ),
            "previous_container_ids": previous_containers,
            "scheduler_identity": scheduler_after,
            "final_container_ids": {key: value["container_id"] for key, value in final.items()},
            "rollback_drill_passed": True,
            "release_generation": generation,
            "production_authorization": "none",
            "local_read_only_deployment": True,
            "audit_tail_sha256": audit_tail,
        }
        if previous_state is not None:
            archive_release_state(state_path, previous_state)
        write_release_state(state_path, state)
        state_written = True
        _append_audit(audit_path, "MIGRATION_COMPLETED", {"state_schema": STATE_SCHEMA})
        return state
    except Exception as error:
        if candidate_started:
            try:
                restored = _deploy(project_root, config, previous_images)
                if state_written:
                    if previous_state is None:
                        state_path.unlink(missing_ok=True)
                    else:
                        write_release_state(state_path, previous_state)
                _append_audit(audit_path, "FAILED_AND_PREVIOUS_RESTORED", {"container_ids": {
                    key: value["container_id"] for key, value in restored.items()
                }, "error_type": type(error).__name__})
            except Exception as restore_error:
                raise WebReleaseError(
                    "Web release failed and previous release restoration also failed: "
                    f"{type(restore_error).__name__}"
                ) from error
        raise


def start_deployed_release(*, root: Path | None = None) -> dict[str, object]:
    """Start the already promoted content-addressed release without rebuilding it."""
    project_root = (root or PROJECT_ROOT).resolve()
    config = load_web_release_config(root=project_root)
    candidate = load_and_verify_candidate(root=project_root)
    state = load_release_state(project_root / config.state_path)
    if (
        state is None
        or state.get("current_candidate_sha256") != candidate.get("candidate_sha256")
    ):
        raise WebReleaseError("Web release state does not match the current candidate")
    if scheduler_identity(project_root) != state.get("scheduler_identity"):
        raise WebReleaseError("scheduler identity differs before Web release start")
    identities = _deploy(project_root, config, _candidate_images(candidate))
    verify_read_only_http(config)
    if scheduler_identity(project_root) != state.get("scheduler_identity"):
        raise WebReleaseError("scheduler identity changed during Web release start")
    return {
        "status": "PASS",
        "candidate_sha256": candidate["candidate_sha256"],
        "container_ids": {key: value["container_id"] for key, value in identities.items()},
        "production_authorization": "none",
        "local_read_only_deployment": True,
    }


def verify_deployed_release(*, root: Path | None = None) -> dict[str, object]:
    project_root = (root or PROJECT_ROOT).resolve()
    config = load_web_release_config(root=project_root)
    candidate = load_and_verify_candidate(root=project_root)
    state = load_release_state(project_root / config.state_path)
    if state is None:
        raise WebReleaseError("Web release state is missing")
    if state.get("current_candidate_sha256") != candidate.get("candidate_sha256"):
        raise WebReleaseError("Web deployed candidate identity differs")
    images = _candidate_images(candidate)
    identities = wait_and_verify_runtime(
        project_root,
        config,
        _service_image_ids(images),
        timeout_seconds=15,
    )
    verify_read_only_http(config)
    if scheduler_identity(project_root) != state.get("scheduler_identity"):
        raise WebReleaseError("scheduler identity differs from Web release state")
    records = _audit_records(project_root / config.audit_path)
    if (
        not records
        or records[-1]["event"] != "MIGRATION_COMPLETED"
        or records[-1]["previous_record_sha256"] != state.get("audit_tail_sha256")
    ):
        raise WebReleaseError("Web release audit is incomplete")
    return {
        "status": "PASS",
        "candidate_sha256": candidate["candidate_sha256"],
        "release_identity_sha256": candidate["attestation"]["attestation_sha256"],
        "container_ids": {key: value["container_id"] for key, value in identities.items()},
        "scheduler_identity_unchanged": True,
        "rollback_drill_passed": state.get("rollback_drill_passed") is True,
        "production_authorization": "none",
        "local_read_only_deployment": True,
    }
