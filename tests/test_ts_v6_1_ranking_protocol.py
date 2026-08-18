from pathlib import Path

import yaml

from shaiwei.provenance import CONTROLLED_FILES
from shaiwei.research.trend_swing.v6_1.contract import PROTOCOL_SHA256, V61Scope


ROOT = Path(__file__).parents[1]
COMPOSE = ROOT / "compose.ts-v6-1-ranking.yaml"


def test_protocol_freezes_ranking_mechanism_and_keeps_all_effect_authority_closed() -> None:
    scope = V61Scope.load()
    assert scope.sha256 == PROTOCOL_SHA256
    assert scope.roles == (
        ("selectable_discovery", "20210104", "20231229"),
        ("frozen_stability_holdout", "20240102", "20251231"),
    )
    mechanism = scope.document["entry_quality_ranking_mechanism"]
    assert mechanism["one_primary_mechanism_change_only"] is True
    assert mechanism["hard_quality_gates_on_events"] == 0
    assert mechanism["selection_rule"]["development_top_k"] == 94
    assert mechanism["selection_rule"]["frozen_retention_fraction_of_188_parent_events"] == 0.5
    assert scope.document["inherited_parent_semantics"]["exit_rules_changed"] is False
    assert scope.document["inherited_parent_semantics"]["sizing_or_risk_rules_changed"] is False
    assert scope.document["frozen_inputs"]["new_market_or_security_data_read"] is False
    assert scope.document["result_firewall"]["forbidden"]
    assert scope.document["execution_control"]["env_or_secret_read"] is False
    assert scope.document["production_authorization"] == "none"


def test_user_rulings_and_budget_are_frozen() -> None:
    rulings = V61Scope.load().document["user_rulings_20260818"]
    budget = rulings["ruling_ts_lane_effect_budget"]
    assert budget["remaining_independent_effect_protocols"] == 2
    assert "authoritative_ts_lane_closure" in budget["exhaustion_consequence"]
    assert "MOOT" in rulings["ruling_trigger_population_redefinition"]
    successors = V61Scope.load().document["successor_requirements"]
    assert successors["preflight_go_authorizes_effect"] is False
    assert successors["separate_effect_protocol_and_user_approval_required"] is True
    assert successors["ts_lane_remaining_effect_protocol_budget_after_this_preflight"] == 2


def test_density_gates_are_inherited_not_relaxed() -> None:
    gate = V61Scope.load().document["density_dispersion_and_integration_gate"]
    assert gate["development"]["minimum_legal_events"] == 90
    assert gate["development"]["minimum_distinct_signal_days"] == 36
    assert gate["development"]["minimum_events_each_calendar_year"] == 10
    assert gate["conditional_density_only_holdout"]["minimum_distinct_signal_days"] == 20
    assert gate["conditional_density_only_holdout"]["minimum_events_each_calendar_year"] == 10
    assert gate["threshold_or_gate_change_after_profile"] == "forbidden"
    assert gate["retention_fraction_change_after_profile"] == "forbidden"


def test_docker_boundary_is_offline_read_only_and_secret_free() -> None:
    document = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))
    serialized = COMPOSE.read_text(encoding="utf-8")
    assert ".env" not in serialized and "docker.sock" not in serialized
    for service in document["services"].values():
        assert service["network_mode"] == "none"
        assert service["read_only"] is True
        assert service["restart"] == "no"
        assert service["cap_drop"] == ["ALL"]
    profile = document["services"]["ts-v6-1-ranking-profile"]
    fixture = document["services"]["ts-v6-1-ranking-fixture"]
    assert fixture["build"]["network"] == "none"
    writable = [row for row in profile["volumes"] if row["read_only"] is False]
    assert len(writable) == 1
    assert writable[0]["source"].endswith("ts-v6-1-entry-quality-ranking-preflight-v1")
    assert "Dockerfile.ts-v6-1-ranking" in CONTROLLED_FILES
    assert COMPOSE.name in CONTROLLED_FILES


def test_v6_1_package_respects_module_size_and_no_generic_dumping_ground() -> None:
    package = ROOT / "src/shaiwei/research/trend_swing/v6_1"
    sizes = {path.name: len(path.read_text(encoding="utf-8").splitlines()) for path in package.glob("*.py")}
    assert sizes and max(sizes.values()) <= 400
    assert not ({"utils.py", "helpers.py", "common.py"} & set(sizes))


def test_profile_preserves_bounded_pre_marker_failure_receipts() -> None:
    source = (ROOT / "src/shaiwei/research/trend_swing/v6_1/profile.py").read_text(encoding="utf-8")
    assert 'glob("pre_marker_failure_*.json")' in source
    assert "len(receipts) > 2" in source
    assert '"pre_marker_failure_receipts": receipts' in source
