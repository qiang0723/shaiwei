from pathlib import Path

import pandas as pd
import pytest

from shaiwei.config import load
from shaiwei.ingest.core import RawBatchWriter
from tools.p1_moneyflow import contract
from tools.p1_moneyflow.contract import (
    MONEYFLOW_FIELDS,
    MoneyflowIngestError,
    MoneyflowIngestor,
    PIT_POLICY,
    Request,
    build_moneyflow_plan,
    canonical_frame_sha256,
    profile_moneyflow_batch,
    write_project_json,
)


def _moneyflow(codes: list[str], trade_date: str = "20260723") -> pd.DataFrame:
    rows = []
    for code in codes:
        row = {column: 1.0 for column in MONEYFLOW_FIELDS["moneyflow"]}
        row.update(ts_code=code, trade_date=trade_date, net_mf_vol=-1.0, net_mf_amount=-1.0)
        rows.append(row)
    return pd.DataFrame(rows, columns=MONEYFLOW_FIELDS["moneyflow"])


def _daily(codes: list[str], trade_date: str = "20260723") -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "ts_code": code,
                "trade_date": trade_date,
                "close": 10.0,
                "pct_chg": 0.0,
                "vol": 4.0,
                "amount": 40.0,
            }
            for code in codes
        ]
    )


def test_plan_is_deterministic_and_validated():
    plan = build_moneyflow_plan(
        ["20260723", "20260722", "20260723"],
        apis=("moneyflow", "moneyflow_dc"),
    )
    assert [(item.api_name, item.trade_date) for item in plan] == [
        ("moneyflow", "20260722"),
        ("moneyflow_dc", "20260722"),
        ("moneyflow", "20260723"),
        ("moneyflow_dc", "20260723"),
    ]


@pytest.mark.parametrize("trade_date", ["2026-07-23", "2026073", "not-a-date"])
def test_plan_rejects_invalid_trade_date(trade_date: str):
    with pytest.raises(ValueError, match="invalid YYYYMMDD"):
        build_moneyflow_plan([trade_date])


def test_ingestor_checks_source_limit_before_bse_filter(tmp_path: Path):
    class Client:
        def query(self, api_name: str, **kwargs):
            fields = kwargs["fields"].split(",")
            values = {}
            for field in fields:
                if field == "ts_code":
                    values[field] = ["000001.SZ", "920001.BJ"]
                elif field == "trade_date":
                    values[field] = [kwargs["trade_date"], kwargs["trade_date"]]
                else:
                    values[field] = [0, 0]
            return pd.DataFrame(values)

    settings = load()
    settings.ingest.min_request_interval_seconds = 0
    settings.ingest.source_row_limit = 2
    settings.ingest.max_attempts = 1
    with pytest.raises(MoneyflowIngestError, match="possible truncation"):
        MoneyflowIngestor(
            client=Client(),
            writer=RawBatchWriter(tmp_path, recorder=lambda **_: "id"),
            settings=settings,
        ).run([Request("moneyflow_dc", "20260723")])


def test_primary_profile_passes_complete_unique_batch():
    profile = profile_moneyflow_batch(
        "moneyflow",
        "20260723",
        _moneyflow(["000001.SZ", "600001.SH"]),
        daily=_daily(["000001.SZ", "600001.SH"]),
    )
    assert profile["gate_status"] == "PASS"
    assert profile["issues"] == []
    assert profile["coverage"]["daily_coverage_rate"] == 1.0
    assert profile["consistency"]["classified_amount_to_daily_ratio"]["median"] == 2.0
    assert profile["pit_policy"]["feature_available_lag_trade_days"] == 1


def test_primary_profile_fails_duplicates_bse_and_low_coverage():
    frame = pd.concat(
        [_moneyflow(["000001.SZ"]), _moneyflow(["000001.SZ", "920001.BJ"])],
        ignore_index=True,
    )
    profile = profile_moneyflow_batch(
        "moneyflow",
        "20260723",
        frame,
        daily=_daily(["000001.SZ", "600001.SH"]),
    )
    assert profile["gate_status"] == "FAIL"
    assert {"DUPLICATE_KEY", "BSE_ROW_PRESENT", "PRIMARY_COVERAGE_BELOW_GATE"} <= set(
        profile["issues"]
    )


def test_diagnostic_signed_net_and_suspension_are_preserved():
    rows = []
    for code in ("000001.SZ", "000002.SZ"):
        row = {column: 1.0 for column in MONEYFLOW_FIELDS["moneyflow_ths"]}
        row.update(
            ts_code=code,
            trade_date="20260723",
            name=code,
            latest=10.0,
            pct_change=0.0,
            buy_sm_amount=-1.0,
            buy_sm_amount_rate=-1.0,
        )
        rows.append(row)
    frame = pd.DataFrame(rows, columns=MONEYFLOW_FIELDS["moneyflow_ths"])
    suspensions = pd.DataFrame(
        [{"ts_code": "000002.SZ", "trade_date": "20260723", "suspend_type": "S"}]
    )
    profile = profile_moneyflow_batch(
        "moneyflow_ths",
        "20260723",
        frame,
        daily=_daily(["000001.SZ"]),
        suspensions=suspensions,
    )
    assert profile["gate_status"] == "DIAGNOSTIC_PASS"
    assert profile["coverage"]["source_only_suspended_codes"] == 1


def test_hash_is_row_order_invariant_and_tail_is_warning():
    frame = _moneyflow(["600001.SH", "000001.SZ"])
    assert canonical_frame_sha256("moneyflow", frame) == canonical_frame_sha256(
        "moneyflow", frame.iloc[::-1]
    )
    frame = _moneyflow(["000001.SZ"])
    frame.loc[0, "net_mf_amount"] = 5.0
    profile = profile_moneyflow_batch(
        "moneyflow",
        "20260723",
        frame,
        daily=_daily(["000001.SZ"]),
    )
    assert profile["gate_status"] == "PASS"
    assert profile["warnings"] == ["NET_FLOW_EXCEEDS_DAILY_SCALE_TAIL"]


def test_project_json_is_non_overwriting_and_scoped(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(contract, "PROJECT_ROOT", tmp_path)
    target = tmp_path / "logs" / "evidence.json"
    write_project_json(target, {"pit": PIT_POLICY})
    with pytest.raises(FileExistsError):
        write_project_json(target, {"pit": PIT_POLICY})
    with pytest.raises(ValueError, match="inside project"):
        write_project_json(tmp_path.parent / "outside.json", {})
