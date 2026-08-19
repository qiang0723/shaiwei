from pathlib import Path

import pytest
import yaml

from shaiwei.research.rf_0c.contract import (
    RECOVERY_SCOPE_SHA256,
    RFCError,
    RFCRecovery,
    active_root,
)


ROOT = Path(__file__).parents[1]
COMPOSE = ROOT / "compose.ts-rf-0c.yaml"


def test_recovery_scope_is_frozen_with_fixture_gate_first() -> None:
    recovery = RFCRecovery.load_if_present()
    assert recovery is not None and recovery.sha256 == RECOVERY_SCOPE_SHA256
    parent = recovery.document["parent_scope"]
    assert parent["failure_class"] == "fixture_gate_did_not_run_before_the_real_profile"
    assert parent["original_scope_closed_no_same_scope_rerun"] is True
    assert recovery.document["recovery"]["candidate_or_effect_attempts_consumed"] == 0
    assert recovery.document["authority"]["fixture_must_pass_before_profile"] is True
    assert active_root(recovery).name.endswith("-r2")
    assert active_root(None).name.endswith("preflight-v1")


def test_recovery_validates_parent_evidence() -> None:
    recovery = RFCRecovery.load_if_present()
    assert recovery is not None
    recovery.validate_parent_evidence()
    document = {**recovery.document, "parent_scope": {**recovery.document["parent_scope"]}}
    document["parent_scope"]["profile_sha256"] = "0" * 64
    with pytest.raises(RFCError, match="evidence differs"):
        RFCRecovery(document).validate_parent_evidence()


def test_fixture_service_mounts_ledgers_and_sealed_registry() -> None:
    document = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))
    fixture = document["services"]["rf-0c-fixture"]
    sources = [row["source"] for row in fixture["volumes"]]
    assert any("llm_factor_attempts_v2.csv" in row for row in sources)
    assert any("identity_registry.json" in row for row in sources)
    assert all(row["read_only"] is True for row in fixture["volumes"])
    for name in ("rf-0c-profile", "rf-0c-auditor"):
        writable = [row for row in document["services"][name]["volumes"] if row["read_only"] is False]
        assert len(writable) == 1
        assert writable[0]["source"].endswith("rf-0c-field-identity-preflight-v1-r2")
