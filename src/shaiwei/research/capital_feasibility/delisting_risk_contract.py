"""Strict loader for the M6-5C-A delisting-risk method contract."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.production_conversion.contract import ProtocolError

from .delisting_risk import RiskPolicy


CONFIG_PATH = PROJECT_ROOT / "config/m6_csi800_production_head30_delisting_risk_method_v1.yaml"


def load_method(path: Path = CONFIG_PATH) -> tuple[dict[str, Any], RiskPolicy]:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ProtocolError("M6-5C-A method contract is not a mapping")
    if (
        document.get("schema_version")
        != "m6-csi800-production-head30-delisting-risk-method-v1"
        or document.get("stage") != "EFFECT_SEALED_METHOD_ENGINEERING_ONLY"
    ):
        raise ProtocolError("M6-5C-A method identity differs")
    predecessor = document.get("known_predecessor", {})
    if predecessor != {
        "status": "BLOCKED_BY_UNMODELED_DELISTING",
        "instrument": "002505.SZ",
        "last_trade_date": "20240702",
        "delist_date": "20240830",
        "original_family_attempt_count": 2,
        "original_scopes_reusable": False,
    }:
        raise ProtocolError("M6-5C-A predecessor differs")
    risk = document.get("risk_policy", {})
    fixed = {
        "policy_version": "paper-v2-delisting-risk-exit",
        "only_new_variable": "delisting_price_risk_exit_overlay_v1",
        "trigger_comparison": "strict_less_than",
        "calculate_as_of_signal_close": True,
        "first_execution_opportunity": "next_official_trade_day_open",
        "held_exit_latched_until_filled": True,
        "blocked_buy_replacement_authorized": False,
        "remaining_target_weight_redistribution_authorized": False,
        "unexecuted_exit_may_create_cash": False,
        "delisting_cash_settlement_authorized": False,
    }
    if any(risk.get(key) != value for key, value in fixed.items()):
        raise ProtocolError("M6-5C-A risk policy differs")
    if (
        Decimal(str(risk.get("trigger_price_cny"))) != Decimal("1.0")
        or int(risk.get("trigger_consecutive_trading_closes", 0)) != 10
        or Decimal(str(risk.get("original_target_weight")))
        != Decimal("0.03333333333333333")
    ):
        raise ProtocolError("M6-5C-A risk threshold differs")
    attempt = document.get("attempt_policy", {})
    if attempt != {
        "family": "m6_head30_capital_feasibility_delisting_risk_v1",
        "known_failure_informed_method": True,
        "historical_authority": "POST_HOC_METHOD_RECOVERY_DIAGNOSTIC",
        "a1_5a_claim_required_before_any_future_real_read": True,
        "attempts_authorized_in_m6_5c_a": 0,
    }:
        raise ProtocolError("M6-5C-A attempt policy differs")
    authority = document.get("authority", {})
    if authority.get("synthetic_method_fixture_authorized") is not True:
        raise ProtocolError("M6-5C-A synthetic authority is absent")
    forbidden = [key for key in authority if key != "synthetic_method_fixture_authorized"]
    if any(
        authority[key] not in (False, "none")
        for key in forbidden
    ) or authority.get("production_authorization") != "none":
        raise ProtocolError("M6-5C-A authority was broadened")
    policy = RiskPolicy(
        trigger_price=Decimal(str(risk.get("trigger_price_cny"))),
        trigger_sessions=int(risk.get("trigger_consecutive_trading_closes", 0)),
        target_weight=Decimal(str(risk.get("original_target_weight"))),
    )
    policy.validate()
    return document, policy
