from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
import yaml

from shaiwei.backtest.full_target import (
    BiweeklyRankHeadEqualWeightStrategy,
    FullTargetStrategyError,
)
from shaiwei.provenance import CONTROLLED_FILES, RELEASE_MANIFEST_SCHEMA
from shaiwei.research.production_conversion.price_recovery_validation import (
    validate_price_recovery_protocol,
)
from shaiwei.research.production_conversion.contract import ProtocolError
from shaiwei.research.production_conversion.real_contract import (
    PRICE_RECOVERY_PROTOCOL,
    ReleaseProtocol,
    mapping,
)
from shaiwei.research.production_conversion.real_release import build_release_document


ROOT = Path(__file__).parents[1]
COMPOSE = ROOT / "compose.m6-production-head30-price-recovery.yaml"


class _Position:
    def __init__(self, price):
        self.price = price

    def get_stock_price(self, _code):
        return self.price


class _Exchange:
    def __init__(self, price):
        self.price = price

    def get_deal_price(self, **_kwargs):
        return self.price


def _strategy(*, deal_price, position_price) -> BiweeklyRankHeadEqualWeightStrategy:
    strategy = BiweeklyRankHeadEqualWeightStrategy(
        topk=1,
        rebalance_days=10,
        risk_degree=1.0,
        signal=pd.Series([1.0], index=["SH1"]),
    )
    strategy.common_infra = {
        "trade_account": SimpleNamespace(
            current_position=_Position(position_price)
        )
    }
    strategy._trade_exchange = _Exchange(deal_price)
    return strategy


@pytest.mark.parametrize("value", [None, "bad", np.nan, np.inf, 0.0, -1.0, True])
def test_missing_or_invalid_deal_price_uses_existing_position_fallback(value) -> None:
    strategy = _strategy(deal_price=value, position_price=10.0)

    assert strategy._valuation_price("SH1", "2091-01-03", "2091-01-03") == 10.0


def test_valid_deal_price_remains_primary() -> None:
    strategy = _strategy(deal_price=11.0, position_price=10.0)

    assert strategy._valuation_price("SH1", "2091-01-03", "2091-01-03") == 11.0


@pytest.mark.parametrize("value", [None, "bad", np.nan, np.inf, 0.0, -1.0, False])
def test_invalid_deal_and_position_prices_fail_closed(value) -> None:
    strategy = _strategy(deal_price=None, position_price=value)

    with pytest.raises(FullTargetStrategyError, match="SH1"):
        strategy._valuation_price("SH1", "2091-01-03", "2091-01-03")


def test_price_recovery_protocol_binds_failure_attempt_and_new_outputs() -> None:
    protocol = ReleaseProtocol.load(PRICE_RECOVERY_PROTOCOL)
    document = protocol.document

    assert protocol.is_recovery is True
    assert protocol.is_price_recovery is True
    assert protocol.output_roots == {
        "effect_root": "data/research/m6_csi800_production_head30_v1/effect-r2",
        "audit_root": "data/research/m6_csi800_production_head30_v1/effect-r2-audit",
        "experiment_ledger_write_authorized": False,
    }
    assert document["execution_counting"]["r1_portfolio_attempts_consumed"] == 1
    assert document["execution_counting"]["total_family_attempts_after_new_effect_read"] == 2
    assert document["recovery_change"]["strategy_formula_changed"] is False


def test_price_recovery_protocol_rejects_behavior_or_attempt_drift() -> None:
    protocol = ReleaseProtocol.load(PRICE_RECOVERY_PROTOCOL)
    cases = []
    behavior = deepcopy(protocol.document)
    behavior["recovery_change"]["held_position_valuation"]["fallback"] = "prior_close"
    cases.append(behavior)
    attempt = deepcopy(protocol.document)
    attempt["execution_counting"]["r1_portfolio_attempts_consumed"] = 0
    cases.append(attempt)
    outputs = deepcopy(protocol.document)
    outputs["artifact_contract"]["ignored_effect_root"] = (
        "data/research/m6_csi800_production_head30_v1/effect"
    )
    cases.append(outputs)

    for document in cases:
        with pytest.raises(ProtocolError):
            validate_price_recovery_protocol(document, ROOT)


def test_price_recovery_compose_is_isolated_and_controlled() -> None:
    assert COMPOSE.name in CONTROLLED_FILES
    services = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))["services"]
    runner = services["m6-production-head30-price-recovery-runner"]
    auditor = services["m6-production-head30-price-recovery-auditor"]
    assert runner["network_mode"] == "none"
    assert runner["read_only"] is True
    assert runner["tmpfs"] == ["/tmp:rw,noexec,nosuid,size=4g,mode=1777"]
    assert auditor["tmpfs"] == ["/tmp:rw,noexec,nosuid,size=1g,mode=1777"]
    text = COMPOSE.read_text(encoding="utf-8")
    assert ".env" not in text
    assert "effect-r2" in text
    assert "approval-r2.json" in text
    assert "/var/run/docker.sock" not in text
    assert "ledger" not in text


def test_release_document_uses_price_recovery_profile(tmp_path: Path) -> None:
    protocol = ReleaseProtocol.load(PRICE_RECOVERY_PROTOCOL)
    snapshot = "a" * 64
    manifest = {
        "schema_version": RELEASE_MANIFEST_SCHEMA,
        "code_snapshot_sha256": snapshot,
        "file_count": 1,
        "files": [{"path": "x", "sha256": "b" * 64}],
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    qlib = mapping(
        ROOT / "config/m6_csi800_model_attribution_release_scope_v1.json"
    )["scope"]["inputs"]
    inputs = {
        "qlib": qlib,
        "sealed_m6_effect": {},
        "sealed_m6_audit": {},
    }
    commit = "1" * 40

    release = build_release_document(
        protocol=protocol,
        created_at="2026-08-20T00:00:00+00:00",
        implementation_git_commit=commit,
        origin_main_commit=commit,
        code_snapshot=snapshot,
        image_id="sha256:" + "2" * 64,
        image_platform="linux/arm64",
        image_git_commit=commit,
        image_release_manifest_path=manifest_path,
        inputs=inputs,
    )

    scope = release["scope"]
    assert scope["outputs"] == protocol.output_roots
    assert scope["image"]["reference"] == "shaiwei:m6-production-head30-price-recovery-v1"
    assert scope["container"]["runner"]["service"] == (
        "m6-production-head30-price-recovery-runner"
    )
    assert scope["execution"]["approval_action"] == (
        "M6_PRODUCTION_HEAD30_G0_EFFECT_PRICE_RECOVERY_ONCE_WITH_REPLAY_"
        "AND_INDEPENDENT_AUDIT"
    )
