"""Validate the immutable M5 source-lineage release and future approval envelope."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any

from shaiwei.research_gates.gate_registry.models import sha256_text
from shaiwei.research_gates.gate_registry.schema import EXPECTED_SCHEMA_FINGERPRINT

from .contract import M5GateError, canonical_json, sha256_json
from .lineage_contract import CASE_ID, LineageInputManifest, LineageProtocol
from .lineage_release_builder import BASE_IMAGE, COMMANDS


APPROVER_SHA256 = sha256_text("M5_LOCAL_PROTOCOL_APPROVER")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
FORBIDDEN_MOUNT_TOKENS = (
    "/workspace",
    ".env",
    ".git",
    "docker.sock",
    "label",
    "effect",
    "model",
    "prediction",
)


def _relative(value: Any) -> str:
    path = PurePosixPath(str(value))
    if path.is_absolute() or not path.parts or ".." in path.parts:
        raise M5GateError("M5 lineage release mount source must be project-relative")
    return path.as_posix()


def _proposal(source: dict[str, Any]) -> dict[str, Any]:
    return {
        "proposal_id": source["proposal_id"],
        "proposal_request_sha256": source["proposal_request_sha256"],
        "canonical_proposal_sha256": source["canonical_proposal_sha256"],
        "proposal_head_event_sha256": source["required_head_event_sha256"],
        "proposal_export_sha256": source["proposal_export_sha256"],
        "required_state_at_approval": source["required_state_at_data_gate_approval"],
        "required_event_seq_at_approval": source["required_event_seq_at_data_gate_approval"],
        "expires_at": source["expires_at"],
    }


@dataclass(frozen=True)
class LineageReleaseScope:
    document: dict[str, Any]
    scope: dict[str, Any]
    sha256: str

    @classmethod
    def load(
        cls,
        path: Path,
        protocol: LineageProtocol,
        input_manifest: LineageInputManifest,
        *,
        source_proposal: dict[str, Any],
    ) -> LineageReleaseScope:
        serialized = path.read_text(encoding="utf-8")
        document = json.loads(serialized)
        if (
            not isinstance(document, dict)
            or set(document) != {"schema_version", "release_scope_sha256", "scope"}
            or document.get("schema_version") != "m5-source-lineage-release-scope-v1"
            or serialized != canonical_json(document) + "\n"
        ):
            raise M5GateError("M5 lineage release envelope differs")
        scope = document["scope"]
        fields = {
            "scope_kind",
            "scope_created_at",
            "case_id",
            "source_proposal",
            "protocol_scope_sha256",
            "protocol_sha256",
            "build_protocol_id",
            "input_manifest_sha256",
            "input_manifest_physical_sha256",
            "implementation",
            "image",
            "commands",
            "container",
            "registry_schema_fingerprint",
            "authority",
        }
        if (
            not isinstance(scope, dict)
            or set(scope) != fields
            or document["release_scope_sha256"] != sha256_json(scope)
            or scope["scope_kind"] != "SOURCE_LINEAGE_RELEASE_NOT_EXECUTION_APPROVAL"
            or scope["case_id"] != CASE_ID
            or scope["protocol_scope_sha256"] != protocol.scope_document["protocol_scope_sha256"]
            or scope["protocol_sha256"] != protocol.sha256
            or scope["build_protocol_id"] != protocol.build_document["build_protocol_id"]
            or scope["input_manifest_sha256"] != input_manifest.sha256
            or scope["input_manifest_physical_sha256"] != input_manifest.physical_sha256
            or scope["source_proposal"] != _proposal(source_proposal)
        ):
            raise M5GateError("M5 lineage release upstream identity differs")
        created = datetime.fromisoformat(str(scope["scope_created_at"]))
        expiry = datetime.fromisoformat(str(scope["source_proposal"]["expires_at"]))
        if created.tzinfo is None or expiry.tzinfo is None or created >= expiry:
            raise M5GateError("M5 lineage release is outside proposal lifetime")
        _validate_implementation(scope["implementation"])
        _validate_image(scope["image"])
        if scope["commands"] != COMMANDS:
            raise M5GateError("M5 lineage release commands differ")
        _validate_container(scope["container"], input_manifest, scope["implementation"]["git_commit"])
        if scope["registry_schema_fingerprint"] != EXPECTED_SCHEMA_FINGERPRINT:
            raise M5GateError("M5 lineage registry schema differs")
        _validate_authority(scope["authority"])
        return cls(document=document, scope=scope, sha256=document["release_scope_sha256"])


def _validate_implementation(value: Any) -> None:
    fields = {
        "git_commit",
        "origin_main_commit",
        "commit_pushed_before_scope",
        "code_bundle_sha256",
        "requirements_lock_sha256",
        "dockerfile_sha256",
        "compose_sha256",
        "auditor_code_sha256",
    }
    if (
        not isinstance(value, dict)
        or set(value) != fields
        or COMMIT_RE.fullmatch(str(value["git_commit"])) is None
        or value["origin_main_commit"] != value["git_commit"]
        or value["commit_pushed_before_scope"] is not True
        or any(
            SHA256_RE.fullmatch(str(value[name])) is None
            for name in fields
            - {
                "git_commit",
                "origin_main_commit",
                "commit_pushed_before_scope",
            }
        )
    ):
        raise M5GateError("M5 lineage implementation is not pushed and content-addressed")


def _validate_image(value: Any) -> None:
    if (
        not isinstance(value, dict)
        or set(value) != {"image_id", "repo_digest", "platform", "base_image"}
        or re.fullmatch(r"sha256:[0-9a-f]{64}", str(value["image_id"])) is None
        or re.fullmatch(r"[^@]+@sha256:[0-9a-f]{64}", str(value["repo_digest"])) is None
        or value["platform"] not in {"linux/arm64", "linux/amd64"}
        or value["base_image"] != BASE_IMAGE
    ):
        raise M5GateError("M5 lineage image identity differs")


def _validate_container(value: Any, manifest: LineageInputManifest, commit: str) -> None:
    fields = {
        "network_mode",
        "run_as_non_root",
        "user",
        "read_only_root",
        "cap_drop_all",
        "no_new_privileges",
        "pids_limit",
        "mounts",
        "resources",
    }
    if (
        not isinstance(value, dict)
        or set(value) != fields
        or {
            key: value[key]
            for key in (
                "network_mode",
                "run_as_non_root",
                "user",
                "read_only_root",
                "cap_drop_all",
                "no_new_privileges",
                "pids_limit",
            )
        }
        != {
            "network_mode": "none",
            "run_as_non_root": True,
            "user": "65532:65532",
            "read_only_root": True,
            "cap_drop_all": True,
            "no_new_privileges": True,
            "pids_limit": 128,
        }
    ):
        raise M5GateError("M5 lineage container is not offline and least privilege")
    mounts = value["mounts"]
    expected = {
        "/lineage-input": "ro",
        "/lineage-output": "rw",
        "/lineage-audit": "rw",
        "/registry": "rw",
    }
    if (
        not isinstance(mounts, list)
        or len(mounts) != 4
        or any(set(item) != {"source", "target", "mode"} for item in mounts)
        or {item["target"]: item["mode"] for item in mounts} != expected
        or any(token in json.dumps(mounts).lower() for token in FORBIDDEN_MOUNT_TOKENS)
    ):
        raise M5GateError("M5 lineage release mounts differ")
    for item in mounts:
        _relative(item["source"])
    input_source = next(item["source"] for item in mounts if item["target"] == "/lineage-input")
    if input_source != f"data/control/m5_2/lineage-input-bundles/{manifest.sha256}-{commit[:7]}":
        raise M5GateError("M5 lineage input path is not content addressed")
    if value["resources"] != {
        "runner": {"cpus": "1.0", "memory": "2g"},
        "auditor": {"cpus": "0.5", "memory": "512m"},
        "registrar": {"cpus": "0.5", "memory": "512m"},
    }:
        raise M5GateError("M5 lineage resources differ")


def _validate_authority(value: Any) -> None:
    expected = {
        "lineage_release_ready",
        "lineage_approval_recorded",
        "lineage_execution_authorized",
        "formal_registry_write_authorized",
        "real_data_read_authorized",
        "real_conflict_diagnosis_authorized",
        "external_call_authorized",
        "credential_read_authorized",
        "pit_compute_authorized",
        "candidate_compute_authorized",
        "label_read_authorized",
        "effect_read_authorized",
        "model_training_authorized",
        "backtest_authorized",
        "production_authorization",
    }
    if (
        not isinstance(value, dict)
        or set(value) != expected
        or value["lineage_release_ready"] is not True
        or any(item is True for key, item in value.items() if key != "lineage_release_ready")
        or value["production_authorization"] != "none"
    ):
        raise M5GateError("M5 lineage release silently grants authority")


@dataclass(frozen=True)
class LineageApprovalEnvelope:
    document: dict[str, Any]
    sha256: str

    @classmethod
    def load(cls, path: Path, release: LineageReleaseScope) -> LineageApprovalEnvelope:
        serialized = path.read_text(encoding="utf-8")
        document = json.loads(serialized)
        fields = {
            "schema_version",
            "case_id",
            "release_scope_sha256",
            "approval_event_seq",
            "approval_event_sha256",
            "approval_actor_sha256",
            "registry_schema_fingerprint",
            "lineage_execution_authorized",
        }
        if (
            not isinstance(document, dict)
            or set(document) != fields
            or serialized != canonical_json(document) + "\n"
            or document["schema_version"] != "m5-source-lineage-approval-v1"
            or document["case_id"] != CASE_ID
            or document["release_scope_sha256"] != release.sha256
            or document["approval_actor_sha256"] != APPROVER_SHA256
            or document["registry_schema_fingerprint"] != EXPECTED_SCHEMA_FINGERPRINT
            or document["lineage_execution_authorized"] is not True
            or int(document["approval_event_seq"]) < 4
            or SHA256_RE.fullmatch(str(document["approval_event_sha256"])) is None
        ):
            raise M5GateError("M5 lineage approval does not bind the exact release")
        return cls(document=document, sha256=sha256_json(document))
