import json
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from shaiwei.config import load
from shaiwei.shadow.manifest import write_signal_manifest
from shaiwei.shadow.reconciliation import (
    next_open_date,
    reconcile_forward_signal,
    tushare_code,
)


def _sentinels():
    return [
        {"sentinel": f"S{number}", "status": "NOT_APPLICABLE" if number == 10 else "PASS"}
        for number in range(1, 11)
    ]


def _manifest(root: Path, day: date, instruments: list[str]) -> Path:
    scores = pd.DataFrame(
        {"instrument": instruments, "score": list(range(len(instruments), 0, -1))}
    )
    path, _ = write_signal_manifest(
        scores,
        signal_date=day,
        topk=len(instruments),
        sentinel_results=_sentinels(),
        data_complete_at=datetime.now(timezone.utc),
        generated_at=datetime.now(timezone.utc),
        data_snapshot_sha256=str(day) * 4,
        code_commit="abc",
        code_snapshot_sha256=("c" * 64),
        output_dir=root,
    )
    return path


def test_next_open_date_and_code_mapping():
    calendar = pd.DataFrame(
        {"cal_date": ["20260716", "20260717", "20260718"], "is_open": [1, 1, 0]}
    )
    assert next_open_date(calendar, "20260716") == "20260717"
    assert tushare_code("SH600000") == "600000.SH"
    assert tushare_code("SZ000001") == "000001.SZ"


def test_reconciliation_uses_real_next_open_and_directional_limits(tmp_path: Path):
    settings = load()
    settings.baseline.account = 1_000_000
    current = _manifest(tmp_path / "signals-current", date(2026, 7, 16), ["SH600001", "SZ000001"])
    previous = _manifest(tmp_path / "signals-previous", date(2026, 7, 15), ["SH600002", "SZ000001"])
    signal_daily = pd.DataFrame(
        [
            {"ts_code": "600001.SH", "close": 10.0},
            {"ts_code": "600002.SH", "close": 10.0},
            {"ts_code": "000001.SZ", "close": 10.0},
        ]
    )
    execution_daily = pd.DataFrame(
        [
            {"ts_code": "600001.SH", "trade_date": "20260717", "open": 11.0, "pre_close": 10.0, "vol": 100},
            {"ts_code": "600002.SH", "trade_date": "20260717", "open": 9.0, "pre_close": 10.0, "vol": 100},
            {"ts_code": "000001.SZ", "trade_date": "20260717", "open": 10.2, "pre_close": 10.0, "vol": 100},
        ]
    )
    stock_basic = pd.DataFrame(
        [
            {"ts_code": code, "list_date": "20100101"}
            for code in ("600001.SH", "600002.SH", "000001.SZ")
        ]
    )
    namechange = pd.DataFrame(
        [
            {"ts_code": code, "name": "普通", "start_date": "20100101", "end_date": None}
            for code in ("600001.SH", "600002.SH", "000001.SZ")
        ]
    )
    result = reconcile_forward_signal(
        settings,
        manifest_path=current,
        previous_manifest_path=previous,
        execution_trade_date="20260717",
        signal_daily=signal_daily,
        execution_daily=execution_daily,
        stock_basic=stock_basic,
        namechange=namechange,
        output_root=tmp_path / "output",
    )
    assert result.order_count == 2
    assert result.trade_count == 2
    assert result.executable_count == 0
    assert result.turnover == pytest.approx(0.5)
    assert result.mean_abs_open_deviation == pytest.approx(0.06)
    document = json.loads(result.artifact_path.read_text())
    statuses = {row["ts_code"]: row["reconcile_status"] for row in document["rows"]}
    assert statuses["600001.SH"] == "BUY_LIMIT_UP"
    assert statuses["600002.SH"] == "SELL_LIMIT_DOWN"
