"""Research-only paper policy for the M6 delisting-price risk exit overlay."""

from __future__ import annotations

from typing import Literal

from shaiwei.config import PaperPortfolio


class PaperDelistingRiskPortfolio(PaperPortfolio):
    account_id: Literal["m6_head30_delisting_risk"]
    execution_policy_version: Literal["paper-v2-delisting-risk-exit"]
    risk_trigger_price_cny: Literal[1.0]
    risk_trigger_consecutive_closes: Literal[10]
    risk_exit_latched: Literal[True]
    risk_cash_reserve_authorized: Literal[True]
