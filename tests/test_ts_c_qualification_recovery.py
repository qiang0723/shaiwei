from pathlib import Path

import pytest
import yaml

from shaiwei.research.trend_swing.ts_c.contract import (
    RECOVERY_SCOPE_SHA256,
    TQCError,
    TQCRecovery,
    active_root,
)


ROOT = Path(__file__).parents[1]
COMPOSE = ROOT / "compose.ts-c-qualification.yaml"


def test_recovery_scope_is_frozen_with_gates_unchanged() -> None:
    recovery = TQCRecovery.load_if_present()
    assert recovery is not None and recovery.sha256 == RECOVERY_SCOPE_SHA256
    parent = recovery.document["parent_scope"]
    assert parent["profile_values_computed_or_written_before_failure"] is False
    assert parent["original_scope_closed_no_same_scope_rerun"] is True
    assert recovery.document["recovery"]["density_gates_unchanged"] is True
    assert recovery.document["recovery"]["candidate_or_effect_attempts_consumed"] == 0
    assert active_root(recovery).name.endswith("-r2")
    assert active_root(None).name.endswith("qualification-v1")


def test_recovery_validates_parent_marker_evidence() -> None:
    recovery = TQCRecovery.load_if_present()
    assert recovery is not None
    recovery.validate_parent_evidence()
    document = {**recovery.document, "parent_scope": {**recovery.document["parent_scope"]}}
    document["parent_scope"]["marker_sha256"] = "0" * 64
    with pytest.raises(TQCError, match="evidence differs"):
        TQCRecovery(document).validate_parent_evidence()


def test_compose_original_output_is_read_only_and_r2_is_the_only_writable() -> None:
    document = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))
    for name in ("ts-c-profile", "ts-c-auditor"):
        volumes = document["services"][name]["volumes"]
        writable = [row for row in volumes if row["read_only"] is False]
        assert len(writable) == 1
        assert writable[0]["source"].endswith("ts-c-trigger-qualification-v1-r2")
        originals = [
            row for row in volumes
            if row["source"].endswith("ts-c-trigger-qualification-v1")
            and not row["source"].endswith("-r2")
        ]
        assert originals and all(row["read_only"] is True for row in originals)
