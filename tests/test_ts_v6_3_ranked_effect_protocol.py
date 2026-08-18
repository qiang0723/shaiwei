from pathlib import Path

import yaml

from shaiwei.provenance import CONTROLLED_FILES
from shaiwei.research.trend_swing.v6_3.contract import PROTOCOL_SHA256, V63Scope


ROOT = Path(__file__).parents[1]
COMPOSE = ROOT / "compose.ts-v6-3-ranked-subset.yaml"


def test_protocol_freezes_single_attempt_and_keeps_holdout_physically_closed() -> None:
    scope = V63Scope.load()
    assert scope.sha256 == PROTOCOL_SHA256
    assert scope.selected_point_hashes == (
        "81833a47b1edb59455c997c422bb36b63454f1da84e29696269c9c950e019784",
    )
    roles = scope.document["chronological_roles"]
    assert roles["conditional_frozen_holdout_effect"]["status"] == "NOT_PART_OF_THIS_PROTOCOL"
    assert roles["current_partial_year"]["role"] == "RESERVED_NOT_READ"
    firewall = scope.document["attempt_and_firewall"]
    assert firewall["strategy_effect_attempt_count_on_first_effect_read"] == 1
    assert firewall["holdout_outcomes_read"] == "forbidden_by_this_protocol"
    assert scope.document["ranking_lineage"]["w7"]["use_w7_or_any_2024_2026_score"] == "forbidden"
    assert scope.document["production_authorization"] == "none"


def test_effect_gate_adds_pre_fee_expectancy_without_relaxing_parent_gates() -> None:
    gate = V63Scope.load().document["discovery_gate"]
    candidate = gate["candidate"]
    assert candidate["pre_fee_per_trade_expectancy_strictly_positive"] is True
    assert candidate["minimum_closed_trades"] == 30
    assert candidate["maximum_drawdown"] == 0.20
    assert candidate["minimum_deflated_sharpe_probability"] == 0.95
    assert gate["deflated_sharpe"]["trial_count"] == 4
    assert gate["deflated_sharpe"]["r3g2_sharpe_source"] == (
        "bound_parent_first_pass_bundle_mechanical_recompute_only"
    )
    budget = V63Scope.load().document["user_rulings_20260818_binding"]
    assert budget["budget_after_this_protocol"] == 1


def test_docker_boundary_is_offline_read_only_and_secret_free() -> None:
    document = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))
    serialized = COMPOSE.read_text(encoding="utf-8")
    assert ".env" not in serialized and "docker.sock" not in serialized
    assert "w7" not in serialized.lower()
    for service in document["services"].values():
        assert service["network_mode"] == "none"
        assert service["read_only"] is True
        assert service["restart"] == "no"
        assert service["cap_drop"] == ["ALL"]
    fixture = document["services"]["ts-v6-3-effect-fixture"]
    assert fixture["build"]["network"] == "none"
    for name in ("ts-v6-3-effect-runner", "ts-v6-3-effect-auditor"):
        service = document["services"][name]
        writable = [row for row in service["volumes"] if row["read_only"] is False]
        assert len(writable) == 1
        assert "ts-v6-3-ranked-subset-effect-v1" in writable[0]["source"]
    assert "Dockerfile.ts-v6-3-ranked-subset" in CONTROLLED_FILES
    assert COMPOSE.name in CONTROLLED_FILES


def test_v6_3_package_respects_module_size_and_no_generic_dumping_ground() -> None:
    package = ROOT / "src/shaiwei/research/trend_swing/v6_3"
    sizes = {path.name: len(path.read_text(encoding="utf-8").splitlines()) for path in package.glob("*.py")}
    assert sizes and max(sizes.values()) <= 400
    assert not ({"utils.py", "helpers.py", "common.py"} & set(sizes))
