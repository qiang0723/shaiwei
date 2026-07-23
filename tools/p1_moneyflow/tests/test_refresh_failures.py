import pytest

from tools.p1_moneyflow.refresh_failures import RefreshFailureError, failed_trade_dates


def test_failed_trade_dates_are_unique_and_sorted():
    assert failed_trade_dates(
        {
            "schema_version": "p1-moneyflow-full-quality-v1",
            "per_trade_date": [
                {"trade_date": "20260724", "gate_status": "FAIL"},
                {"trade_date": "20260723", "gate_status": "PASS"},
                {"trade_date": "20260722", "gate_status": "FAIL"},
                {"trade_date": "20260724", "gate_status": "FAIL"},
            ],
        }
    ) == ["20260722", "20260724"]


def test_failed_trade_dates_refuse_wrong_or_passing_report():
    with pytest.raises(RefreshFailureError, match="not a full-history"):
        failed_trade_dates({"schema_version": "wrong", "per_trade_date": []})
    with pytest.raises(RefreshFailureError, match="no failed"):
        failed_trade_dates(
            {
                "schema_version": "p1-moneyflow-full-quality-v1",
                "per_trade_date": [{"trade_date": "20260723", "gate_status": "PASS"}],
            }
        )
