from __future__ import annotations

import json
from pathlib import Path

import pytest

from shaiwei.research_gates.m7_moneyflow.contract import (
    InputManifest,
    M7GateError,
    M7Protocol,
    canonical_json,
    sha256_json,
)
from shaiwei.research_gates.m7_moneyflow.release import (
    ACTION,
    ApprovalEnvelope,
    DataReleaseScope,
)
from shaiwei.research_gates.m7_moneyflow.release_builder import build_release_document


ROOT = Path(__file__).resolve().parents[1]
SHA = "a" * 64
GIT = "b" * 40


def _protocol() -> M7Protocol:
    return M7Protocol.load(
        ROOT / "config/m7_star_custom_pool_moneyflow_data_v1.yaml",
        build_path=ROOT / "config/m7_star_custom_pool_moneyflow_data_gate_build_v1.yaml",
        project_root=ROOT,
    )


def _manifest(protocol: M7Protocol) -> InputManifest:
    return InputManifest({}, "c" * 64, "d" * 64)


def _document(protocol: M7Protocol, manifest: InputManifest) -> dict[str, object]:
    return build_release_document(
        protocol,
        manifest,
        created_at="2026-08-08T16:00:00+08:00",
        git_commit=GIT,
        origin_main_commit=GIT,
        code_bundle_sha256=SHA,
        requirements_lock_sha256=SHA,
        dockerfile_sha256=SHA,
        compose_sha256=SHA,
        auditor_code_sha256=SHA,
        approval_builder_sha256=SHA,
        image_id=f"sha256:{SHA}",
        repo_digest=f"shaiwei:m7-moneyflow-data-gate-local@sha256:{SHA}",
        platform="linux/arm64",
    )


def test_release_is_content_addressed_but_does_not_authorize_execution(tmp_path: Path) -> None:
    protocol = _protocol()
    manifest = _manifest(protocol)
    path = tmp_path / "release.json"
    document = _document(protocol, manifest)
    path.write_text(canonical_json(document) + "\n", encoding="utf-8")
    release = DataReleaseScope.load(path, protocol, manifest)
    assert release.scope["authority"]["release_ready"] is True
    assert release.scope["authority"]["execution_authorized"] is False
    assert release.scope["authority"]["real_security_key_read_authorized"] is False
    assert release.scope["authority"]["production_authorization"] == "none"


def test_release_rejects_container_or_input_drift(tmp_path: Path) -> None:
    protocol = _protocol()
    manifest = _manifest(protocol)
    document = _document(protocol, manifest)
    document["scope"]["container"]["network_mode"] = "bridge"  # type: ignore[index]
    document["release_scope_sha256"] = sha256_json(document["scope"])
    path = tmp_path / "release.json"
    path.write_text(canonical_json(document) + "\n", encoding="utf-8")
    with pytest.raises(M7GateError, match="least privilege"):
        DataReleaseScope.load(path, protocol, manifest)


def test_approval_must_bind_exact_release_scope_and_proposal(tmp_path: Path) -> None:
    protocol = _protocol()
    manifest = _manifest(protocol)
    release_path = tmp_path / "release.json"
    release_path.write_text(canonical_json(_document(protocol, manifest)) + "\n", encoding="utf-8")
    release = DataReleaseScope.load(release_path, protocol, manifest)
    proposal = release.scope["source_proposal"]
    approval = {
        "schema_version": "m7-moneyflow-data-gate-approval-v1",
        "action": ACTION,
        "release_scope_sha256": release.sha256,
        "proposal_id": proposal["proposal_id"],
        "proposal_state": proposal["required_state_at_approval"],
        "proposal_event_seq": proposal["required_event_seq_at_approval"],
        "proposal_head_event_sha256": proposal["proposal_head_event_sha256"],
        "approved_at": "2026-08-08T16:05:00+08:00",
        "proposal_database_relative_path": proposal["proposal_database_relative_path"],
        "proposal_integrity_verified": True,
        "approval_actor_sha256": "7df97c84a6ddbde116d9b2ec059200349035842d6c88bf55e90880002315b48d",
        "execution_authorized": True,
    }
    approval_path = tmp_path / "approval.json"
    approval_path.write_text(canonical_json(approval) + "\n", encoding="utf-8")
    loaded = ApprovalEnvelope.load(approval_path, release)
    assert loaded.sha256 == sha256_json(approval)
    approval["release_scope_sha256"] = "f" * 64
    approval_path.write_text(canonical_json(approval) + "\n", encoding="utf-8")
    with pytest.raises(M7GateError, match="exact release"):
        ApprovalEnvelope.load(approval_path, release)


def test_release_document_is_json_serializable() -> None:
    protocol = _protocol()
    assert json.loads(canonical_json(_document(protocol, _manifest(protocol))))
