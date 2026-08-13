from copy import deepcopy

import pytest
from pydantic import ValidationError

from shaiwei.research.trend_swing.v5_models import (
    COMMON_FEATURES,
    MECHANISM_FEATURES,
    Mechanism,
    MechanismCandidate,
)


DESIGNS = {
    "VOLATILITY_ADAPTIVE_PULLBACK": (
        "PREVIOUS_COMPLETE_WEEK_VWAP",
        "ATR_MULTIPLE",
        [("ATR_LOOKBACK_DAYS", "INTEGER", "10", "30", 3),
         ("PULLBACK_ATR_MULTIPLE", "DECIMAL", "0.25", "2.00", 4)],
    ),
    "WEEKLY_STRUCTURE_QUANTILE": (
        "PREVIOUS_COMPLETE_WEEK_RANGE",
        "WEEKLY_RANGE_QUANTILE",
        [("WEEKLY_RANGE_QUANTILE", "DECIMAL", "0.15", "0.65", 4)],
    ),
    "BREAKOUT_RETEST": (
        "PRIOR_WEEKLY_BREAKOUT_LEVEL",
        "BREAKOUT_RETEST_DISTANCE",
        [("BREAKOUT_LOOKBACK_WEEKS", "INTEGER", "4", "26", 4),
         ("RETEST_TOLERANCE_ATR", "DECIMAL", "0.10", "1.50", 4)],
    ),
    "MOVING_AVERAGE_RESUMPTION": (
        "DAILY_MEDIUM_MOVING_AVERAGE",
        "ATR_DISTANCE_TO_MOVING_AVERAGE",
        [("MOVING_AVERAGE_LOOKBACK_DAYS", "INTEGER", "10", "60", 4),
         ("MOVING_AVERAGE_TOLERANCE_ATR", "DECIMAL", "0.10", "1.50", 4)],
    ),
    "CONTRACTION_EXPANSION": (
        "COMPLETE_WEEK_CONTRACTION_RANGE",
        "RANGE_AND_VOLUME_CONTRACTION",
        [("CONTRACTION_LOOKBACK_WEEKS", "INTEGER", "3", "12", 3),
         ("RANGE_CONTRACTION_QUANTILE", "DECIMAL", "0.10", "0.50", 3),
         ("VOLUME_EXPANSION_RATIO", "DECIMAL", "1.00", "2.50", 3)],
    ),
    "RELATIVE_STRENGTH_PULLBACK": (
        "STOCK_SECTOR_RELATIVE_STRENGTH_PEAK",
        "RELATIVE_STRENGTH_DRAWDOWN",
        [("RELATIVE_STRENGTH_LOOKBACK_DAYS", "INTEGER", "20", "120", 4),
         ("RELATIVE_STRENGTH_DRAWDOWN_QUANTILE", "DECIMAL", "0.10", "0.60", 4)],
    ),
}


def candidate_document(mechanism: str = "VOLATILITY_ADAPTIVE_PULLBACK") -> dict[str, object]:
    reference, measure, slots = DESIGNS[mechanism]
    enum = Mechanism(mechanism)
    features = sorted(item.value for item in COMMON_FEATURES | MECHANISM_FEATURES[enum])
    return {
        "schema_version": "ts-v5-mechanism-candidate-v1",
        "primary_mechanism": mechanism,
        "hypothesis": "在既有月周右侧和强板块条件下，自适应结构位置可能比固定百分比更稳定。",
        "economic_rationale_draft": "该机制只用于发现期证伪，并将趋势方向、入场位置和风险约束分开。",
        "change_summary": "替换固定百分比回撤位置，其他产品约束保持不变。",
        "entry_design": {
            "reference_frame": reference,
            "pullback_measure": measure,
            "recovery_confirmation": "CLOSE_RECLAIMS_REFERENCE",
            "cancellation_rules": ["STRUCTURE_LOW_BROKEN", "MARKET_OR_SECTOR_GATE_LOST"],
        },
        "parameter_slots": [
            {
                "parameter_id": parameter_id,
                "value_type": value_type,
                "minimum": minimum,
                "maximum": maximum,
                "search_points_maximum": points,
            }
            for parameter_id, value_type, minimum, maximum, points in slots
        ],
        "required_features": features,
        "falsification_conditions": [
            "发现期事件仍集中于单一年度或不足以形成跨年评价。",
            "扣除交易成本后方向不稳定且参数邻域无法保持一致。",
        ],
        "lineage": {"mode": "INDEPENDENT", "parent_candidate_fingerprints": []},
    }


@pytest.mark.parametrize("mechanism", [item.value for item in Mechanism])
def test_all_six_mechanism_archetypes_are_executable_contracts(mechanism: str) -> None:
    candidate = MechanismCandidate.model_validate(candidate_document(mechanism))

    assert candidate.primary_mechanism == mechanism
    assert len(candidate.fingerprint()) == 64
    assert len(candidate.semantic_signature()) == 64


def test_contract_rejects_cross_mechanism_parameters_and_unsafe_bounds() -> None:
    cross = candidate_document()
    cross["parameter_slots"].append(
        {
            "parameter_id": "BREAKOUT_LOOKBACK_WEEKS",
            "value_type": "INTEGER",
            "minimum": "4",
            "maximum": "26",
            "search_points_maximum": 3,
        }
    )
    with pytest.raises(ValidationError, match="another mechanism"):
        MechanismCandidate.model_validate(cross)

    unsafe = candidate_document()
    unsafe["parameter_slots"][1]["maximum"] = "9.00"
    with pytest.raises(ValidationError, match="safe range"):
        MechanismCandidate.model_validate(unsafe)


def test_contract_rejects_missing_product_feature_and_search_explosion() -> None:
    missing = candidate_document()
    missing["required_features"].remove("PIT_MARKET_CAP")
    with pytest.raises(ValidationError, match="required product"):
        MechanismCandidate.model_validate(missing)

    explosion = candidate_document("CONTRACTION_EXPANSION")
    for slot in explosion["parameter_slots"]:
        slot["search_points_maximum"] = 7
    with pytest.raises(ValidationError, match="196"):
        MechanismCandidate.model_validate(explosion)


def test_contract_rejects_code_secret_authority_claims_and_extra_fields() -> None:
    secret_fixture = "sk" + "-1234567890"
    for payload in ("python 生成信号并运行", f"密钥 {secret_fixture}", "该候选已经回测通过适合实盘"):
        document = candidate_document()
        document["change_summary"] = payload
        with pytest.raises(ValidationError):
            MechanismCandidate.model_validate(document)

    extra = candidate_document()
    extra["predicted_return"] = 0.2
    with pytest.raises(ValidationError, match="Extra inputs"):
        MechanismCandidate.model_validate(extra)


def test_semantic_signature_detects_duplicate_logic_despite_prose_change() -> None:
    first = MechanismCandidate.model_validate(candidate_document())
    changed = deepcopy(candidate_document())
    changed["hypothesis"] = "趋势成立以后，以波动调整后的历史参考位寻找恢复信号，可能提高事件稳健性。"
    second = MechanismCandidate.model_validate(changed)

    assert first.fingerprint() != second.fingerprint()
    assert first.semantic_signature() == second.semantic_signature()
