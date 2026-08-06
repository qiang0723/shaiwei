from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from shaiwei.research.model_attribution.audit_recovery_contract import (
    RECOVERY_ACTION,
    RECOVERY_COMMAND,
    RECOVERY_COMPOSE_PATH,
    RECOVERY_MOUNTS,
    RECOVERY_PROTOCOL_PATH,
    RecoveryApproval,
    RecoveryProtocol,
    RecoveryReleaseScope,
    effect_tree_identity,
)
from shaiwei.research.model_attribution.audit_recovery_entrypoint import (
    _invoke_original_audit,
    _verify_sealed_inputs,
    run,
    self_test,
)
from shaiwei.research.model_attribution.audit_recovery_release import (
    build_release_document,
)
from shaiwei.research.model_attribution.contract import (
    AttributionError,
    canonical_sha256,
)


ROOT = Path(__file__).parents[1]


def _write(path: Path, value: dict) -> Path:
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n")
    return path


def _sealed(protocol: RecoveryProtocol) -> dict:
    source = protocol.document["sealed_runner_state"]
    return {
        "effect_root": "data/research/m6_csi800_model_attribution_v1/effect",
        "audit_root": "data/research/m6_csi800_model_attribution_v1/effect-audit",
        "file_count": source["effect_file_count"],
        "total_bytes": source["effect_total_bytes"],
        "tree_sha256": source["effect_tree_sha256"],
        "report_sha256": source["report_sha256"],
        "authorization_sha256": source["authorization_sha256"],
        "effect_read_marker_sha256": source["effect_read_marker_sha256"],
        "first_pass_manifest_sha256": source["first_pass_manifest_sha256"],
        "replay_manifest_sha256": source["replay_manifest_sha256"],
    }


def _release_document() -> tuple[RecoveryProtocol, dict]:
    protocol = RecoveryProtocol.load()
    document = build_release_document(
        protocol=protocol,
        created_at="2026-08-06T16:00:00+00:00",
        implementation_git_commit="a" * 40,
        origin_main_commit="a" * 40,
        image_id="sha256:" + "b" * 64,
        image_platform="linux/arm64",
        image_git_commit="a" * 40,
        base_image_id=protocol.document["original_authority"]["base_image_id"],
        sealed_effect=_sealed(protocol),
    )
    return protocol, document


def test_protocol_and_release_grant_no_execution_before_new_approval(tmp_path: Path) -> None:
    protocol, document = _release_document()
    release = RecoveryReleaseScope.load(
        _write(tmp_path / "scope.json", document),
        protocol,
        compose_path=RECOVERY_COMPOSE_PATH,
    )
    assert release.sha256 == canonical_sha256(document["scope"])
    assert release.scope["execution"]["additional_alternative_attempt_count"] == 0
    assert release.scope["authority"]["execution_authorized"] is False
    assert release.scope["authority"]["sealed_effect_read_authorized"] is False
    assert release.scope["authority"]["production_authorization"] == "none"


@pytest.mark.parametrize("mutation", ["authority", "command", "mount", "count", "image"])
def test_release_rejects_rehashed_boundary_drift(tmp_path: Path, mutation: str) -> None:
    protocol, document = _release_document()
    changed = copy.deepcopy(document)
    if mutation == "authority":
        changed["scope"]["authority"]["external_network_authorized"] = True
    elif mutation == "command":
        changed["scope"]["container"]["command"][-1] = "/other"
    elif mutation == "mount":
        changed["scope"]["container"]["mounts"][0]["source"] = "."
    elif mutation == "count":
        changed["scope"]["execution"]["recovery_auditor_invocation_count"] = 2
    else:
        changed["scope"]["image"]["base_image_id"] = "sha256:" + "0" * 64
    changed["recovery_scope_sha256"] = canonical_sha256(changed["scope"])
    with pytest.raises(AttributionError):
        RecoveryReleaseScope.load(
            _write(tmp_path / f"{mutation}.json", changed),
            protocol,
            compose_path=RECOVERY_COMPOSE_PATH,
        )


