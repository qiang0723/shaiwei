"""Build a content-addressed M7 release scope without granting execution."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .contract import InputManifest, M7GateError, M7Protocol, canonical_json, sha256_file, sha256_json
from .release import ACTION, COMMANDS


def build_release_document(
    protocol: M7Protocol,
    manifest: InputManifest,
    *,
    created_at: str,
    git_commit: str,
    origin_main_commit: str,
    code_bundle_sha256: str,
    requirements_lock_sha256: str,
    dockerfile_sha256: str,
    compose_sha256: str,
    auditor_code_sha256: str,
    approval_builder_sha256: str,
    image_id: str,
    repo_digest: str,
    platform: str,
) -> dict[str, Any]:
    proposal = protocol.proposal
    suffix = f"{manifest.sha256}-{git_commit[:7]}"
    scope = {
        "scope_kind": "DATA_GATE_RELEASE_NOT_EXECUTION_APPROVAL",
        "scope_created_at": created_at,
        "action": ACTION,
        "source_proposal": {
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
        },
        "protocol_scope_sha256": protocol.build_document["protocol_scope_sha256"],
        "protocol_sha256": protocol.sha256,
        "build_contract_sha256": protocol.build_sha256,
        "input_manifest_sha256": manifest.sha256,
        "input_manifest_physical_sha256": manifest.physical_sha256,
        "implementation": {
            "git_commit": git_commit,
            "origin_main_commit": origin_main_commit,
            "commit_pushed_before_scope": True,
            "code_bundle_sha256": code_bundle_sha256,
            "requirements_lock_sha256": requirements_lock_sha256,
            "dockerfile_sha256": dockerfile_sha256,
            "compose_sha256": compose_sha256,
            "auditor_code_sha256": auditor_code_sha256,
            "approval_builder_sha256": approval_builder_sha256,
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
            "user": "65532:65532",
            "read_only_root": True,
            "cap_drop_all": True,
            "no_new_privileges": True,
            "pids_limit": 128,
            "mounts": [
                {"source": f"data/control/m7/input-bundles/{suffix}", "target": "/inputs", "mode": "ro"},
                {"source": f"data/control/m7/outputs/{suffix}", "target": "/outputs", "mode": "rw"},
                {"source": f"data/control/m7/audits/{suffix}", "target": "/audit", "mode": "rw"},
            ],
            "resources": {
                "runner": {"cpus": "2.0", "memory": "4g"},
                "auditor": {"cpus": "1.0", "memory": "2g"},
            },
        },
        "authority": {
            "release_ready": True,
            "release_approval_recorded": False,
            "execution_authorized": False,
            "real_security_key_read_authorized": False,
            "numeric_moneyflow_value_read_authorized": False,
            "network_authorized": False,
            "candidate_generation_authorized": False,
            "label_or_return_read_authorized": False,
            "effect_read_authorized": False,
            "model_training_authorized": False,
            "backtest_authorized": False,
            "paper_or_forward_authorized": False,
            "scheduler_mutation_authorized": False,
            "web_change_authorized": False,
            "production_authorization": "none",
        },
    }
    return {
        "schema_version": "m7-moneyflow-data-gate-release-scope-v1",
        "release_scope_sha256": sha256_json(scope),
        "scope": scope,
    }


def write_release_once(path: Path, document: dict[str, Any]) -> str:
    payload = (canonical_json(document) + "\n").encode("utf-8")
    if path.exists():
        if path.read_bytes() != payload:
            raise M7GateError("existing M7 release scope differs")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        with temporary.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    return sha256_file(path)
