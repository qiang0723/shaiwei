"""Exact release and approval envelopes for one M7 lineage execution."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import PurePosixPath
from pathlib import Path
from typing import Any

from shaiwei.research_gates.m7_moneyflow.contract import canonical_json, sha256_json

from .contract import ACTION, LineageError, LineageInputManifest, LineageProtocol


APPROVER_SHA256 = "7df97c84a6ddbde116d9b2ec059200349035842d6c88bf55e90880002315b48d"
COMMANDS = {
    "runner": ["python", "-m", "shaiwei.research_gates.m7_moneyflow_lineage.runner"],
    "auditor": ["python", "-m", "shaiwei.research_gates.m7_moneyflow_lineage.auditor"],
}
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
GIT_RE = re.compile(r"^[0-9a-f]{40}$")
IMAGE_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def _relative(value: Any) -> str:
    path = PurePosixPath(str(value))
    if path.is_absolute() or not path.parts or ".." in path.parts:
        raise LineageError("lineage release mount source must be project-relative")
    return path.as_posix()


@dataclass(frozen=True)
class LineageRelease:
    document: dict[str, Any]
    scope: dict[str, Any]
    sha256: str

    @classmethod
    def load(
        cls,
        path: Path,
        protocol: LineageProtocol,
        manifest: LineageInputManifest,
    ) -> LineageRelease:
        serialized = path.read_text(encoding="utf-8")
        document = json.loads(serialized)
        if (
            not isinstance(document, dict)
            or set(document) != {"schema_version", "release_scope_sha256", "scope"}
            or serialized != canonical_json(document) + "\n"
            or document.get("schema_version") != "m7-moneyflow-gap-lineage-release-v1"
        ):
            raise LineageError("lineage release envelope differs")
        scope = document.get("scope")
        fields = {
            "scope_kind",
            "scope_created_at",
            "action",
            "source_proposal",
            "protocol_sha256",
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
            or scope["scope_kind"] != "LINEAGE_RELEASE_NOT_EXECUTION_APPROVAL"
            or scope["action"] != ACTION
            or scope["protocol_sha256"] != protocol.sha256
            or scope["input_manifest_sha256"] != manifest.sha256
            or scope["input_manifest_physical_sha256"] != manifest.physical_sha256
        ):
            raise LineageError("lineage release identity differs")
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
            "proposal_database_relative_path": protocol.proposal_export["source_database_relative_path"],
        }
        if scope["source_proposal"] != expected_proposal:
            raise LineageError("lineage release proposal identity differs")
        created = datetime.fromisoformat(str(scope["scope_created_at"]))
        expires = datetime.fromisoformat(str(proposal["expires_at"]))
        if created.tzinfo is None or created > expires:
            raise LineageError("lineage release is outside proposal lifetime")
        implementation = scope["implementation"]
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
        commit = str(implementation.get("git_commit", ""))
        if (
            set(implementation) != implementation_fields
            or GIT_RE.fullmatch(commit) is None
            or implementation["origin_main_commit"] != commit
            or implementation["commit_pushed_before_scope"] is not True
            or any(
                SHA_RE.fullmatch(str(implementation[key])) is None
                for key in implementation_fields
                - {"git_commit", "origin_main_commit", "commit_pushed_before_scope"}
            )
        ):
            raise LineageError("lineage implementation is not pushed and bound")
        image = scope["image"]
        base_image = (
            "python:3.11-slim@sha256:db3ff2e1800a8581e2c48a27c3995339d47bdf046da21c7627accd3d51053a93"
        )
        if (
            set(image) != {"image_id", "repo_digest", "platform", "base_image"}
            or IMAGE_RE.fullmatch(str(image["image_id"])) is None
            or re.fullmatch(r"[^@]+@sha256:[0-9a-f]{64}", str(image["repo_digest"])) is None
            or image["platform"] not in {"linux/arm64", "linux/amd64"}
            or image["base_image"] != base_image
            or scope["commands"] != COMMANDS
        ):
            raise LineageError("lineage image or commands differ")
        container = scope["container"]
        container_fields = {
            "network_mode",
            "user",
            "read_only_root",
            "cap_drop_all",
            "no_new_privileges",
            "pids_limit",
            "mounts",
            "resources",
        }
        expected_resources = {
            "runner": {"cpus": "2.0", "memory": "4g"},
            "auditor": {"cpus": "1.0", "memory": "2g"},
        }
        if (
            set(container) != container_fields
            or container.get("network_mode") != "none"
            or container.get("user") != "65532:65532"
            or container.get("read_only_root") is not True
            or container.get("cap_drop_all") is not True
            or container.get("no_new_privileges") is not True
            or container.get("pids_limit") != 128
            or container.get("resources") != expected_resources
        ):
            raise LineageError("lineage least-privilege container differs")
        mounts = container.get("mounts")
        expected_mounts = {
            ("runner", "/inputs", "ro"),
            ("runner", "/outputs", "rw"),
            ("runner", "/claims", "rw"),
            ("auditor", "/inputs", "ro"),
            ("auditor", "/outputs", "ro"),
            ("auditor", "/audit", "rw"),
            ("auditor", "/claims", "rw"),
        }
        if (
            not isinstance(mounts, list)
            or len(mounts) != 7
            or {(item.get("role"), item.get("target"), item.get("mode")) for item in mounts}
            != expected_mounts
            or any(set(item) != {"role", "source", "target", "mode"} for item in mounts)
            or any(
                token in json.dumps(mounts).lower()
                for token in (
                    "/workspace",
                    ".env",
                    ".git",
                    "docker.sock",
                    "label",
                    "effect",
                    "model",
                    "prediction",
                )
            )
        ):
            raise LineageError("lineage release mounts differ or are overbroad")
        for item in mounts:
            _relative(item["source"])
        suffix = f"{manifest.sha256}-{commit[:7]}"
        expected_input = f"data/control/m7-lineage/input-bundles/{suffix}"
        if any(item["source"] != expected_input for item in mounts if item["target"] == "/inputs"):
            raise LineageError("lineage input bundle path differs")
        authority = scope["authority"]
        authority_fields = {
            "release_ready",
            "release_approval_recorded",
            "execution_authorized",
            "real_security_key_read_authorized",
            "numeric_moneyflow_value_read_authorized",
            "network_authorized",
            "candidate_generation_authorized",
            "label_or_return_read_authorized",
            "effect_read_authorized",
            "model_training_authorized",
            "backtest_authorized",
            "paper_or_forward_authorized",
            "scheduler_mutation_authorized",
            "web_change_authorized",
            "production_authorization",
        }
        if (
            set(authority) != authority_fields
            or authority.get("release_ready") is not True
            or authority.get("production_authorization") != "none"
        ):
            raise LineageError("lineage release authority differs")
        if any(
            value for key, value in authority.items() if key != "release_ready" and isinstance(value, bool)
        ):
            raise LineageError("lineage release silently grants execution")
        return cls(document, scope, document["release_scope_sha256"])


@dataclass(frozen=True)
class LineageApproval:
    document: dict[str, Any]
    sha256: str

    @classmethod
    def load(cls, path: Path, release: LineageRelease) -> LineageApproval:
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
            or document["schema_version"] != "m7-moneyflow-gap-lineage-approval-v1"
            or document["action"] != ACTION
            or document["release_scope_sha256"] != release.sha256
            or document["proposal_id"] != proposal["proposal_id"]
            or document["proposal_state"] != proposal["required_state_at_approval"]
            or document["proposal_event_seq"] != proposal["required_event_seq_at_approval"]
            or document["proposal_head_event_sha256"] != proposal["proposal_head_event_sha256"]
            or document["proposal_database_relative_path"] != proposal["proposal_database_relative_path"]
            or document["proposal_integrity_verified"] is not True
            or document["approval_actor_sha256"] != APPROVER_SHA256
            or document["execution_authorized"] is not True
        ):
            raise LineageError("lineage approval does not bind the exact release")
        approved = datetime.fromisoformat(str(document["approved_at"]))
        expires = datetime.fromisoformat(str(proposal["expires_at"]))
        if approved.tzinfo is None or approved >= expires:
            raise LineageError("lineage approval is expired")
        return cls(document, sha256_json(document))
