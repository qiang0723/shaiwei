from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
import yaml

from shaiwei.research.model_attribution.contract import canonical_sha256
from shaiwei.research.production_conversion.audit_entrypoint_recovery_contract import (
    ACTION,
    COMPOSE_PATH,
    EMBEDDED_ORIGINAL_PROTOCOL,
    EntryRecoveryApproval,
    EntryRecoveryProtocol,
    EntryRecoveryScope,
    expected_sealed,
)
from shaiwei.research.production_conversion.audit_entrypoint_recovery_release import (
    build_release_document,
)
from shaiwei.research.production_conversion.audit_identity_recovery_entrypoint import (
    _audit_documents,
    _synthetic_bundle,
)
from shaiwei.research.production_conversion.contract import ProtocolError


ROOT = Path(__file__).parents[1]


def _write(path: Path, value: dict) -> Path:
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n")
    return path


def _release() -> tuple[EntryRecoveryProtocol, dict]:
    protocol = EntryRecoveryProtocol.load()
    image_id = "sha256:" + "b" * 64
    commit = "a" * 40
    fixture = {
        "status": "PASS", "loaded_path": str(EMBEDDED_ORIGINAL_PROTOCOL),
        "protocol_sha256": protocol.document["root_cause_and_only_change"]["embedded_protocol_sha256"],
        "final_image_id": image_id, "image_git_commit": commit,
        "network_mode": "none", "real_effect_read": False,
        "audit_invoked": False, "production_authorization": "none",
    }
    document = build_release_document(
        protocol=protocol, created_at="2026-08-20T10:30:00+00:00",
        implementation_git_commit=commit, origin_main_commit=commit,
        image_id=image_id, image_platform="linux/arm64", image_git_commit=commit,
        base_image_id=protocol.document["r3_authority"]["image_id"],
        sealed_effect=expected_sealed(protocol), daemon_fixture=fixture,
    )
    return protocol, document


def test_protocol_freezes_only_embedded_allowed_path() -> None:
    protocol = EntryRecoveryProtocol.load()
    change = protocol.document["root_cause_and_only_change"]
    assert change["rejected_path"] == "/inputs/original-protocol.yaml"
    assert change["rejected_path_must_not_be_mounted_or_used"] is True
    assert change["embedded_allowed_path"] == str(EMBEDDED_ORIGINAL_PROTOCOL)
    assert protocol.document["objective"]["audit_semantics_change"] is False
    assert protocol.document["objective"]["additional_portfolio_attempt_count"] == 0


def test_release_is_nonexecuting_and_binds_daemon_fixture(tmp_path: Path) -> None:
    protocol, document = _release()
    release = EntryRecoveryScope.load(
        _write(tmp_path / "scope.json", document), protocol, compose_path=COMPOSE_PATH
    )
    assert release.scope["authority"]["execution_authorized"] is False
    assert release.scope["authority"]["sealed_effect_read_authorized"] is False
    assert release.scope["daemon_fixture"]["status"] == "PASS"
    assert release.scope["daemon_fixture"]["loaded_path"] == str(EMBEDDED_ORIGINAL_PROTOCOL)
    assert release.scope["execution"]["family_portfolio_attempts_consumed"] == 2


@pytest.mark.parametrize("mutation", ["path", "mount", "command", "network", "count", "fixture"])
def test_release_rejects_rehashed_boundary_drift(tmp_path: Path, mutation: str) -> None:
    protocol, document = _release()
    changed = copy.deepcopy(document)
    scope = changed["scope"]
    if mutation == "path":
        scope["container"]["embedded_original_protocol_path"] = "/inputs/original-protocol.yaml"
    elif mutation == "mount":
        scope["container"]["mounts"].append({"source": ".", "target": "/workspace", "mode": "ro"})
    elif mutation == "command":
        scope["container"]["command"].extend(["--original-protocol", "/inputs/original-protocol.yaml"])
    elif mutation == "network":
        scope["container"]["network_mode"] = "bridge"
    elif mutation == "count":
        scope["execution"]["additional_portfolio_attempt_count"] = 1
    else:
        scope["daemon_fixture"]["loaded_path"] = "/inputs/original-protocol.yaml"
    changed["recovery_scope_sha256"] = canonical_sha256(scope)
    with pytest.raises(ProtocolError):
        EntryRecoveryScope.load(
            _write(tmp_path / f"{mutation}.json", changed),
            protocol, compose_path=COMPOSE_PATH,
        )


def test_approval_binds_exact_scope_and_has_no_broader_authority(tmp_path: Path) -> None:
    protocol, document = _release()
    release = EntryRecoveryScope.load(
        _write(tmp_path / "scope.json", document), protocol, compose_path=COMPOSE_PATH
    )
    approval = {
        "schema_version": "m6-production-head30-audit-entrypoint-recovery-approval-v1",
        "recovery_scope_sha256": release.sha256, "action": ACTION,
        "approved_at": "2026-08-20T10:31:00+00:00", "consumed": False,
        "sealed_effect_read_authorized": True, "independent_audit_write_authorized": True,
        "qlib_mount_authorized": False, "runner_invocation_authorized": False,
        "model_fit_prediction_backtest_authorized": False,
        "experiment_ledger_write_authorized": False,
        "external_network_authorized": False, "env_or_secret_read_authorized": False,
        "production_authorization": "none",
    }
    EntryRecoveryApproval.load(_write(tmp_path / "approval.json", approval), release)
    approval["runner_invocation_authorized"] = True
    with pytest.raises(ProtocolError, match="authority differs"):
        EntryRecoveryApproval.load(_write(tmp_path / "bad.json", approval), release)


def test_inherited_audit_semantics_match_r3() -> None:
    bundle = _synthetic_bundle()
    digest = canonical_sha256(bundle)
    report = {
        "decision": bundle["result"]["decision"],
        "first_pass_bundle_sha256": digest,
        "replay_bundle_sha256": digest,
        "result_sha256": canonical_sha256(bundle["result"]),
    }
    checks, *_ = _audit_documents(
        bundle, copy.deepcopy(bundle), report,
        first_sha=digest, replay_sha=digest,
        converter_protocol_sha256=bundle["converter_protocol_sha256"],
        release_engineering_sha256=bundle["release_engineering_sha256"],
    )
    assert all(checks.values())


def test_compose_has_daemon_fixture_and_no_old_protocol_mount() -> None:
    document = yaml.safe_load(
        (ROOT / "compose.m6-production-head30-audit-entrypoint-recovery.yaml").read_text()
    )
    services = document["services"]
    fixture = services["m6-production-head30-audit-entrypoint-recovery-fixture"]
    real = services["m6-production-head30-audit-entrypoint-recovery"]
    for service in (fixture, real):
        assert service["network_mode"] == "none"
        assert service["read_only"] is True
        assert service["cap_drop"] == ["ALL"]
    assert fixture["command"][-1] == "--self-test"
    sources = [mount["source"] for mount in real["volumes"]]
    targets = [mount["target"] for mount in real["volumes"]]
    assert not any(source in {".", "./"} for source in sources)
    assert "/inputs/original-protocol.yaml" not in targets
    assert "/inputs/original-protocol.yaml" not in real["command"]
    assert str(EMBEDDED_ORIGINAL_PROTOCOL) not in targets
    effect = next(mount for mount in real["volumes"] if mount["target"] == "/outputs")
    assert effect["read_only"] is True
