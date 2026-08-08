"""Build a non-executable, content-addressed M7 lineage release scope."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from shaiwei.research_gates.m7_moneyflow.contract import canonical_json, sha256_file, sha256_json

from .contract import ACTION, LineageError, LineageInputManifest, LineageProtocol
from .release import COMMANDS


def build_release_document(
    protocol: LineageProtocol,
    manifest: LineageInputManifest,
    *,
    created_at: str,
    implementation: dict[str, Any],
    image_id: str,
    repo_digest: str,
    platform: str,
) -> dict[str, Any]:
    proposal = protocol.proposal
    commit = implementation["git_commit"]
    suffix = f"{manifest.sha256}-{commit[:7]}"
    scope = {
        "scope_kind": "LINEAGE_RELEASE_NOT_EXECUTION_APPROVAL",
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
            "proposal_database_relative_path": protocol.proposal_export["source_database_relative_path"],
        },
        "protocol_sha256": protocol.sha256,
        "input_manifest_sha256": manifest.sha256,
        "input_manifest_physical_sha256": manifest.physical_sha256,
        "implementation": implementation,
        "image": {
            "image_id": image_id,
            "repo_digest": repo_digest,
            "platform": platform,
            "base_image": "python:3.11-slim@sha256:db3ff2e1800a8581e2c48a27c3995339d47bdf046da21c7627accd3d51053a93",
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
                {
                    "role": "runner",
                    "source": f"data/control/m7-lineage/input-bundles/{suffix}",
                    "target": "/inputs",
                    "mode": "ro",
                },
                {
                    "role": "runner",
                    "source": f"data/control/m7-lineage/outputs/{suffix}",
                    "target": "/outputs",
                    "mode": "rw",
                },
                {
                    "role": "runner",
                    "source": f"data/control/m7-lineage/claims/{suffix}",
                    "target": "/claims",
                    "mode": "rw",
                },
                {
                    "role": "auditor",
                    "source": f"data/control/m7-lineage/input-bundles/{suffix}",
                    "target": "/inputs",
                    "mode": "ro",
                },
                {
                    "role": "auditor",
                    "source": f"data/control/m7-lineage/outputs/{suffix}",
                    "target": "/outputs",
                    "mode": "ro",
                },
                {
                    "role": "auditor",
                    "source": f"data/control/m7-lineage/audits/{suffix}",
                    "target": "/audit",
                    "mode": "rw",
                },
                {
                    "role": "auditor",
                    "source": f"data/control/m7-lineage/claims/{suffix}",
                    "target": "/claims",
                    "mode": "rw",
                },
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
        "schema_version": "m7-moneyflow-gap-lineage-release-v1",
        "release_scope_sha256": sha256_json(scope),
        "scope": scope,
    }


def write_once(path: Path, document: dict[str, Any]) -> str:
    payload = (canonical_json(document) + "\n").encode()
    if path.exists():
        if path.read_bytes() != payload:
            raise LineageError("existing lineage release differs")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        with temporary.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    return sha256_file(path)
