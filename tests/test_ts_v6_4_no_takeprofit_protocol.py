from pathlib import Path

import yaml

from shaiwei.provenance import CONTROLLED_FILES
from shaiwei.research.trend_swing.v6_4.contract import PROTOCOL_SHA256, V64Scope


ROOT = Path(__file__).parents[1]
COMPOSE = ROOT / "compose.ts-v6-4-no-takeprofit.yaml"


def test_protocol_freezes_final_budget_and_exactly_one_removed_mechanism() -> None:
    scope = V64Scope.load()
    assert scope.sha256 == PROTOCOL_SHA256
    change = scope.document["exit_mechanism_change"]
    assert change["fixed_take_profit"] == "REMOVED"
    assert change["no_new_exit_or_threshold_added"] is True
    assert change["stop_risk_time_parameters_unchanged"] is True
    budget = scope.document["user_rulings_20260818_binding"]
    assert budget["ts_lane_remaining_effect_protocol_budget_before_this_protocol"] == 1
    assert budget["budget_after_this_protocol"] == 0
    assert budget["on_reject"] == "authoritative_ts_lane_closure_with_evidence_preserved"
    assert scope.document["selected_effect_point"]["event_subset"] == (
        "full_parent_188_discovery_events_no_quality_filter"
    )
    assert scope.document["production_authorization"] == "none"


def test_dsr_trial_count_and_firewall_are_frozen() -> None:
    scope = V64Scope.load()
    gate = scope.document["discovery_gate"]
    assert gate["deflated_sharpe"]["trial_count"] == 5
    assert gate["candidate"]["pre_fee_per_trade_expectancy_strictly_positive"] is True
    firewall = scope.document["attempt_and_firewall"]
    assert firewall["strategy_effect_attempt_count_on_first_effect_read"] == 1
    assert firewall["holdout_outcomes_read"] == "forbidden_by_this_protocol"
    assert scope.document["ranking_lineage"]["w7"]["use_w7_or_any_2024_2026_score"] == "forbidden"


def test_docker_boundary_is_offline_read_only_and_secret_free() -> None:
    document = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))
    serialized = COMPOSE.read_text(encoding="utf-8")
    assert ".env" not in serialized and "docker.sock" not in serialized
    for service in document["services"].values():
        assert service["network_mode"] == "none"
        assert service["read_only"] is True
        assert service["restart"] == "no"
        assert service["cap_drop"] == ["ALL"]
    fixture = document["services"]["ts-v6-4-effect-fixture"]
    assert fixture["build"]["network"] == "none"
    for name in ("ts-v6-4-effect-runner", "ts-v6-4-effect-auditor", "ts-v6-4-effect-preflight"):
        service = document["services"][name]
        writable = [row for row in service["volumes"] if row["read_only"] is False]
        assert len(writable) == 1
        assert writable[0]["source"].endswith("ts-v6-4-no-takeprofit-effect-v1")
    assert "Dockerfile.ts-v6-4-no-takeprofit" in CONTROLLED_FILES
    assert COMPOSE.name in CONTROLLED_FILES


def test_v6_4_package_respects_module_size_and_no_generic_dumping_ground() -> None:
    package = ROOT / "src/shaiwei/research/trend_swing/v6_4"
    sizes = {path.name: len(path.read_text(encoding="utf-8").splitlines()) for path in package.glob("*.py")}
    assert sizes and max(sizes.values()) <= 400
    assert not ({"utils.py", "helpers.py", "common.py"} & set(sizes))