def test_recovery_approval_binds_exact_scope_and_narrow_authority(tmp_path: Path) -> None:
    protocol, document = _release_document()
    release = RecoveryReleaseScope.load(
        _write(tmp_path / "scope.json", document), protocol, compose_path=RECOVERY_COMPOSE_PATH
    )
    approval = {
        "schema_version": "m6-model-attribution-audit-recovery-approval-v1",
        "recovery_scope_sha256": release.sha256,
        "action": RECOVERY_ACTION,
        "approved_at": "2026-08-06T16:01:00+00:00",
        "consumed": False,
        "sealed_effect_read_authorized": True,
        "independent_audit_write_authorized": True,
        "qlib_mount_authorized": False,
        "runner_invocation_authorized": False,
        "model_fit_prediction_backtest_authorized": False,
        "experiment_ledger_write_authorized": False,
        "external_network_authorized": False,
        "env_or_secret_read_authorized": False,
        "production_authorization": "none",
    }
    RecoveryApproval.load(_write(tmp_path / "approval.json", approval), release)
    approval["external_network_authorized"] = True
    with pytest.raises(AttributionError, match="authority differs"):
        RecoveryApproval.load(_write(tmp_path / "wrong.json", approval), release)


def test_effect_tree_identity_detects_content_and_membership_changes(tmp_path: Path) -> None:
    root = tmp_path / "effect"
    root.mkdir()
    (root / "one.bin").write_bytes(b"one")
    before = effect_tree_identity(root)
    assert effect_tree_identity(root) == before
    (root / "one.bin").write_bytes(b"two")
    assert effect_tree_identity(root) != before
    (root / "extra.bin").write_bytes(b"extra")
    assert effect_tree_identity(root)["file_count"] == 2


def test_entrypoint_calls_original_audit_with_exact_keyword_names(tmp_path: Path) -> None:
    captured = {}

    def fake(**kwargs):
        captured.update(kwargs)
        return {"independent_audit": "PASS"}

    result = _invoke_original_audit(
        fake,
        original_release_path=tmp_path / "release.json",
        original_approval_path=tmp_path / "approval.json",
        effect_root=tmp_path / "effect",
        audit_root=tmp_path / "audit",
    )
    assert result["independent_audit"] == "PASS"
    assert set(captured) == {"release_path", "approval_path", "effect_root", "audit_root"}


def test_sealed_input_gate_rejects_tamper_and_nonempty_audit(tmp_path: Path) -> None:
    original_release = tmp_path / "release.json"
    original_approval = tmp_path / "approval.json"
    original_release.write_bytes(b"release")
    original_approval.write_bytes(b"approval")
    effect = tmp_path / "effect"
    effect.mkdir()
    (effect / "report.json").write_bytes(b"report")
    identity = effect_tree_identity(effect)
    protocol = SimpleNamespace(
        document={
            "original_authority": {
                "release_document_sha256": hashlib.sha256(b"release").hexdigest(),
                "approval_sha256": hashlib.sha256(b"approval").hexdigest(),
            }
        }
    )
    release = SimpleNamespace(
        scope={
            "sealed_effect": {
                **identity,
                "report_sha256": hashlib.sha256(b"report").hexdigest(),
            }
        }
    )
    audit_root = tmp_path / "audit"
    assert _verify_sealed_inputs(
        protocol=protocol,
        release=release,
        original_release_path=original_release,
        original_approval_path=original_approval,
        effect_root=effect,
        audit_root=audit_root,
    ) == identity
    audit_root.mkdir()
    (audit_root / "unexpected.json").write_text("{}")
    with pytest.raises(AttributionError, match="not empty"):
        _verify_sealed_inputs(
            protocol=protocol,
            release=release,
            original_release_path=original_release,
            original_approval_path=original_approval,
            effect_root=effect,
            audit_root=audit_root,
        )


