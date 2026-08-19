from pathlib import Path

import pytest
import yaml

from shaiwei.research.rf_0b.contract import (
    RECOVERY_SCOPE_SHA256,
    RFBError,
    RFBRecovery,
    active_output_paths,
)


ROOT = Path(__file__).parents[1]
COMPOSE = ROOT / "compose.ts-rf-0b.yaml"


def test_recovery_scope_is_frozen_with_zero_consumption() -> None:
    recovery = RFBRecovery.load_if_present()
    assert recovery is not None and recovery.sha256 == RECOVERY_SCOPE_SHA256
    parent = recovery.document["parent_scope"]
    assert parent["market_or_ledger_data_read_before_failure"] is False
    assert parent["outputs_created_before_failure"] == "marker_only"
    assert parent["original_scope_closed_no_same_scope_rerun"] is True
    assert recovery.document["recovery"]["candidate_or_effect_attempts_consumed"] == 0
    assert active_output_paths(recovery).root.name.endswith("-r2")
    assert active_output_paths(None).root.name.endswith("preflight-v1")


def test_recovery_validates_parent_marker_evidence() -> None:
    recovery = RFBRecovery.load_if_present()
    assert recovery is not None
    recovery.validate_parent_evidence()
    document = {**recovery.document, "parent_scope": {**recovery.document["parent_scope"]}}
    document["parent_scope"]["marker_sha256"] = "0" * 64
    with pytest.raises(RFBError, match="evidence differs"):
        RFBRecovery(document).validate_parent_evidence()


def test_compose_original_output_is_read_only_and_r2_is_the_only_writable() -> None:
    document = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))
    for name in ("rf-0b-profile", "rf-0b-auditor"):
        volumes = document["services"][name]["volumes"]
        writable = [row for row in volumes if row["read_only"] is False]
        assert len(writable) == 1
        assert writable[0]["source"].endswith("rf-0b-field-identity-preflight-v1-r2")
        originals = [
            row for row in volumes
            if row["source"].endswith("rf-0b-field-identity-preflight-v1")
            and not row["source"].endswith("-r2")
        ]
        assert originals and all(row["read_only"] is True for row in originals)
