import pandas as pd

from shaiwei.research.trend_swing.contract import TrendSwingProtocol
from shaiwei.research.trend_swing.run import judge_preflight
from shaiwei.research.trend_swing.sources import latest_source_entries


def test_latest_source_entries_preserves_latest_request_identity():
    ledger = pd.DataFrame(
        {
            "batch_id": ["old", "new", "other"],
            "ingest_time": ["2026-01-01T00:00:00Z", "2026-01-02T00:00:00Z", "2026-01-01T00:00:00Z"],
            "source_api": ["tushare.daily", "tushare.daily", "tushare.daily"],
            "params_json": ['{"ts_code":"1"}', '{"ts_code":"1"}', '{"ts_code":"2"}'],
            "row_count": ["1", "1", "1"],
            "parquet_path": ["a", "b", "c"],
            "content_sha256": ["0", "1", "2"],
        }
    )
    latest = latest_source_entries(ledger, "tushare.daily")
    assert latest["batch_id"].tolist() == ["other", "new"]


def test_missing_chinext_blocks_without_fallback():
    protocol = TrendSwingProtocol.load()
    manifest = {
        "required_sources_missing": [],
        "alpha158": {"present": True},
    }
    indexes = [
        {"ts_code": "000906.SH", "duplicate_date_count": 0},
        {"ts_code": "000688.SH", "duplicate_date_count": 0},
    ]
    blocks, details = judge_preflight(protocol, manifest, indexes)
    assert blocks == ["BLOCKED_MARKET_RULE"]
    assert details == [
        {
            "code": "OFFICIAL_SEGMENT_INDEX_MISSING",
            "segment": "chinext",
            "benchmark_code": "399006.SZ",
        }
    ]


def test_duplicate_index_date_blocks_data_even_when_all_indices_exist():
    protocol = TrendSwingProtocol.load()
    manifest = {
        "required_sources_missing": [],
        "alpha158": {"present": True},
    }
    indexes = [
        {"ts_code": "000906.SH", "duplicate_date_count": 0},
        {"ts_code": "399006.SZ", "duplicate_date_count": 2},
        {"ts_code": "000688.SH", "duplicate_date_count": 0},
    ]
    blocks, details = judge_preflight(protocol, manifest, indexes)
    assert blocks == ["BLOCKED_DATA"]
    assert details[0]["code"] == "INDEX_DUPLICATE_DATE"
