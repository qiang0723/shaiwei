from __future__ import annotations

import hashlib
from pathlib import Path

import yaml


ROOT = Path(__file__).parents[1]
CONFIG = ROOT / "config/m5_strategy_factory_truth_projection_v3.yaml"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_m5_web_authority_projection_protocol_is_frozen_and_source_backed() -> None:
    document = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    assert document["schema_version"] == "m5-strategy-factory-truth-projection-addendum-v1"
    assert document["published_at"] == "2026-08-06T17:30:40+08:00"

    protocol = document["protocol"]
    assert _sha256(ROOT / protocol["path"]) == protocol["sha256"]

    base = document["base_projection"]
    assert base["preserve_prior_snapshot"] is True
    assert base["prior_snapshot_id"] == (
        "fae1c53c410213e58bd10d938a5854afdd2cce1e3f4c9acd7affb73624c94a6b"
    )
    assert base["prior_snapshot_sha256"] == (
        "36f750639f5643a67ac0c2f9eb7505949542a9404edad9ff3d7fb970f7bd6f2b"
    )
    assert _sha256(ROOT / base["catalog_path"]) == base["catalog_sha256"]
    assert _sha256(ROOT / base["authority_addendum_path"]) == base["authority_addendum_sha256"]

    evidence = document["evidence"]
    assert [item["evidence_id"] for item in evidence] == [
        "lineage_release_scope",
        "lineage_real_run_acceptance",
        "platform_route_review",
    ]
    for item in evidence:
        assert _sha256(ROOT / item["path"]) == item["sha256"]


def test_m5_web_authority_projection_preserves_failure_semantics_and_authority() -> None:
    document = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    decision = document["decision"]
    assert decision["family_id"] == "fundamental_dynamic"
    assert decision["universe_ids"] == [
        "star50-official-pit-v2",
        "star-board-midcap-pit-v1",
        "star-board-smallcap-pit-v1",
    ]
    assert decision["gate_stage"] == "SOURCE_LINEAGE_FEASIBILITY"
    assert decision["terminal_state"] == "BLOCKED_DATA"
    assert decision["evidence_tier"] == "LINEAGE_NO_GO_ONLY"
    assert decision["verdict"] == "NO_GO_M5_2_SOURCE_LINEAGE_PREEXECUTION"
    assert decision["strategy_effective"] == "NOT_EVALUATED"
    assert decision["effect_read"] is False
    assert (
        decision["conflict_group_count"],
        decision["forward_only_group_count"],
        decision["pit_resolved_group_count"],
    ) == (23, 23, 0)
    assert decision["route_status"] == "PAUSE"
    assert decision["production_authorization"] == "none"
    assert decision["release_consumed"] is True
    assert decision["active_task"] is False

    invariants = document["invariants"]
    assert invariants == {
        "authority_projection_version": "m5-strategy-factory-authority-projection-v1",
        "prior_registered_program_count": 8,
        "active_authorized_task_count": 0,
        "formal_factor_admission_count": 0,
        "external_calls_made_by_projection": 0,
        "production_authorization": "none",
        "bse_count": 0,
    }
