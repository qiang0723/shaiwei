from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from shaiwei.research_gates.m7_moneyflow.contract import canonical_json
from shaiwei.research_gates.m7_moneyflow_recovery.contract import RecoveryError
from shaiwei.research_gates.m7_moneyflow_recovery.projection_contract import (
    ACTION,
    TargetProjectionProtocol,
)
from shaiwei.research_gates.m7_moneyflow_recovery.projection_fixture import (
    verify_projection_fixture,
)
from shaiwei.research_gates.m7_moneyflow_recovery.projection_release import (
    APPROVER_SHA256,
    CODE_BUNDLE_ROOTS,
    TargetProjectionApproval,
    TargetProjectionRelease,
    build_release_document,
    code_bundle_sha256,
)


ROOT = Path(__file__).resolve().parents[1]
TRACKED_RELEASE = ROOT / "config/m7_moneyflow_recovery_target_projection_release_scope_v1.json"
TRACKED_RELEASE_SHA256 = "9aca04576362455af66c5426bd0b4b6211d7edecc8b141de5ecee96ae5781614"


def _protocol() -> TargetProjectionProtocol:
    return TargetProjectionProtocol.load(
        ROOT / "config/m7_moneyflow_recovery_target_projection_v2.yaml",
        project_root=ROOT,
    )


def _release(tmp_path: Path) -> tuple[TargetProjectionRelease, Path]:
    document = build_release_document(
        _protocol(),
        created_at="2026-08-09T15:00:00+08:00",
        git_commit="a" * 40,
        code_bundle_sha256="b" * 64,
        image_id="sha256:" + "c" * 64,
        platform="linux/arm64",
    )
    path = tmp_path / "release.json"
    path.write_text(canonical_json(document) + "\n", encoding="utf-8")
    return TargetProjectionRelease.load(path, _protocol()), path


def test_real_scale_fixture_is_exact_offline_and_one_shot() -> None:
    result = verify_projection_fixture(ROOT)
    assert result["verdict"] == "GO_M7_RECOVERY_TARGET_PROJECTION_ENGINEERING_ONLY"
    assert result["track_a_member_rows"] == 908
    assert result["track_b_member_rows"] == 541
    assert result["main_and_independent_targets_exact_match"] is True
    assert result["second_invocation_stopped_before_semantic_read"] is True
    assert result["real_security_key_read"] is False
    assert result["moneyflow_numeric_value_columns_read"] == 0
    assert result["provider_call_count"] == 0
    assert result["network_used"] is False
    assert result["production_authorization"] == "none"


def test_release_scope_is_content_addressed_offline_and_non_executable(tmp_path: Path) -> None:
    release, path = _release(tmp_path)
    scope = release.scope
    assert release.document["release_scope_sha256"] == release.sha256
    assert scope["action"] == ACTION
    assert scope["container"]["network_mode"] == "none"
    assert scope["container"]["read_only_root"] is True
    assert scope["container"]["user"] == "65532:65532"
    assert scope["authority"]["execution_authorized"] is False
    assert scope["authority"]["real_security_key_read_authorized"] is False
    assert scope["authority"]["numeric_moneyflow_value_read_authorized"] is False
    assert scope["authority"]["provider_call_authorized"] is False
    assert scope["authority"]["production_authorization"] == "none"
    assert scope["implementation"]["code_bundle_roots"] == list(CODE_BUNDLE_ROOTS)
    serialized = path.read_text(encoding="utf-8")
    assert all(token not in serialized for token in (".env", "docker.sock", '"/workspace"'))


def test_code_bundle_is_deterministic_narrow_and_nonempty() -> None:
    first = code_bundle_sha256(ROOT)
    second = code_bundle_sha256(ROOT)
    assert first == second
    assert len(first) == 64
    assert all(not root.startswith(("data", "ledger", "logs")) for root in CODE_BUNDLE_ROOTS)


def test_tracked_release_binds_pushed_implementation_and_current_code_bundle() -> None:
    release = TargetProjectionRelease.load(TRACKED_RELEASE, _protocol())
    implementation = release.scope["implementation"]
    assert release.sha256 == TRACKED_RELEASE_SHA256
    assert implementation["git_commit"] == "23f06b2479ac6f394fbc8599cff4d98dd6ee55ce"
    assert implementation["origin_main_commit"] == implementation["git_commit"]
    assert implementation["code_bundle_sha256"] == code_bundle_sha256(ROOT)
    assert release.scope["image"]["image_id"] == (
        "sha256:ea77e1716ae14774f2eb98e33fcab58136b62aa8be3fd567155fcbddf82ed007"
    )
    assert release.scope["authority"]["execution_authorized"] is False


def test_approval_is_exactly_bound_and_wrong_scope_is_rejected(tmp_path: Path) -> None:
    release, _ = _release(tmp_path)
    approval = {
        "schema_version": "m7-moneyflow-recovery-target-approval-v1",
        "action": ACTION,
        "release_scope_sha256": release.sha256,
        "approved_at": "2026-08-09T15:01:00+08:00",
        "approval_actor_sha256": APPROVER_SHA256,
        "execution_authorized": True,
    }
    path = tmp_path / "approval.json"
    path.write_text(canonical_json(approval) + "\n", encoding="utf-8")
    parsed = TargetProjectionApproval.load(path, release)
    assert parsed.document == approval
    approval["release_scope_sha256"] = "f" * 64
    path.write_text(canonical_json(approval) + "\n", encoding="utf-8")
    with pytest.raises(RecoveryError, match="approval differs"):
        TargetProjectionApproval.load(path, release)


def test_release_loader_rejects_authority_or_container_expansion(tmp_path: Path) -> None:
    release, path = _release(tmp_path)
    for mutate in ("network", "numeric"):
        document = json.loads(canonical_json(release.document))
        if mutate == "network":
            document["scope"]["container"]["network_mode"] = "bridge"
        else:
            document["scope"]["authority"]["numeric_moneyflow_value_read_authorized"] = True
        from shaiwei.research_gates.m7_moneyflow.contract import sha256_json

        document["release_scope_sha256"] = sha256_json(document["scope"])
        path.write_text(canonical_json(document) + "\n", encoding="utf-8")
        with pytest.raises(RecoveryError):
            TargetProjectionRelease.load(path, _protocol())


def test_projection_docker_is_offline_read_only_and_unmounted() -> None:
    compose = yaml.safe_load(
        (ROOT / "compose.m7-moneyflow-target-projection.yaml").read_text(encoding="utf-8")
    )
    service = compose["services"]["m7-target-projection-fixture"]
    assert service["network_mode"] == "none"
    assert service["read_only"] is True
    assert service["user"] == "65532:65532"
    assert service["cap_drop"] == ["ALL"]
    serialized = canonical_json(service)
    assert all(token not in serialized for token in ("volumes", ".env", "docker.sock", "/workspace"))


def test_projection_entrypoints_have_no_secret_provider_or_production_dependencies() -> None:
    package = ROOT / "src/shaiwei/research_gates/m7_moneyflow_recovery"
    names = (
        "projection_contract.py",
        "projection_release.py",
        "projection_runner.py",
        "projection_auditor.py",
        "projection_sealing.py",
        "projection_fixture.py",
    )
    combined = "\n".join((package / name).read_text(encoding="utf-8") for name in names)
    for token in (
        "shaiwei.config",
        "create_client",
        "tushare",
        "baostock",
        "requests.",
        "httpx",
        "ledger/",
        "logs/",
    ):
        assert token not in combined
    assert max(len((package / name).read_text(encoding="utf-8").splitlines()) for name in names) <= 400
