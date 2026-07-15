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
                "date": "2026-07-15", "open": 1.0, "close": 2.0,
                "high": 2.0, "low": 1.0, "volume": 300.0, "amount": 4.0,
            }]
        )

    recorded = []
    writer = RawBatchWriter(tmp_path, recorder=lambda **kwargs: recorded.append(kwargs) or "id")
    request = CrosscheckRequest("600519.SH", date(2026, 7, 15), date(2026, 7, 15))
    batch = AKShareIngestor(writer, fetch=fetch).run([request])[0]

    assert calls[0]["adjust"] == ""
    assert calls[0]["symbol"] == "sh600519"
    assert pd.read_parquet(batch.parquet_path).loc[0, "ts_code"] == "600519.SH"
    assert pd.read_parquet(batch.parquet_path).loc[0, "trade_date"] == "20260715"
    assert pd.read_parquet(batch.parquet_path).loc[0, "vol"] == 3.0
    assert recorded[0]["source_api"] == "akshare.stock_zh_a_daily"


def test_akshare_retries_transient_network_failures_through_configured_window(tmp_path: Path):
    attempts = []

    def fetch(**kwargs):
        attempts.append(kwargs)
        if len(attempts) < 6:
            raise ConnectionError("temporary proxy disconnect")
        return pd.DataFrame(
            [{
                "date": "2026-07-15", "open": 1.0, "close": 2.0,
                "high": 2.0, "low": 1.0, "volume": 300.0, "amount": 4.0,
            }]
        )

    ingestor = AKShareIngestor(
        RawBatchWriter(tmp_path, recorder=lambda **_: "id"),
        fetch=fetch,
        max_attempts=6,
        retry_base_seconds=0,
    )
    request = CrosscheckRequest("600519.SH", date(2026, 7, 15), date(2026, 7, 15))

    assert ingestor.run([request])[0].row_count == 1
    assert len(attempts) == 6
