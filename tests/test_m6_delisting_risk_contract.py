from __future__ import annotations

from pathlib import Path

import yaml

from shaiwei.research.capital_feasibility.delisting_risk_contract import load_method


ROOT = Path(__file__).parents[1]


def test_m6_5c_a_contract_is_effect_sealed_and_claim_first() -> None:
    document, policy = load_method()

    assert policy.trigger_sessions == 10
    assert str(policy.trigger_price) == "1.0"
    assert document["risk_policy"]["remaining_target_weight_redistribution_authorized"] is False
    assert document["attempt_policy"]["a1_5a_claim_required_before_any_future_real_read"] is True
    assert document["attempt_policy"]["attempts_authorized_in_m6_5c_a"] == 0
    assert document["authority"]["real_effect_read_authorized"] is False
    assert document["authority"]["paper_engine_change_authorized"] is False


def test_method_module_is_small_and_has_no_runtime_or_effect_dependencies() -> None:
    path = ROOT / "src/shaiwei/research/capital_feasibility/delisting_risk.py"
    text = path.read_text(encoding="utf-8")

    assert len(text.splitlines()) <= 400
    for forbidden in (
        "pandas",
        "qlib",
        "shaiwei.paper",
        "shaiwei.ledger",
        "docker",
        "deepseek",
        "sealed_inputs",
    ):
        assert forbidden not in text.lower()


def test_every_non_fixture_authority_is_false_or_none() -> None:
    document = yaml.safe_load(
        (ROOT / "config/m6_csi800_production_head30_delisting_risk_method_v1.yaml").read_text(
            encoding="utf-8"
        )
    )
    authority = document["authority"]
    assert authority.pop("synthetic_method_fixture_authorized") is True
    assert set(authority.values()) <= {False, "none"}
