from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml


ROOT = Path(__file__).parents[1]
CONFIG_PATH = ROOT / "config/m7_star_custom_pool_moneyflow_data_v1.yaml"
EXPORT_PATH = ROOT / "config/m7_star_custom_pool_moneyflow_proposal_export_v1.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_sha256(document: object) -> str:
    payload = json.dumps(
        document,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _config() -> dict[str, object]:
    document = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    return document


def test_m7_proposal_export_is_canonical_and_review_required() -> None:
    export = json.loads(EXPORT_PATH.read_text(encoding="utf-8"))
    canonical = export["canonical_proposal"]
    request = canonical["request"]

    assert export["schema_version"] == "m5-proposal-export-v1"
    assert export["proposal_state_at_export"] == "REVIEW_REQUIRED"
    assert export["proposal_event_seq_at_export"] == 2
    assert export["proposal_head_event"]["event_sha256"] == (
        "da38d05ae213eca5a7b27a766989a64b57598412257ce72fb5e0542f978b1f0a"
    )
    assert export["canonical_proposal_sha256"] == _canonical_sha256(canonical)
    assert export["proposal_request_sha256"] == _canonical_sha256(request)
    assert request["family_id"] == "moneyflow"
    assert request["generation_mode"] == "DETERMINISTIC_CODE"
    assert request["generation_attempt_cap"] == request["candidate_cap"] == 8
    assert request["provider_call_intent_count"] == 0
    assert request["provider_budget_usd"] == "0.00"
    assert request["universe_ids"] == [
        "star-board-all-pit-v1",
        "star-board-midcap-pit-v1",
        "star-board-smallcap-pit-v1",
    ]
    authority = canonical["authority"]
    assert authority["evidence_tier"] == "PROPOSAL_ONLY"
    assert authority["authority_status"] == "NON_AUTHORITATIVE_PROPOSAL"
    assert authority["authoritative_outcome"] == "NOT_EVALUATED"
    assert authority["production_authorization"] == "none"
    assert all(
        value is False
        for key, value in authority.items()
        if key.endswith("_authorized")
    )


def test_m7_protocol_binds_tracked_proposal_and_membership_evidence() -> None:
    config = _config()
    source = config["source_proposal"]
    membership = config["membership_input"]
    export = json.loads(EXPORT_PATH.read_text(encoding="utf-8"))
    manifest = json.loads(
        (ROOT / "config/m3_star_custom_pit_manifest_v1.json").read_text(encoding="utf-8")
    )

    assert source["proposal_export_sha256"] == _sha256(EXPORT_PATH)
    assert source["canonical_proposal_sha256"] == _canonical_sha256(
        export["canonical_proposal"]
    )
    assert source["required_state_at_release_approval"] == "REVIEW_REQUIRED"
    assert source["required_event_seq_at_release_approval"] == 2
    assert membership["protocol_sha256"] == _sha256(
        ROOT / membership["protocol_path"]
    )
    assert membership["manifest_sha256"] == _sha256(
        ROOT / membership["manifest_path"]
    )
    assert membership["daily_membership_sha256"] == manifest["artifacts"][
        "daily_members"
    ]["sha256"]
    assert membership["daily_membership_row_count"] == manifest["artifacts"][
        "daily_members"
    ]["rows"]


def test_m7_data_gate_is_key_only_and_consumes_no_research_attempt() -> None:
    config = _config()
    scope = config["scope"]
    moneyflow = config["moneyflow_input"]
    boundary = config["execution_boundary"]

    assert scope["candidate_definition_count"] == 0
    assert scope["evaluation_unit_count"] == 0
    assert scope["effect_test_count"] == 0
    assert scope["generation_attempt_increment"] == 0
    assert scope["prior_moneyflow_family_attempt_count"] == 18
    assert scope["proposal_planned_after_count"] == 26
    assert moneyflow["projected_columns_only"] == ["ts_code", "trade_date"]
    assert moneyflow["numeric_moneyflow_value_read_authorized"] is False
    assert boundary["real_data_read_authorized"] is False
    assert boundary["candidate_generation_authorized"] is False
    assert boundary["label_or_return_read_authorized"] is False
    assert boundary["effect_read_authorized"] is False
    assert boundary["network_authorized"] is False
    assert boundary["production_authorization"] == "none"
    assert "candidates" not in config


def test_m7_pit_coverage_and_verdict_contract_are_frozen() -> None:
    config = _config()
    pit = config["point_in_time"]
    quality = config["quality_gate"]
    verdict = config["verdict"]

    assert pit["feature_start_date"] == "20210104"
    assert pit["feature_end_date"] == "20260630"
    assert pit["source_start_date"] == "20201231"
    assert pit["source_end_date"] == "20260629"
    assert pit["feature_available_lag_trade_days"] == 1
    assert pit["same_day_use_forbidden"] is True
    assert pit["future_source_use_forbidden"] is True
    assert quality["aggregate_member_key_coverage_minimum_by_universe"] == 0.995
    assert quality["half_year_member_key_coverage_minimum_by_universe"] == 0.99
    assert quality["worst_feature_date_member_key_coverage_minimum_by_universe"] == 0.95
    assert len(quality["complete_half_year_segments"]) == 11
    assert verdict["go"] == "GO_M7_0_DATA_COMPATIBILITY_ONLY"
    assert verdict["no_go"] == "NO_GO_M7_0_DATA_COMPATIBILITY"
    assert verdict["strategy_effective_on_go"] == "NOT_EVALUATED"
    assert verdict["production_authorization"] == "none"
    assert verdict["no_partial_pool_go"] is True