def test_synthetic_recovery_calls_auditor_once_and_writes_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    effect = tmp_path / "effect"
    audit_root = tmp_path / "audit"
    effect.mkdir()
    (effect / "report.json").write_bytes(b"sealed-report")
    before = effect_tree_identity(effect)
    protocol = SimpleNamespace(
        document={
            "original_authority": {
                "release_scope_sha256": "1" * 64,
                "approval_sha256": "2" * 64,
            }
        }
    )
    release = SimpleNamespace(sha256="3" * 64)
    approval = SimpleNamespace(sha256="4" * 64)
    monkeypatch.setattr(
        "shaiwei.research.model_attribution.audit_recovery_entrypoint.RecoveryProtocol.load",
        lambda path: protocol,
    )
    monkeypatch.setattr(
        "shaiwei.research.model_attribution.audit_recovery_entrypoint.RecoveryReleaseScope.load",
        lambda path, loaded_protocol, compose_path: release,
    )
    monkeypatch.setattr(
        "shaiwei.research.model_attribution.audit_recovery_entrypoint.RecoveryApproval.load",
        lambda path, loaded_release: approval,
    )
    monkeypatch.setattr(
        "shaiwei.research.model_attribution.audit_recovery_entrypoint._verify_runtime",
        lambda *args, **kwargs: {
            "git_commit": "a" * 40,
            "contract_sha256": "b" * 64,
            "entrypoint_sha256": "c" * 64,
        },
    )
    monkeypatch.setattr(
        "shaiwei.research.model_attribution.audit_recovery_entrypoint._verify_sealed_inputs",
        lambda **kwargs: before,
    )
    calls = []

    def fake_audit(**kwargs):
        calls.append(kwargs)
        audit_root.mkdir()
        (audit_root / "audit.json").write_text("{}\n")
        return {
            "audit_sha256": hashlib.sha256(b"{}\n").hexdigest(),
            "independent_audit": "PASS",
            "production_authorization": "none",
        }

    result = run(
        recovery_protocol_path=tmp_path / "protocol.yaml",
        recovery_release_path=tmp_path / "recovery-release.json",
        recovery_approval_path=tmp_path / "recovery-approval.json",
        recovery_compose_path=tmp_path / "compose.yaml",
        original_release_path=tmp_path / "original-release.json",
        original_approval_path=tmp_path / "original-approval.json",
        effect_root=effect,
        audit_root=audit_root,
        audit_runner=fake_audit,
    )
    assert len(calls) == 1
    assert result["effect_tree_unchanged"] is True
    assert result["additional_alternative_attempt_count"] == 0
    receipt = json.loads((audit_root / "recovery-receipt.json").read_text())
    assert receipt["effect_tree_before"] == receipt["effect_tree_after"] == before
    assert receipt["runner_invocation_count"] == 0


def test_compose_and_thin_dockerfile_match_frozen_boundary() -> None:
    service = yaml.safe_load(RECOVERY_COMPOSE_PATH.read_text())["services"]["m6-audit-recovery"]
    mounts = [
        {
            "source": row["source"].removeprefix("./"),
            "target": row["target"],
            "mode": "ro" if row["read_only"] else "rw",
        }
        for row in service["volumes"]
    ]
    assert service["network_mode"] == "none"
    assert service["read_only"] is True
    assert service["cap_drop"] == ["ALL"]
    assert service["security_opt"] == ["no-new-privileges:true"]
    assert "env_file" not in service
    assert service["command"] == RECOVERY_COMMAND
    assert mounts == RECOVERY_MOUNTS
    assert all("qlib" not in row["source"] and "ledger" not in row["source"] for row in mounts)
    dockerfile = (ROOT / "Dockerfile.m6-audit-recovery").read_text()
    assert dockerfile.splitlines()[0] == "FROM shaiwei:m6-model-attribution-release-v1"
    copies = [line for line in dockerfile.splitlines() if line.startswith("COPY ")]
    assert len(copies) == 2
    assert all("/opt/shaiwei/m6-audit-recovery/" in line for line in copies)


def test_self_test_is_synthetic_and_new_modules_respect_soft_limit() -> None:
    assert self_test() == {
        "original_audit_signature": "PASS",
        "tree_tamper_detection": "PASS",
        "real_effect_read": False,
        "audit_invoked": False,
        "production_authorization": "none",
    }
    modules = [
        ROOT / "src/shaiwei/research/model_attribution/audit_recovery_contract.py",
        ROOT / "src/shaiwei/research/model_attribution/audit_recovery_entrypoint.py",
        ROOT / "src/shaiwei/research/model_attribution/audit_recovery_release.py",
    ]
    assert all(len(path.read_text().splitlines()) <= 400 for path in modules)
    assert RECOVERY_PROTOCOL_PATH.is_file()
