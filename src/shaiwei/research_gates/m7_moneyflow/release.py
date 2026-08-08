"""Exact release and approval envelopes for one future M7 real key read."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any

from .contract import InputManifest, M7GateError, M7Protocol, canonical_json, sha256_json


ACTION = "M7_STAR_CUSTOM_POOL_MONEYFLOW_DATA_GATE_ONCE"
APPROVER_SHA256 = "7df97c84a6ddbde116d9b2ec059200349035842d6c88bf55e90880002315b48d"
COMMANDS = {
    "runner": ["python", "-m", "shaiwei.research_gates.m7_moneyflow.runner"],
    "auditor": ["python", "-m", "shaiwei.research_gates.m7_moneyflow.auditor"],
}
GIT_RE = re.compile(r"^[0-9a-f]{40}$")
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
IMAGE_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
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


def _relative_mount(value: Any) -> str:
    path = PurePosixPath(str(value))
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise M7GateError("M7 release mount source must be project-relative")
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
        protocol: M7Protocol,
        manifest: InputManifest,
    ) -> DataReleaseScope:
        serialized = path.read_text(encoding="utf-8")
        document = json.loads(serialized)
        if (
            not isinstance(document, dict)
            or set(document) != {"schema_version", "release_scope_sha256", "scope"}
            or serialized != canonical_json(document) + "\n"
            or document.get("schema_version") != "m7-moneyflow-data-gate-release-scope-v1"
        ):
            raise M7GateError("M7 release envelope shape or serialization differs")
        scope = document.get("scope")
        fields = {
            "scope_kind",
            "scope_created_at",
            "action",
            "source_proposal",
            "protocol_scope_sha256",
            "protocol_sha256",
            "build_contract_sha256",
            "input_manifest_sha256",
            "input_manifest_physical_sha256",
            "implementation",
            "image",
            "commands",
            "container",
            "authority",
        }
        if (
            not isinstance(scope, dict)
            or set(scope) != fields
            or document["release_scope_sha256"] != sha256_json(scope)
            or scope["scope_kind"] != "DATA_GATE_RELEASE_NOT_EXECUTION_APPROVAL"
            or scope["action"] != ACTION
            or scope["protocol_scope_sha256"] != protocol.build_document["protocol_scope_sha256"]
            or scope["protocol_sha256"] != protocol.sha256
            or scope["build_contract_sha256"] != protocol.build_sha256
            or scope["input_manifest_sha256"] != manifest.sha256
            or scope["input_manifest_physical_sha256"] != manifest.physical_sha256
        ):
            raise M7GateError("M7 release scope identity differs")
        proposal = protocol.proposal
        expected_proposal = {
            "proposal_id": proposal["proposal_id"],
            "proposal_request_sha256": proposal["proposal_request_sha256"],
            "canonical_proposal_sha256": proposal["canonical_proposal_sha256"],
            "proposal_head_event_sha256": proposal["required_head_event_sha256"],
            "proposal_export_sha256": proposal["proposal_export_sha256"],
            "required_state_at_approval": proposal["required_state_at_release_approval"],
            "required_event_seq_at_approval": proposal["required_event_seq_at_release_approval"],
            "expires_at": proposal["expires_at"],
            "proposal_database_relative_path": protocol.proposal_export[
                "source_database_relative_path"
            ],
        }
        if scope["source_proposal"] != expected_proposal:
            raise M7GateError("M7 release proposal identity differs")
        created = datetime.fromisoformat(str(scope["scope_created_at"]))
        expires = datetime.fromisoformat(str(proposal["expires_at"]))
        if created.tzinfo is None or expires.tzinfo is None or created > expires:
            raise M7GateError("M7 release was created outside proposal lifetime")
        implementation = scope["implementation"]
        commit = str(implementation.get("git_commit", ""))
        implementation_fields = {
            "git_commit",
            "origin_main_commit",
            "commit_pushed_before_scope",
            "code_bundle_sha256",
            "requirements_lock_sha256",
            "dockerfile_sha256",
            "compose_sha256",
            "auditor_code_sha256",
            "approval_builder_sha256",
        }
        if (
            set(implementation) != implementation_fields
            or GIT_RE.fullmatch(commit) is None
            or implementation["origin_main_commit"] != commit
            or implementation["commit_pushed_before_scope"] is not True
            or any(SHA_RE.fullmatch(str(implementation[key])) is None for key in implementation_fields - {"git_commit", "origin_main_commit", "commit_pushed_before_scope"})
        ):
            raise M7GateError("M7 release implementation is not pushed and content-addressed")
        image = scope["image"]
        if (
            set(image) != {"image_id", "repo_digest", "platform", "base_image"}
            or IMAGE_RE.fullmatch(str(image["image_id"])) is None
            or re.fullmatch(r"[^@]+@sha256:[0-9a-f]{64}", str(image["repo_digest"])) is None
            or image["platform"] not in {"linux/arm64", "linux/amd64"}
            or image["base_image"] != protocol.build_document["container"]["base_image"]
        ):
            raise M7GateError("M7 release image identity differs")
        if scope["commands"] != COMMANDS:
            raise M7GateError("M7 release commands differ")
        container = scope["container"]
        expected_container_fields = {
            "network_mode",
            "user",
            "read_only_root",
            "cap_drop_all",
            "no_new_privileges",
            "pids_limit",
            "mounts",
            "resources",
        }
        if (
            set(container) != expected_container_fields
            or container["network_mode"] != "none"
            or container["user"] != "65532:65532"
            or container["read_only_root"] is not True
            or container["cap_drop_all"] is not True
            or container["no_new_privileges"] is not True
            or container["pids_limit"] != 128
            or container["resources"] != {
                "runner": {"cpus": "2.0", "memory": "4g"},
                "auditor": {"cpus": "1.0", "memory": "2g"},
            }
        ):
            raise M7GateError("M7 release container differs from least privilege contract")
        mounts = container["mounts"]
        modes = {"/inputs": "ro", "/outputs": "rw", "/audit": "rw"}
        if (
            not isinstance(mounts, list)
            or len(mounts) != 3
            or {item.get("target") for item in mounts} != set(modes)
            or any(set(item) != {"source", "target", "mode"} for item in mounts)
            or any(item["mode"] != modes[item["target"]] for item in mounts)
            or any(token in json.dumps(mounts).lower() for token in FORBIDDEN_MOUNT_TOKENS)
        ):
            raise M7GateError("M7 release mounts differ or contain forbidden resources")
        for item in mounts:
            _relative_mount(item["source"])
        expected_input = f"data/control/m7/input-bundles/{manifest.sha256}-{commit[:7]}"
        if next(item["source"] for item in mounts if item["target"] == "/inputs") != expected_input:
            raise M7GateError("M7 input bundle is not bound to input and implementation")
        authority = scope["authority"]
        if authority.get("release_ready") is not True or authority.get("production_authorization") != "none":
            raise M7GateError("M7 release is not ready or expands production authority")
        if any(value for key, value in authority.items() if key != "release_ready" and isinstance(value, bool)):
            raise M7GateError("M7 release silently contains execution authority")
        return cls(document, scope, document["release_scope_sha256"])


@dataclass(frozen=True)
class ApprovalEnvelope:
    document: dict[str, Any]
    sha256: str

    @classmethod
    def load(cls, path: Path, release: DataReleaseScope) -> ApprovalEnvelope:
        serialized = path.read_text(encoding="utf-8")
        document = json.loads(serialized)
        fields = {
            "schema_version",
            "action",
            "release_scope_sha256",
            "proposal_id",
            "proposal_state",
            "proposal_event_seq",
            "proposal_head_event_sha256",
            "proposal_database_relative_path",
            "proposal_integrity_verified",
            "approved_at",
            "approval_actor_sha256",
            "execution_authorized",
        }
        proposal = release.scope["source_proposal"]
        if (
            not isinstance(document, dict)
            or set(document) != fields
            or serialized != canonical_json(document) + "\n"
            or document["schema_version"] != "m7-moneyflow-data-gate-approval-v1"
            or document["action"] != ACTION
            or document["release_scope_sha256"] != release.sha256
            or document["proposal_id"] != proposal["proposal_id"]
            or document["proposal_state"] != proposal["required_state_at_approval"]
            or document["proposal_event_seq"] != proposal["required_event_seq_at_approval"]
            or document["proposal_head_event_sha256"] != proposal["proposal_head_event_sha256"]
            or document["proposal_database_relative_path"]
            != proposal["proposal_database_relative_path"]
            or document["proposal_integrity_verified"] is not True
            or document["approval_actor_sha256"] != APPROVER_SHA256
            or document["execution_authorized"] is not True
        ):
            raise M7GateError("M7 approval does not bind the exact release and proposal")
        approved = datetime.fromisoformat(str(document["approved_at"]))
        expires = datetime.fromisoformat(str(proposal["expires_at"]))
        if approved.tzinfo is None or approved >= expires:
            raise M7GateError("M7 approval occurred after proposal expiry")
        return cls(document, sha256_json(document))
