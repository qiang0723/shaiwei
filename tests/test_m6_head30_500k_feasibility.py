from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from shaiwei.research.capital_feasibility.contract import Policy, load_protocol
from shaiwei.research.capital_feasibility.execution import Account, Target, rebalance
from shaiwei.research.capital_feasibility.fixture import build_fixture
from shaiwei.research.capital_feasibility.verdict import evaluate
from shaiwei.research.model_attribution.contract import canonical_sha256
from shaiwei.research.production_conversion.contract import ProtocolError


def _targets(
    price: str = "10",
    *,
    board: str = "MAIN",
    amount: str = "100000000",
) -> list[Target]:
    return [
        Target(
            instrument=f"{600000 + index:06d}.SH",
            score=float(30 - index),
            price=Decimal(price),
            board=board,
            trailing_median_amount=Decimal(amount),
        )
        for index in range(30)
    ]


def _passing_effect() -> dict[str, float | int]:
    return {
        "positive_window_count": 4,
        "combined_1_5x_net_excess": 0.01,
        "executable_to_ideal_pooled_nav_ratio": 0.95,
    }


def test_frozen_protocol_loads_without_real_authority() -> None:
    document = load_protocol()
    assert document["single_variable_contract"]["changed_capital_rmb"] == 500000
    assert document["frozen_input_lineage"]["windows"] == [
        "W1", "W2", "W3", "W4", "W5", "W6",
    ]
    assert document["production_authorization"] == "none"
    assert document["engineering_authority"]["real_500k_simulation_authorized"] is False


def test_protocol_mutation_fails_closed(tmp_path: Path) -> None:
    document = load_protocol()
    document["hard_feasibility_gates"]["minimum_post_rebalance_position_count"] = 19
    path = tmp_path / "mutated.yaml"
    path.write_text(yaml.safe_dump(document), encoding="utf-8")
    with pytest.raises(ProtocolError, match="hard feasibility"):
        load_protocol(path)


def test_low_price_head30_is_feasible_and_deterministic() -> None:
    first = rebalance(Account(Policy().initial_cash, {}), _targets())
    replay = rebalance(Account(Policy().initial_cash, {}), _targets())
    assert canonical_sha256(first) == canonical_sha256(replay)
    assert first["realized_position_count"] == 30
    assert first["negative_cash"] is False
    assert first["accounting_difference"] == "0.00"
    assert first["invalid_lot_fill_count"] == 0
    assert evaluate([first] * 6, _passing_effect())["decision"] == (
        "CAPITAL_FEASIBLE_RESEARCH_ONLY"
    )


def test_minimum_lot_and_capacity_fail_closed() -> None:
    expensive = rebalance(Account(Policy().initial_cash, {}), _targets("1000"))
    constrained = rebalance(
        Account(Policy().initial_cash, {}),
        _targets(amount="1000"),
    )
    assert expensive["minimum_lot_rejection_count"] == 30
    assert constrained["capacity_violation_count"] == 30
    assert evaluate([expensive] * 6, _passing_effect())["decision"] == "CAPITAL_INFEASIBLE"
    assert evaluate([constrained] * 6, _passing_effect())["decision"] == (
        "CAPITAL_INFEASIBLE"
    )


def test_main_and_star_buy_rules_are_explicit() -> None:
    main = rebalance(Account(Policy().initial_cash, {}), _targets("10", board="MAIN"))
    star = rebalance(Account(Policy().initial_cash, {}), _targets("10", board="STAR"))
    assert all(trade["quantity"] % 100 == 0 for trade in main["trades"])
    assert all(trade["quantity"] >= 200 for trade in star["trades"])
    assert main["policy"]["star_minimum"] == 200


def test_identity_and_effect_gates_fail_closed() -> None:
    with pytest.raises(ValueError, match="exactly 30"):
        rebalance(Account(Policy().initial_cash, {}), _targets()[:-1])
    bj = _targets()
    bj[-1] = Target("920001.BJ", 0.0, Decimal("10"))
    with pytest.raises(ValueError, match="Beijing"):
        rebalance(Account(Policy().initial_cash, {}), bj)
    record = rebalance(Account(Policy().initial_cash, {}), _targets())
    assert evaluate([], _passing_effect())["decision"] == "BLOCKED"
    failed_effect = {**_passing_effect(), "positive_window_count": 3}
    result = evaluate([record] * 6, failed_effect)
    assert result["decision"] == "CAPITAL_INFEASIBLE"
    assert result["checks"]["positive_windows"] is False


def test_fixture_discloses_result_blind_boundary() -> None:
    evidence = build_fixture()
    assert evidence["status"] == "PASS"
    assert evidence["real_market_data_read"] is False
    assert evidence["real_effect_read"] is False
    assert evidence["model_fit_count"] == 0
    assert evidence["production_authorization"] == "none"
