from copy import deepcopy
from decimal import Decimal
import json

import pytest

from shaiwei.research.provider_contract import D1ControlError
from shaiwei.research.trend_swing.v5_contract import canonical_json
from shaiwei.research.trend_swing.v5_r3g_acceptance import build_evidence
from shaiwei.research.trend_swing.v5_r3g_contract import (
    R3GScope,
    evidence_tree_sha256,
    registered_candidates,
    sanitized_registry,
)
from shaiwei.research.trend_swing.v5_r3g_fixtures import (
    adversarial_evidence,
    normal_path_evidence,
)
from shaiwei.research.trend_swing.v5_r3g_state import DailyInput


@pytest.fixture(scope="module")
def scope() -> R3GScope:
    return R3GScope.load()


@pytest.fixture(scope="module")
def candidates(scope: R3GScope):
    return registered_candidates(scope)


def test_frozen_scope_addenda_and_r3f_evidence_are_bound(scope: R3GScope):
    assert scope.document["production_authorization"] == "none"
    assert scope.reference_addendum["reason"]["candidate_removed_repaired_or_recompiled"] is False
    assert scope.confirmation_addendum["reason"]["parameter_or_threshold_changed"] is False
    assert evidence_tree_sha256() == scope.document["frozen_inputs"]["r3f_evidence_tree_sha256"]


def test_six_candidates_recompile_with_exact_effective_grids(candidates):
    assert [item.candidate.primary_mechanism.value for item in candidates] == [
        "VOLATILITY_ADAPTIVE_PULLBACK",
        "WEEKLY_STRUCTURE_QUANTILE",
        "BREAKOUT_RETEST",
        "MOVING_AVERAGE_RESUMPTION",
        "CONTRACTION_EXPANSION",
        "RELATIVE_STRENGTH_PULLBACK",
    ]
    assert [len(item.grid) for item in candidates] == [81, 75, 81, 81, 32, 81]
    assert sum(len(item.grid) for item in candidates) == 431


def test_registry_is_deterministic_and_contains_no_llm_free_text(scope, candidates):
    first = sanitized_registry(scope, candidates)
    second = sanitized_registry(scope, registered_candidates(scope))
    assert canonical_json(first) == canonical_json(second)
    serialized = canonical_json(first)
    assert all(term not in serialized for term in (
        "hypothesis", "economic_rationale_draft", "change_summary",
        "falsification_conditions", "reasoning_content",
    ))


def test_all_six_normal_paths_execute(candidates):
    evidence = normal_path_evidence(candidates)
    assert len(evidence) == 6
    assert {row["terminal_status"] for row in evidence} == {"EXECUTED"}


def test_all_adversarial_paths_hold(candidates):
    evidence = adversarial_evidence(candidates)
    assert len(evidence) == 15
    assert all(evidence.values())


def test_daily_input_rejects_future_result_field():
    document = {
        "sequence": 1,
        "lagged_feature_sequence": 0,
        "low": Decimal("1"),
        "close": Decimal("1"),
        "prior_valid_high": Decimal("1"),
        "amount": Decimal("1"),
        "prior_20d_amount_median": Decimal("1"),
        "reference": Decimal("1"),
        "atr": Decimal("1"),
        "threshold": Decimal("0.1"),
        "relative_strength": Decimal("1"),
        "structure_low": Decimal("0.5"),
        "base_structure_gate": True,
        "market_sector_gate": True,
        "liquidity_gate": True,
        "security_eligible": True,
        "breakout_prerequisite": True,
        "contraction_prerequisite": True,
        "first_plan_week_bar": True,
        "return_after_entry": Decimal("1"),
    }
    with pytest.raises(D1ControlError):
        DailyInput.from_mapping(document)


def test_report_gate_is_result_blind_density_scope_proposal_only(scope):
    registry, report = build_evidence(scope)
    assert report["gate"] == "GO_R3G_DENSITY_SCOPE_PROPOSAL_ONLY"
    assert report["strategy_effect_attempt_count"] == 0
    assert report["candidate_effectiveness"] == "NOT_EVALUATED"
    assert report["production_authorization"] == "none"
    assert report["registry_canonical_sha256"]
    assert json.loads(json.dumps(registry)) == registry


def test_scope_drift_fails_closed(scope, tmp_path):
    document = deepcopy(scope.document)
    document["authority"]["read_post_entry_return_or_effect"] = True
    path = tmp_path / "scope.yaml"
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(D1ControlError):
        R3GScope.load(path)
