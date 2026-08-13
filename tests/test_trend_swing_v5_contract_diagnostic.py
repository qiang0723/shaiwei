from copy import deepcopy
from pathlib import Path

from shaiwei.research.trend_swing.v5_contract_diagnostic import diagnose_document
from shaiwei.research.trend_swing.v5_models import Mechanism
from test_trend_swing_v5_candidate_contract import candidate_document


def rule_ids(result: dict[str, object]) -> set[str]:
    return {item["rule_id"] for item in result["diagnostic_violations"]}  # type: ignore[index]


def test_hidden_parameter_and_feature_rules_are_contract_projection_gaps() -> None:
    document = candidate_document("VOLATILITY_ADAPTIVE_PULLBACK")
    document["entry_design"]["cancellation_rules"] = ["STRUCTURE_LOW_BROKEN", "MAX_WAIT_EXPIRED"]
    document["parameter_slots"][0]["minimum"] = "5"
    document["required_features"] = [
        "ADJUSTED_DAILY_OHLCV", "COMPLETE_WEEK_OHLCV", "DAILY_ATR", "WEEKLY_VWAP",
        "MARKET_AND_SECTOR_TREND",
    ]

    result = diagnose_document(document, Mechanism.VOLATILITY_ADAPTIVE_PULLBACK)

    assert {
        "MANDATORY_CANCELLATION_SET", "PARAMETER_SAFE_RANGE", "MANDATORY_FEATURE_SET",
    }.issubset(rule_ids(result))
    assert "JSON_SCHEMA_EXPRESSIVENESS_GAP" in result["root_causes"]
    assert "PROMPT_CONTRACT_GAP" in result["root_causes"]
    assert "MODEL_INSTRUCTION_NONCOMPLIANCE" not in result["root_causes"]


def test_visible_length_and_enum_violations_are_model_noncompliance() -> None:
    document = candidate_document("WEEKLY_STRUCTURE_QUANTILE")
    document["economic_rationale_draft"] = "研" * 801
    document["required_features"][0] = "PREVIOUS_COMPLETE_WEEK_RANGE"

    result = diagnose_document(document, Mechanism.WEEKLY_STRUCTURE_QUANTILE)

    assert {"RATIONALE_MAX_LENGTH", "FEATURE_ENUM_MEMBERSHIP"}.issubset(rule_ids(result))
    visible = [
        item for item in result["diagnostic_violations"]
        if item["rule_id"] in {"RATIONALE_MAX_LENGTH", "FEATURE_ENUM_MEMBERSHIP"}
    ]
    assert all(item["transmitted_json_schema"] is True for item in visible)
    assert "MODEL_INSTRUCTION_NONCOMPLIANCE" in result["root_causes"]


def test_cross_mechanism_parameter_and_search_product_are_detected() -> None:
    document = deepcopy(candidate_document("MOVING_AVERAGE_RESUMPTION"))
    document["parameter_slots"].append({
        "parameter_id": "ATR_LOOKBACK_DAYS", "value_type": "INTEGER",
        "minimum": "10", "maximum": "30", "search_points_maximum": 7,
    })
    for slot in document["parameter_slots"]:
        slot["search_points_maximum"] = 7

    result = diagnose_document(document, Mechanism.MOVING_AVERAGE_RESUMPTION)

    assert {"MECHANISM_PARAMETER_MAPPING", "SEARCH_EVALUATION_PRODUCT"}.issubset(rule_ids(result))
    assert result["local_validator_defect_detected"] is False


def test_diagnostic_modules_remain_small_and_single_purpose() -> None:
    root = Path(__file__).resolve().parents[1] / "src/shaiwei/research/trend_swing"
    assert len((root / "v5_contract_diagnostic.py").read_text().splitlines()) <= 400
    assert len((root / "v5_contract_diagnostic_audit.py").read_text().splitlines()) <= 160
