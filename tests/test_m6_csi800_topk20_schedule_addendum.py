from __future__ import annotations

import hashlib
from pathlib import Path

import yaml

from shaiwei.config import PROJECT_ROOT


ADDENDUM = PROJECT_ROOT / "config/m6_csi800_topk20_conversion_schedule_addendum_v1.yaml"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load() -> dict:
    document = yaml.safe_load(ADDENDUM.read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    return document


def test_addendum_is_result_blind_and_binds_all_predecessors() -> None:
    document = _load()
    assert document["stage"] == "RESULT_BLIND_BEFORE_REAL_TOPK20_EFFECT"
    for key in (
        "result_protocol",
        "engineering_protocol",
        "engineering_manifest",
        "real_release_protocol",
    ):
        row = document["predecessors"][key]
        assert _sha(PROJECT_ROOT / row["path"]) == row["sha256"]
    assert document["finding"]["found_before_real_effect_read"] is True
    assert document["finding"]["real_m6_effect_semantics_read"] is False
    assert document["finding"]["qlib_read"] is False
    assert document["finding"]["real_top20_backtest_count"] == 0


def test_addendum_changes_only_schedule_diagnostic_shape() -> None:
    correction = _load()["correction"]
    assert correction["decision_or_gate_change"] is False
    assert correction["hypothesis_or_attempt_change"] is False
    assert correction["portfolio_parameter_change"] is False
    assert correction["model_or_prediction_change"] is False
    assert correction["required_schedule_shape"] == (
        "topk_then_window_then_arm_then_rebalance_date_then_security_list"
    )
    assert correction["schedule_dates"] == {
        "source": "exact_prediction_trade_dates",
        "first_step": 0,
        "cadence_trade_days": 10,
        "must_match_across_topk_and_arms_within_window": True,
    }
    overlap = correction["scheduled_top20_overlap_vs_clean_control"]
    assert overlap["aggregation"] == (
        "unweighted_arithmetic_mean_across_all_rebalance_dates_in_W1_through_W6"
    )
    assert overlap["role"] == "diagnostic_required_decomposition_not_gate"


def test_addendum_requires_dual_implementation_and_exact_release_binding() -> None:
    requirements = _load()["implementation_requirements"]
    assert requirements["primary_metrics_and_independent_audit_both_updated"] is True
    assert requirements["synthetic_fixture_must_have_multiple_rebalance_dates_per_window"] is True
    assert requirements["legacy_single_list_schedule_must_fail_closed"] is True
    assert requirements["exact_release_scope_must_bind_this_addendum_sha256"] is True
    assert requirements["no_real_effect_or_qlib_read_before_exact_scope_approval"] is True
    authority = _load()["authority"]
    assert authority["sealed_effect_semantic_read_authorized"] is False
    assert authority["qlib_read_authorized"] is False
    assert authority["real_top20_backtest_authorized"] is False
    assert authority["production_authorization"] == "none"

