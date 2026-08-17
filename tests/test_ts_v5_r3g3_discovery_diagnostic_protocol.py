import json
from pathlib import Path

import pytest
import yaml

from shaiwei.research.trend_swing.r3g3.contract import (
    DiagnosticProtocol,
    verify_entrypoint_recovery,
    verify_auditor_recovery,
    verify_parent_sources,
)
from shaiwei.research.trend_swing.r3g3.evidence import (
    R3G3Error,
    canonical_sha256,
    sha256_file,
)


ROOT = Path(__file__).parents[1]
PROTOCOL = ROOT / "config/ts_v5_r3g3_discovery_diagnostic_v1.yaml"
RECOVERY = ROOT / "config/ts_v5_r3g3_discovery_diagnostic_entrypoint_recovery_v1.yaml"
RECOVERY_R2 = (
    ROOT / "config/ts_v5_r3g3_discovery_diagnostic_parent_authority_recovery_v1.yaml"
)
AUDIT_RECOVERY = (
    ROOT / "config/ts_v5_r3g3_discovery_diagnostic_auditor_entrypoint_recovery_v1.yaml"
)
AUDIT_SERIALIZATION_RECOVERY = (
    ROOT / "config/ts_v5_r3g3_discovery_diagnostic_auditor_serialization_recovery_v1.yaml"
)


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
    digest, action = verify_entrypoint_recovery(RECOVERY, protocol)
    assert len(digest) == 64 and "ENTRYPOINT_RECOVERY" in action
    document = yaml.safe_load(RECOVERY.read_text(encoding="utf-8"))
    document["recovery"]["strategy_effect_attempt_increment"] = 1
    tampered = tmp_path / "recovery.yaml"
    tampered.write_text(yaml.safe_dump(document), encoding="utf-8")
    with pytest.raises(R3G3Error, match="recovery scope differs"):
        verify_entrypoint_recovery(tampered, protocol)


def test_parent_authority_uses_pre_audit_report_and_final_independent_audit(tmp_path) -> None:
    protocol_document = _load()
    inputs, discovery = tmp_path / "inputs", tmp_path / "inputs/discovery"
    discovery.mkdir(parents=True)
    documents = {
        "report.json": {
            "verdict": "REJECT_TS_V5_R3G2_DISCOVERY",
            "strategy_effective": "PENDING_INDEPENDENT_AUDIT",
            "holdout": None,
        },
        "parent-audit.json": {
            "independent_audit": "PASS",
            "verdict": "REJECT_TS_V5_R3G2_DISCOVERY",
            "strategy_effective": "REJECT",
        },
        "first-pass-summary.json": {},
        "partition-summary.json": {},
    }
    for name, document in documents.items():
        (inputs / name).write_text(json.dumps(document, sort_keys=True), encoding="utf-8")
    files = {"pass_summary.json": sha256_file(inputs / "first-pass-summary.json")}
    manifest = {
        "schema_version": "ts-v5-r3g2-effect-pass-manifest-v1",
        "file_count": 1,
        "files": files,
        "bundle_sha256": canonical_sha256(files),
    }
    manifest_path = inputs / "first-pass-manifest.json"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
    parent = protocol_document["frozen_parent"]
    parent["result_report"]["sha256"] = sha256_file(inputs / "report.json")
    parent["independent_audit"]["sha256"] = sha256_file(inputs / "parent-audit.json")
    parent["first_pass_summary"]["sha256"] = sha256_file(inputs / "first-pass-summary.json")
    parent["discovery_partition_summary"]["sha256"] = sha256_file(
        inputs / "partition-summary.json"
    )
    parent["first_pass_manifest"]["sha256"] = sha256_file(manifest_path)
    parent["first_pass_manifest"]["bundle_sha256"] = manifest["bundle_sha256"]
    protocol_path = tmp_path / "protocol.yaml"
    protocol_path.write_text(
        yaml.safe_dump(protocol_document, sort_keys=False), encoding="utf-8"
    )

    identity = verify_parent_sources(DiagnosticProtocol.load(protocol_path), inputs)
    assert identity["first_pass_bundle_sha256"] == manifest["bundle_sha256"]


def test_parent_authority_recovery_binds_prior_authorization(tmp_path) -> None:
    protocol = DiagnosticProtocol.load(PROTOCOL)
    document = yaml.safe_load(RECOVERY_R2.read_text(encoding="utf-8"))
    assert document["parent_protocol_sha256"] == protocol.sha256
    assert document["prior_recovery"]["authorization_sha256"] == (
        "88f37f3754b8e8768dc11f00000d6dfcf75dd6ef66a01c5e7363a68791b55b8d"
    )
    authorization = tmp_path / "authorization.json"
    authorization.write_text('{"fixture":true}', encoding="utf-8")
    document["prior_recovery"]["authorization_sha256"] = sha256_file(authorization)
    recovery = tmp_path / "recovery-r2.yaml"
    recovery.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    digest, action = verify_entrypoint_recovery(recovery, protocol, authorization)
    assert len(digest) == 64 and "PARENT_AUTHORITY_RECOVERY" in action


def test_auditor_recovery_binds_completed_diagnostic(tmp_path) -> None:
    protocol = DiagnosticProtocol.load(PROTOCOL)
    diagnostic = tmp_path / "diagnostic"
    diagnostic.mkdir()
    for name in ("authorization.json", "report.json", "manifest.json"):
        (diagnostic / name).write_text(json.dumps({"name": name}), encoding="utf-8")
    document = yaml.safe_load(AUDIT_RECOVERY.read_text(encoding="utf-8"))
    document["frozen_diagnostic"] = {
        f"{name.removesuffix('.json').replace('-', '_')}_sha256": sha256_file(diagnostic / name)
        for name in ("authorization.json", "report.json", "manifest.json")
    }
    recovery = tmp_path / "audit-recovery.yaml"
    recovery.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    digest, action = verify_auditor_recovery(recovery, protocol, diagnostic)
    assert len(digest) == 64 and action.endswith("AUDIT_ENTRYPOINT_RECOVERY_ONCE")


def test_auditor_serialization_recovery_keeps_same_diagnostic_bindings(tmp_path) -> None:
    protocol = DiagnosticProtocol.load(PROTOCOL)
    diagnostic = tmp_path / "diagnostic"
    diagnostic.mkdir()
    for name in ("authorization.json", "report.json", "manifest.json"):
        (diagnostic / name).write_text(json.dumps({"name": name}), encoding="utf-8")
    document = yaml.safe_load(AUDIT_SERIALIZATION_RECOVERY.read_text(encoding="utf-8"))
    document["frozen_diagnostic"].update(
        {
            f"{name.removesuffix('.json').replace('-', '_')}_sha256": sha256_file(
                diagnostic / name
            )
            for name in ("authorization.json", "report.json", "manifest.json")
        }
    )
    recovery = tmp_path / "audit-serialization-recovery.yaml"
    recovery.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    digest, action = verify_auditor_recovery(recovery, protocol, diagnostic)
    assert len(digest) == 64 and action.endswith("AUDIT_SERIALIZATION_RECOVERY_ONCE")
