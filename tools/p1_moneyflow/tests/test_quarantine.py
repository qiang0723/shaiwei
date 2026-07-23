from datetime import date

import pytest

from shaiwei.config import EvaluationWindow, StressPeriod, load
from tools.p1_moneyflow.quarantine import QuarantineError, evaluate_quarantine


def _documents() -> tuple[dict[str, object], dict[str, object]]:
    dates = ["20200102", "20200103", "20200106", "20200107", "20200108"]
    quality = {
        "schema_version": "p1-moneyflow-full-quality-v1",
        "source": {"revision_observed_count": 0, "saturated_response_count": 0},
        "per_trade_date": [
            {
                "trade_date": trade_date,
                "gate_status": "FAIL" if trade_date == "20200106" else "PASS",
                "issues": ["PRIMARY_AMOUNT_SCALE_MISMATCH"] if trade_date == "20200106" else [],
            }
            for trade_date in dates
        ],
    }
    refresh = {
        "schema_version": "p1-moneyflow-failed-date-refresh-v1",
        "status": "STABLE_REFRESH",
        "revision_trade_dates": [],
        "observations": [{"trade_date": "20200106"}],
    }
    return quality, refresh


def test_quarantine_requires_stable_refresh():
    quality, refresh = _documents()
    refresh["status"] = "REVISION_OBSERVED"
    refresh["revision_trade_dates"] = ["20200106"]
    with pytest.raises(QuarantineError, match="not stable"):
        evaluate_quarantine(quality, refresh)


def test_quarantine_evaluates_frozen_coverage(monkeypatch):
    quality, refresh = _documents()
    settings = load()
    settings.g1_admission.discovery_start = date(2020, 1, 2)
    settings.g1_admission.discovery_end = date(2020, 1, 8)
    settings.evaluation.g0_windows = [
        EvaluationWindow(
            name=f"W{index}",
            train_start=date(2019, 1, 1),
            train_end=date(2019, 12, 31),
            test_start=date(2020, 1, 2),
            test_end=date(2020, 1, 8),
        )
        for index in range(1, 7)
    ]
    settings.evaluation.stress_periods = [
        StressPeriod(name=f"S{index}", start=date(2020, 1, 2), end=date(2020, 1, 8))
        for index in range(1, 4)
    ]
    monkeypatch.setattr("tools.p1_moneyflow.quarantine.load", lambda: settings)
    result = evaluate_quarantine(quality, refresh)
    assert result["status"] == "FAIL"
    assert result["overall"]["valid_source_date_rate"] == 0.8
    assert result["quarantined_source_dates"] == [
        {"trade_date": "20200106", "issues": ["PRIMARY_AMOUNT_SCALE_MISMATCH"]}
    ]
