from pathlib import Path

import pytest
import yaml

from shaiwei.research.trend_swing.v6_3.contract import (
    PARENT_FIRST_PASS_BUNDLE_SHA256,
    RECOVERY_SCOPE_SHA256,
    V63Error,
    V63Recovery,
    active_output_root,
)


ROOT = Path(__file__).parents[1]
COMPOSE = ROOT / "compose.ts-v6-3-ranked-subset.yaml"


def test_recovery_scope_is_frozen_with_zero_new_attempt_accounting() -> None:
    recovery = V63Recovery.load_if_present()
    assert recovery is not None and recovery.sha256 == RECOVERY_SCOPE_SHA256
    parent = recovery.document["parent_scope"]
    assert parent["candidate_outcome_read_before_failure"] is False
    assert parent["first_pass_or_replay_output_created"] is False
    assert parent["original_scope_closed_no_same_scope_rerun"] is True
    ruling = recovery.document["user_ruling_20260818"]
    assert ruling["failed_scope_effect_attempts_consumed"] == 0
    assert ruling["this_recovery_consumes_effect_attempts"] == 1
    assert ruling["ts_lane_budget_after_this_recovery"] == 1
    assert active_output_root(recovery).name.endswith("-r2")
    assert active_output_root(None).name.endswith("effect-v1")


def test_parent_bundle_constant_is_the_tree_bundle_not_the_manifest_file() -> None:
    assert PARENT_FIRST_PASS_BUNDLE_SHA256 == (
        "f36bc46fe8cd499f19c886951a761235cfdbd89cb8d0954172279d5d774f12a9"
    )
    assert PARENT_FIRST_PASS_BUNDLE_SHA256 != (
        "d00f2fce1c4be5cd6a8af07436416e65d015f3f053470525ee8bd5e005bac41c"
    )


def test_recovery_scope_validates_parent_evidence() -> None:
    recovery = V63Recovery.load_if_present()
    assert recovery is not None
    recovery.validate_parent_evidence()
    document = {**recovery.document, "parent_scope": {**recovery.document["parent_scope"]}}
    document["parent_scope"]["failure_receipt_sha256"] = "0" * 64
    with pytest.raises(V63Error, match="evidence differs"):
        V63Recovery(document).validate_parent_evidence()


def test_compose_original_output_is_read_only_and_r2_is_the_only_writable() -> None:
    document = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))
    for name in ("ts-v6-3-effect-runner", "ts-v6-3-effect-auditor"):
        volumes = document["services"][name]["volumes"]
        writable = [row for row in volumes if row["read_only"] is False]
        assert len(writable) == 1
        assert writable[0]["source"].endswith("ts-v6-3-ranked-subset-effect-v1-r2")
        originals = [
            row for row in volumes
            if row["source"].endswith("ts-v6-3-ranked-subset-effect-v1")
            and not row["source"].endswith("-r2")
        ]
        assert originals and all(row["read_only"] is True for row in originals)
