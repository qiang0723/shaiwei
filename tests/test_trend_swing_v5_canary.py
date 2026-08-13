from decimal import Decimal
from pathlib import Path

from shaiwei.research.trend_swing.v5_canary import (
    MECHANISMS,
    SCOPE_SHA256,
    V5CanaryScope,
    preflight,
)


def test_canary_scope_is_frozen_but_not_execution_authority() -> None:
    scope = V5CanaryScope.load()

    assert scope.sha256 == SCOPE_SHA256
    assert scope.completed_responses == 4
    assert scope.hard_ceiling_usd == Decimal("0.10")
    assert scope.document["execution_authorized"] is False
    assert scope.document["user_approval_received"] is False
    assert scope.document["deepseek_api_called"] is False
    assert scope.document["attempt_contract"]["mechanism_order"] == list(MECHANISMS)


def test_canary_preflight_builds_exact_v2_bundle_without_live_authority() -> None:
    report = preflight()

    assert report["gate"] == "GO_PREEXECUTION_ONLY"
    assert report["request_count"] == 4
    assert len(report["request_hashes"]) == 4
    assert len(set(report["request_hashes"])) == 4
    assert len(report["request_bundle_sha256"]) == 64
    assert report["planned_worst_case_usd"] == "0.034104"
    assert report["batch_hard_ceiling_usd"] == "0.10"
    assert all(report["checks"].values())
    assert report["provider_calls"] == 0
    assert report["secret_read"] is False
    assert report["market_or_effect_read"] is False
    assert report["parameter_search_or_backtest"] is False
    assert report["paper_web_or_production"] is False


def test_canary_module_stays_well_below_architecture_limit() -> None:
    root = Path(__file__).resolve().parents[1]
    lines = (root / "src/shaiwei/research/trend_swing/v5_canary.py").read_text().splitlines()

    assert len(lines) <= 250
