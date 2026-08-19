"""Adversarial synthetic fixtures for the RF-0C preflight machinery."""

from __future__ import annotations

from typing import Any

from shaiwei.research.rf_0c.contract import RFCError
from shaiwei.research.rf_0c.fields import classify_member_day


def _row(**overrides: Any) -> dict[str, Any]:
    base = {
        "ts_code": "600000.SH",
        "trade_date": "20240103",
        "list_date": "20000101",
        "bar_record_count": 1,
        "bar_variant_count": 1,
        "open": 10.0,
        "high": 10.5,
        "low": 9.8,
        "close": 10.2,
        "pre_close": 10.1,
        "adj_factor": 1.0,
        "prior_adj_factor": 1.0,
        "prior_bar_close": 10.1,
        "primary_suspended": False,
        "independent_status": "1",
    }
    base.update(overrides)
    return base


def fixture() -> dict[str, Any]:
    no_bar = dict(
        bar_record_count=0, bar_variant_count=0, open=None, high=None, low=None,
        close=None, pre_close=None, adj_factor=None, prior_adj_factor=None,
        prior_bar_close=None,
    )
    cases = {
        "suspension_missing_bar_primary": (
            _row(primary_suspended=True, **no_bar), {"NO_BAR_SUSPENDED"},
        ),
        "suspension_confirmed_only_by_independent_baostock": (
            _row(independent_status="0", **no_bar), {"NO_BAR_SUSPENDED"},
        ),
        "no_bar_unexplained_remains_when_neither_layer_confirms": (
            _row(**no_bar), {"NO_BAR_UNEXPLAINED"},
        ),
        "corporate_action_factor_change": (_row(adj_factor=1.5), {"CORPORATE_ACTION_DAY"}),
        "first_listing_day_without_prior_close": (
            _row(list_date="20240103", pre_close=None, prior_bar_close=None),
            {"FIRST_LISTING_DAY", "PRE_CLOSE_MISSING_OR_NONPOSITIVE"},
        ),
        "missing_open_with_present_close": (_row(open=None), {"OPEN_MISSING_OR_NONPOSITIVE"}),
        "cross_non_trading_day_prev_close_reference": (_row(pre_close=None), set()),
        "bse_row_rejection": (_row(ts_code="430001.BJ"), {"BSE_ROW"}),
        "one_word_limit_open_proxy": (
            _row(open=11.11, high=11.11, low=11.11, close=11.11, pre_close=10.1),
            {"ONE_WORD_LIMIT_OPEN_PROXY"},
        ),
        "clean_day": (_row(), set()),
    }
    for name, (row, expected) in cases.items():
        observed = set(classify_member_day(row))
        if observed != expected:
            raise RFCError(f"RF-0C fixture case differs: {name}: {observed} != {expected}")
    return {"fixture_pass": True, "adversarial_cases": len(cases)}
