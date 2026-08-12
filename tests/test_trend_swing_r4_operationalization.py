from hashlib import sha256
from pathlib import Path

import yaml


ROOT = Path(__file__).parents[1]
PROTOCOL = ROOT / "config/ts_v3_pullback_state_preflight_v1.yaml"
ADDENDUM = ROOT / "config/ts_v3_pullback_state_operationalization_v1.yaml"


def _addendum() -> dict:
    return yaml.safe_load(ADDENDUM.read_text(encoding="utf-8"))


def test_r4_addendum_binds_frozen_protocol_without_broadening_authority() -> None:
    addendum = _addendum()

    assert addendum["predecessor"]["protocol_sha256"] == sha256(
        PROTOCOL.read_bytes()
    ).hexdigest()
    assert addendum["predecessor"]["immutable_and_not_rewritten"] is True
    assert all(value is False for value in addendum["authority"].values())


def test_r4_addendum_freezes_pit_and_immediate_next_open_semantics() -> None:
    addendum = _addendum()
    sequence = addendum["sequence_semantics"]
    next_open = addendum["next_open_semantics"]

    assert sequence["touch_day_requires_current_PIT_member_non_ST_unique_industry_and_all_daily_gates"] is True
    assert sequence["invalidation_on_or_before_confirmation_is_absorbing"] is True
    assert sequence["later_confirmations_in_same_security_plan_week"] == "ignored"
    assert next_open["date"] == "immediately_next_SSE_official_open_day_after_confirmation"
    assert next_open["later_security_bar_substitution"] == "forbidden"
    assert next_open["next_day_current_PIT_member_required"] is True
    assert next_open["confirmation_and_next_day_adjustment_factor_exact_match_required"] is True


def test_r4_addendum_keeps_benchmark_and_artifacts_fail_closed() -> None:
    addendum = _addendum()

    assert addendum["benchmark_discovery_semantics"]["absent_status"] == (
        "BLOCKED_BENCHMARK_DATA"
    )
    assert addendum["benchmark_discovery_semantics"][
        "content_inference_from_000906_price_series"
    ] == "forbidden"
    assert addendum["machine_artifacts"]["report_and_audit"]["aggregate_only"] is True
    assert addendum["attempt_control"]["strategy_effect_attempt_count"] == 0
