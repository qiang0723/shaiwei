from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/ts_v5_evolutionary_research_v1.yaml"


def test_v5_governance_keeps_family_active_but_live_research_closed() -> None:
    document = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))

    assert document["family"]["family_status"] == "TS_FAMILY_ACTIVE"
    assert document["family"]["retirement_authority"] == "USER_EXPLICIT_ONLY"
    assert document["family"]["specific_version_stop_does_not_stop_family"] is True
    assert len(document["mechanism_archetypes"]) == 6
    assert len(set(document["mechanism_archetypes"])) == 6
    assert document["research_lifecycle"]["logic_revision_separate_from_parameter_optimization"]
    assert document["research_lifecycle"]["all_generated_candidates_count"]

    boundary = document["llm_boundary"]
    authority = document["current_authority"]
    assert boundary["live_call_authorized"] is False
    assert boundary["spend_authorized"] is False
    assert boundary["raw_market_data_allowed"] is False
    assert boundary["security_identity_allowed"] is False
    assert authority["deepseek_call"] is False
    assert authority["real_market_or_effect_read"] is False
    assert authority["backtest"] is False
    assert authority["production_authorization"] == "none"


def test_v5_product_risk_boundaries_are_not_research_parameters() -> None:
    document = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    constraints = document["product_constraints"]

    assert constraints == {
        "market": "A_SHARE",
        "direction": "LONG_ONLY",
        "execution_timing": "NEXT_LEGAL_OPEN",
        "t_plus_one": True,
        "maximum_entry_batches": 2,
        "averaging_down": False,
        "maximum_single_name_weight": 0.10,
        "maximum_holding_count": 7,
        "maximum_gross_weight": 0.70,
        "bj_allowed": False,
        "real_costs_and_tradeability_required": True,
    }


def test_v5_first_llm_batch_is_only_an_unapproved_bounded_proposal() -> None:
    document = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    proposal = document["llm_boundary"]["suggested_first_batch"]

    assert proposal["completed_responses_exact"] == 12
    assert proposal["calls_serial"] is True
    assert proposal["maximum_cost_usd"] == "0.50"
    assert proposal["unused_budget_carryover"] is False
    assert proposal["replacement_responses_authorized"] is False
