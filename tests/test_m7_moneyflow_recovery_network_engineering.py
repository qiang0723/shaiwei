from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from shaiwei.research_gates.m7_moneyflow.contract import canonical_json
from shaiwei.research_gates.m7_moneyflow_recovery.contract import RecoveryError
from shaiwei.research_gates.m7_moneyflow_network_recovery.network_contract import (
    NetworkReleaseProtocol,
)
from shaiwei.research_gates.m7_moneyflow_network_recovery.network_fixture import (
    verify_network_fixture,
)
from shaiwei.research_gates.m7_moneyflow_network_recovery.network_release import (
    APPROVER_SHA256,
    NetworkRecoveryApproval,
    NetworkRecoveryRelease,
    build_release_document,
)
from shaiwei.research_gates.m7_moneyflow_recovery.sealing import write_canonical_once


ROOT = Path(__file__).resolve().parents[1]


def _protocol() -> NetworkReleaseProtocol:
    return NetworkReleaseProtocol.load(
        ROOT / "config/m7_moneyflow_evidence_recovery_network_release_v1.yaml",
        project_root=ROOT,
    )


def _manifest() -> dict[str, object]:
    return {
        "plan_id": "1" * 64,
        "plan_root_relative_path": "data/control/m7-recovery/request-plans/" + "1" * 64,
        "target_identity": {
            "track_a": {"physical_sha256": "2" * 64, "logical_sha256": "3" * 64},
            "track_b": {"physical_sha256": "4" * 64, "logical_sha256": "5" * 64},
        },
        "request_summary": {
            "status": {
                "request_count": 500,
                "required_key_count": 527,
                "request_identity_bundle_sha256": "6" * 64,
            },
            "full_market": {
                "request_count": 30,
                "request_identity_bundle_sha256": "7" * 64,
            },
            "targeted": {
                "request_count": 541,
                "request_identity_bundle_sha256": "8" * 64,
            },
        },
    }


def _document() -> dict[str, object]:
    return build_release_document(
        _protocol(),
        _manifest(),
        plan_manifest_sha256="9" * 64,
        created_at="2026-08-09T16:00:00+08:00",
        git_commit="a" * 40,
        code_bundle_sha256="b" * 64,
        image_id="sha256:" + "c" * 64,
        platform="linux/arm64",
    )


def test_network_fixture_uses_only_mock_clients_and_stops_duplicate() -> None:
    result = verify_network_fixture(ROOT)
    assert result["verdict"] == "GO_M7_RECOVERY_NETWORK_RELEASE_ENGINEERING_ONLY"
    assert result["status_request_count"] == 1
    assert result["moneyflow_request_count"] == 2
    assert result["mock_provider_call_count"] == 3
    assert result["duplicate_stopped_before_provider"] is True
    assert result["external_network_used"] is False
    assert result["secret_read"] is False


def test_exact_release_has_four_narrow_roles_and_no_authority_before_approval() -> None:
    scope = _document()["scope"]
    assert set(scope["roles"]) == {
        "status_collector",
        "moneyflow_collector",
        "evaluator",
        "auditor",
    }
    assert scope["roles"]["status_collector"]["network_mode"] == "bridge"
    assert scope["roles"]["moneyflow_collector"]["network_mode"] == "bridge"
    assert scope["roles"]["evaluator"]["network_mode"] == "none"
    assert scope["roles"]["auditor"]["network_mode"] == "none"
    writable = [
        item["source"]
        for role in scope["roles"].values()
        for item in role["mounts"]
        if item["mode"] == "rw"
    ]
    assert len(writable) == len(set(writable))
    serialized = canonical_json(scope)
    assert "/run/secrets/tushare_token" in canonical_json(
        scope["roles"]["moneyflow_collector"]
    )
    assert "/run/secrets/tushare_token" not in canonical_json(
        scope["roles"]["status_collector"]
    )
    assert all(token not in serialized for token in (".env", "docker.sock", "/workspace"))
    assert re.search(r"[0-9]{6}\.(?:SH|SZ|BJ)", serialized) is None
    assert scope["authority"]["execution_authorized"] is False
    assert scope["authority"]["network_authorized"] is False
    assert scope["authority"]["provider_call_authorized"] is False
    assert scope["authority"]["secret_read_authorized"] is False
    assert scope["provider_limits"]["exact_provider_request_count"] == 1071


def test_release_and_exact_approval_are_canonical_and_scope_bound(tmp_path: Path) -> None:
    release_path = tmp_path / "release.json"
    write_canonical_once(release_path, _document())
    release = NetworkRecoveryRelease.load(
        release_path,
        _protocol(),
        plan_manifest=_manifest(),
        plan_manifest_sha256="9" * 64,
    )
    approval = {
        "schema_version": "m7-moneyflow-recovery-network-approval-v1",
        "action": "M7_MONEYFLOW_EVIDENCE_RECOVERY_ONCE",
        "release_scope_sha256": release.sha256,
        "approved_at": "2026-08-09T16:01:00+08:00",
        "approval_actor_sha256": APPROVER_SHA256,
        "execution_authorized": True,
        "network_authorized": True,
        "provider_call_authorized": True,
        "secret_read_authorized": True,
        "same_scope_rerun_authorized": False,
    }
    approval_path = tmp_path / "approval.json"
    write_canonical_once(approval_path, approval)
    parsed = NetworkRecoveryApproval.load(approval_path, release)
    assert parsed.document == approval
    approval["release_scope_sha256"] = "f" * 64
    bad_path = tmp_path / "bad-approval.json"
    write_canonical_once(bad_path, approval)
    with pytest.raises(RecoveryError, match="approval differs"):
        NetworkRecoveryApproval.load(bad_path, release)


def test_release_rejects_nonexact_counts() -> None:
    manifest = _manifest()
    manifest["request_summary"]["targeted"]["request_count"] = 540
    with pytest.raises(RecoveryError, match="exact request counts"):
        build_release_document(
            _protocol(),
            manifest,
            plan_manifest_sha256="9" * 64,
            created_at="2026-08-09T16:00:00+08:00",
            git_commit="a" * 40,
            code_bundle_sha256="b" * 64,
            image_id="sha256:" + "c" * 64,
            platform="linux/arm64",
        )


def test_network_docker_fixture_is_offline_read_only_and_unmounted() -> None:
    compose = yaml.safe_load(
        (ROOT / "compose.m7-moneyflow-recovery-network.yaml").read_text(encoding="utf-8")
    )
    service = compose["services"]["m7-recovery-network-fixture"]
    assert service["network_mode"] == "none"
    assert service["read_only"] is True
    assert service["user"] == "65532:65532"
    assert service["cap_drop"] == ["ALL"]
    assert service["security_opt"] == ["no-new-privileges:true"]
    serialized = canonical_json(service)
    assert all(token not in serialized for token in ("volumes", ".env", "docker.sock"))


def test_network_modules_are_split_and_under_soft_limit() -> None:
    package = ROOT / "src/shaiwei/research_gates/m7_moneyflow_network_recovery"
    counts = {
        path.name: len(path.read_text(encoding="utf-8").splitlines())
        for path in package.glob("*.py")
    }
    assert max(counts.values()) <= 400
    assert "shaiwei.config" not in (package / "live_clients.py").read_text(encoding="utf-8")
    assert ".env" not in (package / "live_clients.py").read_text(encoding="utf-8")
