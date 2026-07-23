from pathlib import Path

import pandas as pd

from tools.p1_moneyflow.contract import MONEYFLOW_FIELDS
from tools.p1_moneyflow.full_audit import _quality_query, evaluate_quality_table


def _row() -> dict[str, object]:
    return {
        "trade_date": "20260723",
        "moneyflow_rows": 1000,
        "moneyflow_distinct_codes": 1000,
        "daily_rows": 1000,
        "daily_distinct_codes": 1000,
        "intersection_codes": 1000,
        "source_only_codes": 0,
        "daily_only_codes": 0,
        "null_or_nonfinite_rows": 0,
        "negative_gross_rows": 0,
        "bse_rows": 0,
        "classified_amount_ratio_median": 2.0,
        "classified_volume_ratio_median": 2.0,
        "net_scale_tail_rows": 0,
    }


def test_full_quality_gate_passes_complete_day():
    result = evaluate_quality_table(pd.DataFrame([_row()])).iloc[0]
    assert result["gate_status"] == "PASS"
    assert result["issues"] == []
    assert result["daily_coverage_rate"] == 1.0


def test_full_quality_gate_fails_key_scope_coverage_and_scale():
    row = _row()
    row.update(
        moneyflow_rows=998,
        moneyflow_distinct_codes=997,
        intersection_codes=990,
        source_only_codes=8,
        bse_rows=1,
        classified_amount_ratio_median=1.8,
    )
    result = evaluate_quality_table(pd.DataFrame([row])).iloc[0]
    assert result["gate_status"] == "FAIL"
    assert {
        "DUPLICATE_MONEYFLOW_KEY",
        "BSE_ROW_PRESENT",
        "PRIMARY_COVERAGE_BELOW_GATE",
        "PRIMARY_SOURCE_ONLY_ABOVE_GATE",
        "PRIMARY_AMOUNT_SCALE_MISMATCH",
    } <= set(result["issues"])


def test_full_quality_tail_is_warning_not_failure():
    row = _row()
    row["net_scale_tail_rows"] = 1
    result = evaluate_quality_table(pd.DataFrame([row])).iloc[0]
    assert result["gate_status"] == "PASS"
    assert result["warnings"] == ["NET_FLOW_EXCEEDS_DAILY_SCALE_TAIL"]


def test_duckdb_quality_query_reconciles_source_and_daily(tmp_path: Path):
    source_rows = []
    for code in ("000001.SZ", "600001.SH"):
        row = {column: 1.0 for column in MONEYFLOW_FIELDS["moneyflow"]}
        row.update(ts_code=code, trade_date="20260723", net_mf_amount=-1.0)
        source_rows.append(row)
    moneyflow_path = tmp_path / "moneyflow.parquet"
    daily_path = tmp_path / "daily.parquet"
    pd.DataFrame(source_rows, columns=MONEYFLOW_FIELDS["moneyflow"]).to_parquet(
        moneyflow_path, index=False
    )
    pd.DataFrame(
        [
            {
                "ts_code": code,
                "trade_date": "20260723",
                "amount": 40.0,
                "vol": 4.0,
            }
            for code in ("000001.SZ", "600001.SH")
        ]
    ).to_parquet(daily_path, index=False)
    quality = evaluate_quality_table(
        _quality_query([str(moneyflow_path)], [str(daily_path)], ["20260723"])
    ).iloc[0]
    assert quality["gate_status"] == "PASS"
    assert quality["classified_amount_ratio_median"] == 2.0
    assert quality["classified_volume_ratio_median"] == 2.0
