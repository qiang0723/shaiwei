from __future__ import annotations

import copy
from pathlib import Path

import pytest

from shaiwei.research_gates.gate_registry.schema import EXPECTED_SCHEMA_FINGERPRINT
from shaiwei.research_gates.m5_dynamic.contract import (
    InputManifest,
    M5DataProtocol,
    M5GateError,
    canonical_json,
    sha256_json,
)
from shaiwei.research_gates.m5_dynamic.release import (
    APPROVER_SHA256,
    ApprovalEnvelope,
    DataReleaseScope,
)
from shaiwei.research_gates.m5_dynamic.release_builder import build_release_document


ROOT = Path(__file__).parents[1]


def _protocol() -> M5DataProtocol:
    return M5DataProtocol.load(
        ROOT / "config/m5_dynamic_fundamental_cross_pool_v1.yaml",
        build_path=ROOT / "config/m5_dynamic_fundamental_data_gate_build_v1.yaml",
        project_root=ROOT,
    )


def _recovery_protocol() -> M5DataProtocol:
    return M5DataProtocol.load(
        ROOT / "config/m5_dynamic_fundamental_cross_pool_v1.yaml",
        build_path=ROOT / "config/m5_dynamic_fundamental_data_gate_build_v2.yaml",
        project_root=ROOT,
    )


def _input() -> InputManifest:
    return InputManifest(
        document={"fixture": True},
        sha256="5" * 64,
        physical_sha256="6" * 64,
    )


def _release_document(protocol: M5DataProtocol, manifest: InputManifest) -> dict:
    return build_release_document(
        protocol,
        manifest,
        created_at="2026-08-05T13:00:00+00:00",
        git_commit="a" * 40,
        origin_main_commit="a" * 40,
        code_bundle_sha256="b" * 64,
        requirements_lock_sha256="c" * 64,
        dockerfile_sha256="d" * 64,
        compose_sha256="e" * 64,
        auditor_code_sha256="f" * 64,
        image_id="sha256:" + "1" * 64,
        repo_digest="shaiwei/m5-data-gate@sha256:" + "2" * 64,
        platform="linux/arm64",
        input_bundle_relative_path=(
            "data/control/m5_2/input-bundles/" + manifest.sha256 + "-aaaaaaa"
        ),
        output_relative_path="data/control/m5_2/output-staging/fixture",
        audit_relative_path="data/control/m5_2/audit-staging/fixture",
        registry_relative_path="data/control/m5_2/runtime/fixture",
    )


def _write(path: Path, document: dict) -> Path:
    path.write_text(canonical_json(document) + "\n", encoding="utf-8")
    return path


def test_release_scope_is_content_addressed_but_grants_no_execution(tmp_path: Path) -> None:
    protocol = _protocol()
    manifest = _input()
    document = _release_document(protocol, manifest)

    loaded = DataReleaseScope.load(_write(tmp_path / "release.json", document), protocol, manifest)

    assert loaded.sha256 == document["release_scope_sha256"]
    assert loaded.scope["authority"]["data_gate_release_ready"] is True
    assert loaded.scope["authority"]["data_gate_execution_authorized"] is False
    assert loaded.scope["authority"]["real_data_read_authorized"] is False
    assert loaded.scope["authority"]["production_authorization"] == "none"


@pytest.mark.parametrize(
    "mutation", ["execution", "mount", "registry", "bundle_identity", "commit"]
)
def test_release_scope_rejects_rehashed_authority_or_identity_drift(
    tmp_path: Path, mutation: str
) -> None:
    protocol = _protocol()
    manifest = _input()
    document = copy.deepcopy(_release_document(protocol, manifest))
    if mutation == "execution":
        document["scope"]["authority"]["data_gate_execution_authorized"] = True
    elif mutation == "mount":
        document["scope"]["container"]["mounts"][0]["source"] = "/workspace"
    elif mutation == "registry":
        document["scope"]["container"]["mounts"] = [
            item
            for item in document["scope"]["container"]["mounts"]
            if item["target"] != "/registry"
        ]
    elif mutation == "bundle_identity":
        document["scope"]["container"]["mounts"][0]["source"] = (
            "data/control/m5_2/input-bundles/" + manifest.sha256
        )
    else:
        document["scope"]["implementation"]["origin_main_commit"] = "9" * 40
    document["release_scope_sha256"] = sha256_json(document["scope"])

    with pytest.raises(M5GateError):
        DataReleaseScope.load(_write(tmp_path / "release.json", document), protocol, manifest)


def test_approval_must_bind_exact_release_scope_and_registry_identity(tmp_path: Path) -> None:
    protocol = _protocol()
    manifest = _input()
    release = DataReleaseScope.load(
        _write(tmp_path / "release.json", _release_document(protocol, manifest)),
        protocol,
        manifest,
    )
    approval = {
        "schema_version": "m5-data-gate-approval-v1",
        "case_id": "3" * 64,
        "release_scope_sha256": release.sha256,
        "approval_event_seq": 4,
        "approval_event_sha256": "4" * 64,
        "approval_actor_sha256": APPROVER_SHA256,
        "registry_schema_fingerprint": EXPECTED_SCHEMA_FINGERPRINT,
        "data_gate_execution_authorized": True,
    }

    loaded = ApprovalEnvelope.load(_write(tmp_path / "approval.json", approval), release)
    assert loaded.sha256 == sha256_json(approval)

    approval["release_scope_sha256"] = "0" * 64
    with pytest.raises(M5GateError, match="exact approved release"):
        ApprovalEnvelope.load(_write(tmp_path / "drifted.json", approval), release)


def test_recovery_release_and_approval_bind_the_new_case(tmp_path: Path) -> None:
    protocol = _recovery_protocol()
    manifest = _input()
    document = _release_document(protocol, manifest)
    release = DataReleaseScope.load(
        _write(tmp_path / "release-v2.json", document), protocol, manifest
    )
    assert document["schema_version"] == "m5-data-gate-release-scope-v2"
    assert release.scope["case_id"] == protocol.case_id
    approval = {
        "schema_version": "m5-data-gate-approval-v1",
        "case_id": protocol.case_id,
        "release_scope_sha256": release.sha256,
        "approval_event_seq": 4,
        "approval_event_sha256": "4" * 64,
        "approval_actor_sha256": APPROVER_SHA256,
        "registry_schema_fingerprint": EXPECTED_SCHEMA_FINGERPRINT,
        "data_gate_execution_authorized": True,
    }
    ApprovalEnvelope.load(_write(tmp_path / "approval-v2.json", approval), release)
    approval["case_id"] = "0" * 64
    with pytest.raises(M5GateError, match="case differs"):
        ApprovalEnvelope.load(
            _write(tmp_path / "approval-drift.json", approval), release
        )
