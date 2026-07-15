from datetime import date
from pathlib import Path

import pandas as pd

from shaiwei.ingest.akshare import AKShareIngestor, CrosscheckRequest
from shaiwei.ingest.core import RawBatchWriter


def test_akshare_history_is_normalized_and_recorded(tmp_path: Path):
    calls = []

    def fetch(**kwargs):
        calls.append(kwargs)
        return pd.DataFrame(
            [{
                "日期": "2026-07-15", "股票代码": "600519", "开盘": 1.0, "收盘": 2.0,
                "最高": 2.0, "最低": 1.0, "成交量": 3.0, "成交额": 4.0,
            }]
        )

    recorded = []
    writer = RawBatchWriter(tmp_path, recorder=lambda **kwargs: recorded.append(kwargs) or "id")
    request = CrosscheckRequest("600519.SH", date(2026, 7, 15), date(2026, 7, 15))
    batch = AKShareIngestor(writer, fetch=fetch).run([request])[0]

    assert calls[0]["adjust"] == ""
    assert pd.read_parquet(batch.parquet_path).loc[0, "ts_code"] == "600519.SH"
    assert pd.read_parquet(batch.parquet_path).loc[0, "trade_date"] == "20260715"
    assert recorded[0]["source_api"] == "akshare.stock_zh_a_hist"
