from __future__ import annotations

from tools.p2_star50_effect.contract import load_protocol, verify_frozen_inputs


def test_frozen_thresholds_and_pressure_mapping_are_exact():
    protocol = load_protocol()
    assert protocol["portfolio"]["account_rmb"] == 100_000_000
    assert protocol["portfolio"]["topk"] == 10
    assert protocol["portfolio"]["n_drop"] == 2
    assert protocol["portfolio"]["rebalance_trade_days"] == 10
    assert protocol["model"]["seed"] == 42
    assert protocol["model"]["label"] == "Ref($open,-11)/Ref($open,-1)-1"
    assert protocol["execution"]["cost_multipliers"] == [1.0, 1.5, 2.0]
    assert protocol["execution"]["extra_slippage_each_side"] == 0.001
    assert {
        row["name"]: row["frozen_model_window"]
        for row in protocol["evaluation"]["pressure_periods"]
    } == {
        "star_2023_drawdown": "STAR-W1",
        "microcap_2024": "STAR-W2",
        "volume_price_2026h1": "STAR-W3",
    }


def test_all_p2_1_and_v2_hashes_and_qlib_tree_are_still_frozen():
    evidence = verify_frozen_inputs(load_protocol())
    assert evidence["qlib"]["artifact_sha256"] == (
        "b8f736ef9bc9e31cc236a81ca281a23e904789fb5ec87caa9195b572c6b78729"
    )
    assert evidence["comparator_bound"] is False
    assert evidence["upstream_reports_recalculated"] is False
