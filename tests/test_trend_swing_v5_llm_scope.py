from decimal import Decimal
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
SCOPE = ROOT / "config/ts_v5_llm_research_scope_v1.yaml"


def load_scope() -> dict[str, object]:
    return yaml.safe_load(SCOPE.read_text(encoding="utf-8"))


def test_scope_is_precise_but_not_execution_authority() -> None:
    scope = load_scope()

    assert scope["status"] == "AWAITING_EXPLICIT_USER_APPROVAL"
    assert scope["execution_authorized"] is False
    assert scope["user_approval_received"] is False
    assert scope["deepseek_api_called"] is False
    assert scope["production_authorization"] == "none"
    assert scope["attempt_contract"]["completed_response_target_exact"] == 12
    assert scope["attempt_contract"]["independent_slots"] == 6
    assert scope["attempt_contract"]["adversarial_revision_slots"] == 6
    assert scope["attempt_contract"]["replacement_response_authorized"] is False


def test_scope_cost_bound_is_recomputed_exactly() -> None:
    cost = load_scope()["cost_contract"]
    per_slot = (
        Decimal(cost["maximum_prompt_tokens_per_slot"])
        * Decimal(cost["input_cache_miss_usd_per_million"])
        + Decimal(cost["maximum_output_tokens_per_slot"])
        * Decimal(cost["output_usd_per_million"])
    ) / Decimal("1000000")
    planned = per_slot * 12

    assert planned == Decimal(cost["planned_worst_case_all_cache_miss_usd"])
    assert planned < Decimal(cost["batch_hard_ceiling_usd"])


def test_scope_forbids_market_identity_effect_and_secrets() -> None:
    scope = load_scope()
    forbidden = set(scope["send_forbidden"])

    assert {
        "raw_or_row_level_market_data",
        "security_code_name_or_list",
        "holdings_orders_fills_or_signals",
        "discovery_return_or_risk_metrics",
        "sealed_validation_or_locked_test",
        "forward_or_production_results",
        "local_absolute_paths",
        "api_key_or_other_secret",
    }.issubset(forbidden)
    assert scope["next_authority_if_approved"]["market_or_effect_read"] is False
    assert scope["next_authority_if_approved"]["parameter_search_or_backtest"] is False
    assert scope["next_authority_if_approved"]["paper_web_or_production"] is False
