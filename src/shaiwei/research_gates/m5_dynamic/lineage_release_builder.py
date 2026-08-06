"""Build a content-addressed M5 lineage release without granting execution."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from shaiwei.research_gates.gate_registry.schema import EXPECTED_SCHEMA_FINGERPRINT

from .contract import M5GateError, canonical_json, sha256_file, sha256_json
from .lineage_contract import LineageInputManifest, LineageProtocol


COMMANDS = {
    "runner": ["python", "-m", "shaiwei.research_gates.m5_dynamic.lineage_runner"],
    "auditor": ["python", "-m", "shaiwei.research_gates.m5_dynamic.lineage_auditor"],
    "registrar": ["python", "-m", "shaiwei.research_gates.gate_registry"],
}
BASE_IMAGE = (
    "shaiwei:m5-lineage-local@"
    "sha256:fe9101f11a54d0b2111c0000ffff5a21d7d72fd86f4300aa30ae7b934119b606"
)


def build_lineage_release_document(
    protocol: LineageProtocol,
    input_manifest: LineageInputManifest,
    *,
    source_proposal: dict[str, Any],
    created_at: str,
    git_commit: str,
    origin_main_commit: str,
    code_bundle_sha256: str,
    requirements_lock_sha256: str,
    dockerfile_sha256: str,
    compose_sha256: str,
    auditor_code_sha256: str,
    image_id: str,
    repo_digest: str,
    platform: str,
    input_relative_path: str,
    output_relative_path: str,
    audit_relative_path: str,
    registry_relative_path: str,
) -> dict[str, Any]:
    proposal = {
        "proposal_id": source_proposal["proposal_id"],
        "proposal_request_sha256": source_proposal["proposal_request_sha256"],
        "canonical_proposal_sha256": source_proposal["canonical_proposal_sha256"],
        "proposal_head_event_sha256": source_proposal["required_head_event_sha256"],
        "proposal_export_sha256": source_proposal["proposal_export_sha256"],
        "required_state_at_approval": source_proposal["required_state_at_data_gate_approval"],
        "required_event_seq_at_approval": source_proposal["required_event_seq_at_data_gate_approval"],
        "expires_at": source_proposal["expires_at"],
    }
    scope = {
        "scope_kind": "SOURCE_LINEAGE_RELEASE_NOT_EXECUTION_APPROVAL",
        "scope_created_at": created_at,
        "case_id": protocol.build_document["derived_case_id"],
        "source_proposal": proposal,
        "protocol_scope_sha256": protocol.scope_document["protocol_scope_sha256"],
        "protocol_sha256": protocol.sha256,
        "build_protocol_id": protocol.build_document["build_protocol_id"],
        "input_manifest_sha256": input_manifest.sha256,
        "input_manifest_physical_sha256": input_manifest.physical_sha256,
        "implementation": {
            "git_commit": git_commit,
            "origin_main_commit": origin_main_commit,
            "commit_pushed_before_scope": True,
            "code_bundle_sha256": code_bundle_sha256,
            "requirements_lock_sha256": requirements_lock_sha256,
            "dockerfile_sha256": dockerfile_sha256,
            "compose_sha256": compose_sha256,
            "auditor_code_sha256": auditor_code_sha256,
        },
        "image": {
            "image_id": image_id,
            "repo_digest": repo_digest,
            "platform": platform,
            "base_image": BASE_IMAGE,
        },
        "commands": COMMANDS,
        "container": {
            "network_mode": "none",
            "run_as_non_root": True,
            "user": "65532:65532",
            "read_only_root": True,
            "cap_drop_all": True,
            "no_new_privileges": True,
            "pids_limit": 128,
            "mounts": [
                {"source": input_relative_path, "target": "/lineage-input", "mode": "ro"},
                {"source": output_relative_path, "target": "/lineage-output", "mode": "rw"},
                {"source": audit_relative_path, "target": "/lineage-audit", "mode": "rw"},
                {"source": registry_relative_path, "target": "/registry", "mode": "rw"},
            ],
            "resources": {
                "runner": {"cpus": "1.0", "memory": "2g"},
                "auditor": {"cpus": "0.5", "memory": "512m"},
                "registrar": {"cpus": "0.5", "memory": "512m"},
            },
        },
        "registry_schema_fingerprint": EXPECTED_SCHEMA_FINGERPRINT,
        "authority": {
            "lineage_release_ready": True,
            "lineage_approval_recorded": False,
            "lineage_execution_authorized": False,
            "formal_registry_write_authorized": False,
            "real_data_read_authorized": False,
            "real_conflict_diagnosis_authorized": False,
            "external_call_authorized": False,
            "credential_read_authorized": False,
            "pit_compute_authorized": False,
            "candidate_compute_authorized": False,
            "label_read_authorized": False,
            "effect_read_authorized": False,
            "model_training_authorized": False,
            "backtest_authorized": False,
            "production_authorization": "none",
        },
    }
    return {
        "schema_version": "m5-source-lineage-release-scope-v1",
        "release_scope_sha256": sha256_json(scope),
        "scope": scope,
    }


def write_lineage_release_once(path: Path, document: dict[str, Any]) -> str:
    payload = (canonical_json(document) + "\n").encode("utf-8")
    if path.exists():
        if path.read_bytes() != payload:
            raise M5GateError("existing M5 lineage release scope differs")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        with temporary.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    return sha256_file(path)
