from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.p2_star50_engineering.contract import (  # noqa: E402
    GateFailure,
    verify_monthly_crosscheck,
    verify_official_daily_membership,
)


def _protocol(months: list[str]) -> dict:
    return {
        "identity": {"benchmark_source_code": "000688.SH"},
        "input_gate": {
            "expected_months": months,
            "expected_month_count": len(months),
            "snapshot_trade_dates_per_month_exact": 1,
            "snapshot_rows_per_month_exact": 50,
            "snapshot_unique_constituents_per_month_exact": 50,
            "duplicate_snapshot_key_count_maximum": 0,
            "bse_row_count_maximum": 0,
        },
        "dataset_contract": {
            "strategy_usable_start": "2020-07-23",
            "official_member_count_per_trade_date": 50,
            "official_membership_duplicate_key_count_maximum": 0,
        },
    }


def _frames() -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    months = ["2020-07", "2020-08", "2020-09"]
    dates = ["20200723", "20200803", "20200901"]
    codes = [f"688{number:03d}.SH" for number in range(50)]
    weight_rows = [
        {"index_code": "000688.SH", "con_code": code, "trade_date": date} for date in dates for code in codes
    ]
    official_rows = [{"trade_date": date, "code": code} for date in dates for code in codes]
    return pd.DataFrame(weight_rows), pd.DataFrame(official_rows), _protocol(months)


def test_monthly_crosscheck_passes_exact_domain() -> None:
    weights, official, protocol = _frames()
    report = verify_monthly_crosscheck(weights, official, protocol)
    assert report["exact_set_match_month_count"] == 3
    assert report["months_with_exactly_one_snapshot"] == 3


def test_missing_month_plus_duplicate_month_cannot_hide_behind_same_snapshot_total() -> None:
    weights, official, protocol = _frames()
    missing = weights.loc[~weights["trade_date"].eq("20200803")]
    duplicate_month = weights.loc[weights["trade_date"].eq("20200901")].assign(trade_date="20200915")
    corrupted = pd.concat([missing, duplicate_month], ignore_index=True)

    assert corrupted["trade_date"].nunique() == weights["trade_date"].nunique()
    with pytest.raises(GateFailure, match="missing=.*2020-08.*wrong_snapshot_count=.*2020-09"):
        verify_monthly_crosscheck(corrupted, official, protocol)


def test_official_membership_rejects_bse() -> None:
    _, official, protocol = _frames()
    corrupted = official.copy()
    corrupted.loc[0, "code"] = "920001.BJ"
    with pytest.raises(GateFailure, match=r"\.BJ"):
        verify_official_daily_membership(corrupted, protocol)
