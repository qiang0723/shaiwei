from pathlib import Path

import yaml

from shaiwei.provenance import CONTROLLED_FILES
from shaiwei.research.trend_swing.ts_b.contract import PROTOCOL_SHA256, TSBScope


ROOT = Path(__file__).parents[1]
COMPOSE = ROOT / "compose.ts-b-holdout.yaml"


def test_protocol_abolishes_discovery_and_freezes_single_attempt() -> None:
    scope = TSBScope.load()
    assert scope.sha256 == PROTOCOL_SHA256
    roles = scope.document["chronological_roles"]
    assert roles["discovery_effect"]["status"] == "ABOLISHED_NO_2021_2023_READ"
    assert roles["current_partial_year"]["role"] == "RESERVED_NOT_READ"
    firewall = scope.document["attempt_and_firewall"]
    assert firewall["discovery_2021_2023_read"] == "forbidden"
    assert firewall["strategy_effect_attempt_count_on_first_effect_read"] == 1
    budget = scope.document["user_rulings_20260819_binding"]
    assert budget["budget_after_this_protocol"] == 0
    assert scope.document["production_authorization"] == "none"


def test_holdout_gate_and_dsr_are_frozen() -> None:
    gate = TSBScope.load().document["holdout_gate"]
    candidate = gate["candidate"]
    assert candidate["pre_fee_per_trade_expectancy_strictly_positive"] is True
    assert candidate["minimum_closed_trades"] == 15
    assert candidate["each_calendar_year_net_return_minimum"] == -0.05
    assert candidate["minimum_deflated_sharpe_probability"] == 0.95
    assert gate["deflated_sharpe"]["trial_count"] == 6


def test_docker_boundary_is_offline_read_only_and_secret_free() -> None:
    document = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))
    serialized = COMPOSE.read_text(encoding="utf-8")
    assert ".env" not in serialized and "docker.sock" not in serialized
    for service in document["services"].values():
        assert service["network_mode"] == "none"
        assert service["read_only"] is True
        assert service["restart"] == "no"
        assert service["cap_drop"] == ["ALL"]
    fixture = document["services"]["ts-b-effect-fixture"]
    assert fixture["build"]["network"] == "none"
    for name in ("ts-b-effect-runner", "ts-b-effect-auditor", "ts-b-effect-preflight"):
        service = document["services"][name]
        writable = [row for row in service["volumes"] if row["read_only"] is False]
        assert len(writable) == 1
        assert writable[0]["source"].endswith("ts-b-holdout-effect-v1")
    assert "Dockerfile.ts-b-holdout" in CONTROLLED_FILES
    assert COMPOSE.name in CONTROLLED_FILES


def test_ts_b_package_respects_module_size_and_no_generic_dumping_ground() -> None:
    package = ROOT / "src/shaiwei/research/trend_swing/ts_b"
    sizes = {path.name: len(path.read_text(encoding="utf-8").splitlines()) for path in package.glob("*.py")}
    assert sizes and max(sizes.values()) <= 400
    assert not ({"utils.py", "helpers.py", "common.py"} & set(sizes))
