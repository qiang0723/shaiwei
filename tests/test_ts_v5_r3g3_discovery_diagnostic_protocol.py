from pathlib import Path

import pytest
import yaml

from shaiwei.research.trend_swing.r3g3.contract import (
    DiagnosticProtocol,
    verify_entrypoint_recovery,
)
from shaiwei.research.trend_swing.r3g3.evidence import R3G3Error


ROOT = Path(__file__).parents[1]
PROTOCOL = ROOT / "config/ts_v5_r3g3_discovery_diagnostic_v1.yaml"
RECOVERY = ROOT / "config/ts_v5_r3g3_discovery_diagnostic_entrypoint_recovery_v1.yaml"


def _load() -> dict:
    return yaml.safe_load(PROTOCOL.read_text(encoding="utf-8"))


def test_diagnostic_is_result_known_but_detail_blind_and_zero_attempt() -> None:
    document = _load()
    assert document["status"] == (
        "RESULT_KNOWN_DETAIL_BLIND_DIAGNOSTIC_PROTOCOL_FROZEN_PENDING_IMPLEMENTATION"
    )
    execution = document["execution_contract"]
    assert execution["strategy_effect_attempt_increment"] == 0
    assert execution["model_training_prediction_or_backtest"] == "forbidden"
    assert execution["parameter_search_or_threshold_change"] == "forbidden"
    assert execution["external_network_or_provider"] == "forbidden"
    assert execution["env_or_secret_read"] == "forbidden"
    assert execution["deepseek_calls"] == 0
    assert execution["paper_web_scheduler_or_production_change"] == "forbidden"


def test_diagnostic_reads_only_first_pass_discovery_and_keeps_holdout_closed() -> None:
    boundary = _load()["allowed_read_boundary"]
    assert boundary["partition"] == "discovery"
    assert boundary["start"] == "20210104"
    assert boundary["end"] == "20231229"
    assert boundary["pass"] == "first_pass"
    assert boundary["detailed_parquet_each_point"] == {
        "scenario": "base_1x",
        "files": ["nav.parquet", "orders.parquet", "trades.parquet"],
    }
    assert boundary["replay_detail_read"] == "forbidden"
    assert boundary["holdout_path_or_value_read"] == "forbidden"
    assert boundary["partial_2026_path_or_value_read"] == "forbidden"
    assert boundary["raw_market_security_list_score_prediction_or_model_read"] == "forbidden"


def test_questions_groupings_and_denominators_are_frozen_before_detail_read() -> None:
    document = _load()
    assert [row["id"] for row in document["diagnostic_questions"]] == [
        "DQ1_PARTICIPATION_FUNNEL",
        "DQ2_SIZING_AND_EXECUTION",
        "DQ3_TRADE_ECONOMICS",
        "DQ4_COST_AND_LOCAL_ROBUSTNESS",
    ]
    assert [row["label"] for row in document["frozen_groupings"]["holding_trade_days"]] == [
        "D01_05",
        "D06_10",
        "D11_15",
        "D16_PLUS",
    ]
    denominator = document["frozen_groupings"]["denominator_policy"]
    assert denominator["invested_day"] == "position_count_strictly_positive_at_daily_close"
    assert denominator["new_entry_day"] == "at_least_one_filled_buy_order"
    assert document["driver_classification"]["causal_claim_from_observational_slice"] == (
        "forbidden"
    )


def test_parent_result_and_artifact_identity_are_immutable() -> None:
    parent = _load()["frozen_parent"]
    assert parent["authoritative_verdict"] == "REJECT_TS_V5_R3G2_DISCOVERY"
    assert parent["strategy_effective"] == "REJECT"
    assert parent["effect_attempts_already_consumed"] == 3
    assert parent["result_report"]["sha256"] == (
        "515e891bec3e43e94f62e3796804bcf2283215395aab58eccaf74a7e35ffd528"
    )
    assert parent["independent_audit"]["sha256"] == (
        "79de6dabf229630036af67ab840176a1f31cf19b5a2c4231a30b72d60866046f"
    )
    assert parent["first_pass_manifest"]["bundle_sha256"] == (
        "f36bc46fe8cd499f19c886951a761235cfdbd89cb8d0954172279d5d774f12a9"
    )


def test_report_is_aggregate_portable_and_non_sensitive() -> None:
    report = _load()["report_contract"]
    assert report["audience"] == "product_stakeholders"
    assert report["answer_first"] is True
    assert report["portable_self_contained_html"] is True
    assert report["canonical_artifact_json"] is True
    assert report["source_paths_are_project_relative_and_non_sensitive"] is True
    assert report["raw_security_trade_or_order_rows_in_report"] == "forbidden"
    assert _load()["frozen_groupings"]["security_and_industry_labels_in_tracked_outputs"] == (
        "forbidden"
    )


def test_terminal_boundary_does_not_implicitly_authorize_ts_v6() -> None:
    boundary = _load()["terminal_boundary"]
    assert boundary == {
        "r3g2_verdict_may_change": False,
        "holdout_may_open": False,
        "ts_v6_effect_authorized": False,
        "simulation_or_production_authorized": False,
        "next_step_if_diagnostic_passes": (
            "separately_freeze_one_mechanically_distinct_ts_v6_hypothesis"
        ),
    }


def test_entrypoint_recovery_is_bound_to_original_protocol_and_zero_attempt(tmp_path) -> None:
    protocol = DiagnosticProtocol.load(PROTOCOL)
    assert len(verify_entrypoint_recovery(RECOVERY, protocol)) == 64
    document = yaml.safe_load(RECOVERY.read_text(encoding="utf-8"))
    document["recovery"]["strategy_effect_attempt_increment"] = 1
    tampered = tmp_path / "recovery.yaml"
    tampered.write_text(yaml.safe_dump(document), encoding="utf-8")
    with pytest.raises(R3G3Error, match="recovery scope differs"):
        verify_entrypoint_recovery(tampered, protocol)
