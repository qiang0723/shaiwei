import csv
from pathlib import Path

import pytest

from shaiwei.config import load
from shaiwei.shadow.report import build_forward_report


def _write(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def test_forward_report_aggregates_operating_results_and_recoveries(tmp_path: Path):
    daily = tmp_path / "daily.csv"
    shadow = tmp_path / "shadow.csv"
    reconciliation = tmp_path / "reconciliation.csv"
    _write(
        daily,
        [
            {"target_trade_date": day, "status": "PASS"}
            for day in ("20260715", "20260716", "20260717")
        ],
    )
    _write(
        shadow,
        [
            {"finished_at": "1", "signal_trade_date": "20260714", "status": "FAIL", "on_time": "false"},
            {"finished_at": "2", "signal_trade_date": "20260714", "status": "PASS", "on_time": "true"},
            {"finished_at": "3", "signal_trade_date": "20260715", "status": "PASS", "on_time": "true"},
            {"finished_at": "4", "signal_trade_date": "20260716", "status": "PASS", "on_time": "false"},
        ],
    )
    _write(
        reconciliation,
        [
            {
                "finished_at": str(index),
                "signal_trade_date": signal,
                "execution_trade_date": execution,
                "status": "PASS",
                "trade_count": 10,
                "executable_count": executable,
                "turnover": turnover,
                "mean_abs_open_deviation": deviation,
                "estimated_cost": cost,
            }
            for index, (signal, execution, executable, turnover, deviation, cost) in enumerate(
                [
                    ("20260714", "20260715", 9, 1.0, 0.01, 0.001),
                    ("20260715", "20260716", 10, 0.2, 0.02, 0.002),
                    ("20260716", "20260717", 8, 0.3, 0.03, 0.003),
                ],
                start=1,
            )
        ],
    )
    report = build_forward_report(
        load(),
        daily_path=daily,
        shadow_path=shadow,
        reconciliation_path=reconciliation,
    )
    assert report["trial_ready"] is True
    assert report["signal_count"] == 3
    assert report["on_time_signal_rate"] == pytest.approx(2 / 3)
    assert report["trade_executable_rate"] == pytest.approx(0.9)
    assert report["average_turnover"] == pytest.approx(0.5)
    assert report["failure_count"] == 1
    assert report["recovery_count"] == 1
