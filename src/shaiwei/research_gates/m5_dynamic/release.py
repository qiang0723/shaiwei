"""Content-addressed release and approval envelopes for the future real M5 data gate."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from pathlib import PurePosixPath
from typing import Any

from shaiwei.research_gates.gate_registry.models import sha256_text
from shaiwei.research_gates.gate_registry.schema import EXPECTED_SCHEMA_FINGERPRINT

from .contract import (
    BUILD_PROTOCOL_ID,
    PROTOCOL_SCOPE_SHA256,
    InputManifest,
    M5DataProtocol,
    M5GateError,
    canonical_json,
    sha256_json,
)
from .release_builder import COMMANDS


GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
APPROVER_SHA256 = sha256_text("M5_LOCAL_PROTOCOL_APPROVER")
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
SCOPE_FIELDS = {
    "scope_kind",
    "scope_created_at",
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


def _relative_mount(value: Any) -> str:
    path = PurePosixPath(str(value))
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise M5GateError("M5 data release mount source must be project-relative")
    return path.as_posix()


@dataclass(frozen=True)
class DataReleaseScope:
    document: dict[str, Any]
    scope: dict[str, Any]
    sha256: str

    @classmethod
    def load(
        cls,
        path: Path,
        protocol: M5DataProtocol,
        input_manifest: InputManifest,
    ) -> DataReleaseScope:
        serialized = path.read_text(encoding="utf-8")
        document = json.loads(serialized)
        if not isinstance(document, dict) or set(document) != {
            "schema_version",
            "release_scope_sha256",
            "scope",
        }:
            raise M5GateError("M5 data release envelope fields differ")
        if serialized != canonical_json(document) + "\n":
            raise M5GateError("M5 data release envelope is not canonical")
        if document["schema_version"] != "m5-data-gate-release-scope-v1":
            raise M5GateError("M5 data release schema differs")
        scope = document["scope"]
        if (
            not isinstance(scope, dict)
            or set(scope) != SCOPE_FIELDS
            or document["release_scope_sha256"] != sha256_json(scope)
        ):
            raise M5GateError("M5 data release scope hash differs")
        if (
            scope.get("scope_kind") != "DATA_GATE_RELEASE_NOT_EXECUTION_APPROVAL"
            or scope.get("protocol_scope_sha256") != PROTOCOL_SCOPE_SHA256
            or scope.get("protocol_sha256") != protocol.sha256
            or scope.get("build_protocol_id") != BUILD_PROTOCOL_ID
            or scope.get("input_manifest_sha256") != input_manifest.sha256
            or scope.get("input_manifest_physical_sha256")
            != input_manifest.physical_sha256
            or re.fullmatch(
                r"[0-9a-f]{64}", str(scope.get("input_manifest_physical_sha256", ""))
            )
            is None
        ):
            raise M5GateError("M5 data release upstream identity differs")
        proposal = protocol.document["source_proposal"]
        expected_proposal = {
            "proposal_id": proposal["proposal_id"],
            "proposal_request_sha256": proposal["proposal_request_sha256"],
            "canonical_proposal_sha256": proposal["canonical_proposal_sha256"],
            "proposal_head_event_sha256": proposal["required_head_event_sha256"],
            "proposal_export_sha256": proposal["proposal_export_sha256"],
            "required_state_at_data_gate_approval": proposal[
                "required_state_at_data_gate_approval"
            ],
            "required_event_seq_at_data_gate_approval": proposal[
                "required_event_seq_at_data_gate_approval"
            ],
            "expires_at": proposal["expires_at"],
        }
        if scope.get("source_proposal") != expected_proposal:
            raise M5GateError("M5 data release proposal identity differs")
        try:
            created_at = datetime.fromisoformat(str(scope["scope_created_at"]))
            expires_at = datetime.fromisoformat(str(expected_proposal["expires_at"]))
        except ValueError as exc:
            raise M5GateError("M5 data release time is invalid") from exc
        if created_at.tzinfo is None or expires_at.tzinfo is None or created_at > expires_at:
            raise M5GateError("M5 data release is outside the proposal lifetime")
        implementation = scope.get("implementation") or {}
        commit = str(implementation.get("git_commit", ""))
        if (
            set(implementation)
            != {
                "git_commit",
                "origin_main_commit",
                "commit_pushed_before_scope",
                "code_bundle_sha256",
                "requirements_lock_sha256",
                "dockerfile_sha256",
                "compose_sha256",
                "auditor_code_sha256",
            }
            or GIT_SHA_RE.fullmatch(commit) is None
            or implementation.get("commit_pushed_before_scope") is not True
            or implementation.get("origin_main_commit") != commit
            or not re.fullmatch(r"[0-9a-f]{64}", str(implementation.get("code_bundle_sha256", "")))
            or any(
                re.fullmatch(r"[0-9a-f]{64}", str(implementation.get(key, ""))) is None
                for key in (
                    "requirements_lock_sha256",
                    "dockerfile_sha256",
                    "compose_sha256",
                    "auditor_code_sha256",
                )
            )
        ):
            raise M5GateError("M5 data release implementation is not pushed and content-addressed")
        image = scope.get("image") or {}
        image_id = str(image.get("image_id", ""))
        repo_digest = str(image.get("repo_digest", ""))
        if (
            set(image) != {"image_id", "repo_digest", "platform", "base_image"}
            or image.get("platform") not in {"linux/arm64", "linux/amd64"}
            or image.get("base_image") != protocol.build_document["container"]["base_image"]
            or re.fullmatch(r"sha256:[0-9a-f]{64}", image_id) is None
            or re.fullmatch(r"[^@]+@sha256:[0-9a-f]{64}", repo_digest) is None
        ):
            raise M5GateError("M5 data release image identity differs")
        commands = scope.get("commands")
        if commands != COMMANDS:
            raise M5GateError("M5 data release commands differ")
        container = scope.get("container") or {}
        if (
            set(container)
            != {
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
            or container.get("network_mode") != "none"
            or container.get("read_only_root") is not True
            or container.get("run_as_non_root") is not True
            or container.get("user") != "65532:65532"
            or container.get("cap_drop_all") is not True
            or container.get("no_new_privileges") is not True
            or container.get("pids_limit") != 128
        ):
            raise M5GateError("M5 data release container is not offline and least-privilege")
        mounts = container.get("mounts")
        if not isinstance(mounts, list) or not mounts:
            raise M5GateError("M5 data release mount plan is empty")
        serialized_mounts = json.dumps(mounts, ensure_ascii=False).lower()
        if any(token in serialized_mounts for token in FORBIDDEN_MOUNT_TOKENS):
            raise M5GateError("M5 data release contains a forbidden mount")
        expected_modes = {"/inputs": "ro", "/outputs": "rw", "/audit": "rw"}
        if (
            len(mounts) != 3
            or any(set(item) != {"source", "target", "mode"} for item in mounts)
            or {item.get("target") for item in mounts} != set(expected_modes)
            or any(item.get("mode") != expected_modes[item.get("target")] for item in mounts)
        ):
            raise M5GateError("M5 data release mount targets differ")
        for item in mounts:
            _relative_mount(item["source"])
        if container.get("resources") != {
            "runner": {"cpus": "1.0", "memory": "2g"},
            "auditor": {"cpus": "0.5", "memory": "512m"},
            "registrar": {"cpus": "0.5", "memory": "512m"},
        }:
            raise M5GateError("M5 data release resource limits differ")
        if scope.get("registry_schema_fingerprint") != EXPECTED_SCHEMA_FINGERPRINT:
            raise M5GateError("M5 data release registry schema differs")
        authority = scope.get("authority") or {}
        expected_authority_fields = {
            "data_gate_release_ready",
            "data_gate_approval_recorded",
            "data_gate_execution_authorized",
            "engineering_gate_execution_authorized",
            "real_data_read_authorized",
            "label_read_authorized",
            "effect_read_authorized",
            "external_call_authorized",
            "model_training_authorized",
            "backtest_authorized",
            "paper_authorized",
            "forward_authorized",
            "scheduler_mutation_authorized",
            "web_change_authorized",
            "production_authorization",
        }
        if set(authority) != expected_authority_fields or authority.get(
            "data_gate_release_ready"
        ) is not True:
            raise M5GateError("M5 data release is not marked ready")
        forbidden_true = {
            key
            for key, value in authority.items()
            if key != "data_gate_release_ready" and isinstance(value, bool) and value
        }
        if forbidden_true or authority.get("production_authorization") != "none":
            raise M5GateError("M5 data release silently contains execution or production authority")
        return cls(document=document, scope=scope, sha256=document["release_scope_sha256"])


@dataclass(frozen=True)
class ApprovalEnvelope:
    document: dict[str, Any]
    sha256: str

    @classmethod
    def load(cls, path: Path, release: DataReleaseScope) -> ApprovalEnvelope:
        serialized = path.read_text(encoding="utf-8")
        document = json.loads(serialized)
        expected_fields = {
            "schema_version",
            "case_id",
            "release_scope_sha256",
            "approval_event_seq",
            "approval_event_sha256",
            "approval_actor_sha256",
            "registry_schema_fingerprint",
            "data_gate_execution_authorized",
        }
        if not isinstance(document, dict) or set(document) != expected_fields:
            raise M5GateError("M5 data approval envelope fields differ")
        if serialized != canonical_json(document) + "\n":
            raise M5GateError("M5 data approval envelope is not canonical")
        if (
            document["schema_version"] != "m5-data-gate-approval-v1"
            or document["release_scope_sha256"] != release.sha256
            or document["approval_actor_sha256"] != APPROVER_SHA256
            or document["registry_schema_fingerprint"] != EXPECTED_SCHEMA_FINGERPRINT
            or document["data_gate_execution_authorized"] is not True
            or int(document["approval_event_seq"]) < 4
            or re.fullmatch(r"[0-9a-f]{64}", str(document["case_id"])) is None
            or re.fullmatch(r"[0-9a-f]{64}", str(document["approval_event_sha256"])) is None
        ):
            raise M5GateError("M5 data approval envelope is not bound to the exact approved release")
        return cls(document=document, sha256=sha256_json(document))
