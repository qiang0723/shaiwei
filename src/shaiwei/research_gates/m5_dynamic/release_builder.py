"""Build the immutable M5 data-gate release scope; never grants execution authority."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from shaiwei.research_gates.gate_registry.schema import EXPECTED_SCHEMA_FINGERPRINT

from .contract import (
    BUILD_PROTOCOL_ID,
    PROTOCOL_SCOPE_SHA256,
    InputManifest,
    M5DataProtocol,
    M5GateError,
    canonical_json,
    sha256_file,
    sha256_json,
)


COMMANDS = {
    "runner": ["python", "-m", "shaiwei.research_gates.m5_dynamic.runner"],
    "auditor": ["python", "-m", "shaiwei.research_gates.m5_dynamic.auditor"],
    "registrar": ["python", "-m", "shaiwei.research_gates.gate_registry"],
}


def build_release_document(
    protocol: M5DataProtocol,
    input_manifest: InputManifest,
    *,
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
    input_bundle_relative_path: str,
    output_relative_path: str,
    audit_relative_path: str,
) -> dict[str, Any]:
    proposal = protocol.document["source_proposal"]
    scope = {
        "scope_kind": "DATA_GATE_RELEASE_NOT_EXECUTION_APPROVAL",
        "scope_created_at": created_at,
        "source_proposal": {
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
        },
        "protocol_scope_sha256": PROTOCOL_SCOPE_SHA256,
        "protocol_sha256": protocol.sha256,
        "build_protocol_id": BUILD_PROTOCOL_ID,
        "input_manifest_sha256": input_manifest.sha256,
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
            "base_image": protocol.build_document["container"]["base_image"],
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
                {
                    "source": input_bundle_relative_path,
                    "target": "/inputs",
                    "mode": "ro",
                },
                {
                    "source": output_relative_path,
                    "target": "/outputs",
                    "mode": "rw",
                },
                {
                    "source": audit_relative_path,
                    "target": "/audit",
                    "mode": "rw",
                },
            ],
            "resources": {
                "runner": {"cpus": "1.0", "memory": "2g"},
                "auditor": {"cpus": "0.5", "memory": "512m"},
                "registrar": {"cpus": "0.5", "memory": "512m"},
            },
        },
        "registry_schema_fingerprint": EXPECTED_SCHEMA_FINGERPRINT,
        "authority": {
            "data_gate_release_ready": True,
            "data_gate_approval_recorded": False,
            "data_gate_execution_authorized": False,
            "engineering_gate_execution_authorized": False,
            "real_data_read_authorized": False,
            "label_read_authorized": False,
            "effect_read_authorized": False,
            "external_call_authorized": False,
            "model_training_authorized": False,
            "backtest_authorized": False,
            "paper_authorized": False,
            "forward_authorized": False,
            "scheduler_mutation_authorized": False,
            "web_change_authorized": False,
            "production_authorization": "none",
        },
    }
    return {
        "schema_version": "m5-data-gate-release-scope-v1",
        "release_scope_sha256": sha256_json(scope),
        "scope": scope,
    }


def write_release_once(path: Path, document: dict[str, Any]) -> str:
    payload = (canonical_json(document) + "\n").encode("utf-8")
    if path.exists():
        if path.read_bytes() != payload:
            raise M5GateError("existing M5 data release scope differs")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        with temporary.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    return sha256_file(path)
