from copy import deepcopy

import pandas as pd
import pytest

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.trend_swing.contract import (
    TrendSwingError,
    TrendSwingProtocol,
    _validate_protocol,
)
from shaiwei.research.trend_swing.features import (
    completed_period_on,
    listing_segment,
    monthly_aggregates,
    sector_daily_return,
    structural_gate_flags,
    weekly_aggregates,
)


PROTOCOL = PROJECT_ROOT / "config/ts_v3_data_gate_v1.yaml"


def _bars() -> pd.DataFrame:
    dates = [
        "20260128", "20260129", "20260130",
        "20260202", "20260203", "20260204", "20260205", "20260206",
        "20260209", "20260210", "20260211", "20260212", "20260213",
        "20260216",
    ]
    return pd.DataFrame(
        {
            "ts_code": ["600001.SH"] * len(dates),
            "trade_date": dates,
            "open": range(10, 10 + len(dates)),
            "high": range(11, 11 + len(dates)),
            "low": range(9, 9 + len(dates)),
            "close": range(10, 10 + len(dates)),
            "amount": [1_000_000_000.0] * len(dates),
        }
    )


def test_protocol_rejects_effect_or_network_authority():
    protocol = TrendSwingProtocol.load(PROTOCOL)
    assert protocol.document["alpha158"]["role"] == "ranking_only"
    assert protocol.document["attempt_and_change_control"]["data_profile_attempt_count"] == 1

    tampered = deepcopy(protocol.document)
    tampered["authorization"]["strategy_backtest"] = True
    with pytest.raises(TrendSwingError, match="authority"):
        _validate_protocol(tampered)


def test_listing_segment_is_explicit_and_bse_fails_closed():
    assert listing_segment("600001.SH") == "main"
    assert listing_segment("300001.SZ") == "chinext"
    assert listing_segment("688001.SH") == "star"
    with pytest.raises(TrendSwingError, match=".BJ"):
        listing_segment("830001.BJ")


def test_week_and_month_use_only_completed_periods():
    bars = _bars()
    weekly = weekly_aggregates(bars)
    latest = completed_period_on("20260212", weekly, "week_end")
    assert latest["week_end"] == pd.Timestamp("2026-02-06")
    assert latest["weekly_amount"] == 5_000_000_000.0

    monthly = monthly_aggregates(bars)
    latest_month = completed_period_on("20260216", monthly, "month_end")
    assert latest_month["month_end"] == pd.Timestamp("2026-01-31")


def test_duplicate_or_bse_bars_fail_closed():
    bars = _bars()
    with pytest.raises(TrendSwingError, match="duplicate"):
        weekly_aggregates(pd.concat([bars, bars.iloc[[0]]], ignore_index=True))
    bars.loc[0, "ts_code"] = "830001.BJ"
    with pytest.raises(TrendSwingError, match=".BJ"):
        monthly_aggregates(bars)


def test_structural_gates_preserve_strict_monthly_and_nondecreasing_weekly_rules():
    frame = pd.DataFrame(
        {
            "total_mv_rmb": [20_000_000_000, 19_999_999_999],
            "weekly_amount_rmb": [5_000_000_000, 5_000_000_000],
            "monthly_high": [12.0, 12.0],
            "previous_monthly_high": [11.0, 11.0],
            "previous_2_monthly_high": [10.0, 10.0],
            "weekly_low": [10.0, 10.0],
            "previous_weekly_low": [10.0, 10.0],
            "previous_2_weekly_low": [9.0, 9.0],
            "weekly_close": [11.0, 11.0],
            "weekly_high": [12.0, 12.0],
        }
    )
    flags = structural_gate_flags(frame)
    assert flags.loc[0, "all"]
    assert not flags.loc[1, "all"]


def test_sector_basket_requires_five_unique_pit_members():
    frame = pd.DataFrame(
        {
            "trade_date": ["20260105"] * 6,
            "industry": ["I1"] * 4 + ["I2"] * 2,
            "ts_code": [f"60000{i}.SH" for i in range(6)],
            "daily_return": [0.01] * 6,
        }
    )
    result = sector_daily_return(frame)
    assert not result["eligible"].any()
    extra = frame.iloc[[0]].assign(ts_code="600099.SH", industry="I1")
    result = sector_daily_return(pd.concat([frame, extra], ignore_index=True))
    assert result.loc[result["industry"].eq("I1"), "eligible"].item()
