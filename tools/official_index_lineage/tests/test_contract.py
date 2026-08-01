from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
import yaml

from shaiwei.config import PROJECT_ROOT
from tools.official_index_lineage.contract import (
    DataGateError,
    Request,
    build_plan,
    canonical_frame_sha256,
    load_protocol,
    validate_response,
    write_immutable_json,
)

PROTOCOL = PROJECT_ROOT / "config" / "m2_star200_v1.yaml"


def test_frozen_protocol_and_request_plan() -> None:
    protocol = load_protocol(PROTOCOL)
    plan = build_plan(protocol)
    assert len(plan) == 27
    assert sum(item.api_name == "index_daily" for item in plan) == 3
    assert sum(item.api_name == "index_weight" for item in plan) == 24
    assert plan[0].start_date == "20240820"
    assert plan[-1].partition_name == "2026-07"
    assert {item.index_code for item in plan} == {"000699.SH"}


def test_protocol_unknown_field_fails_closed(tmp_path: Path) -> None:
    payload = yaml.safe_load(PROTOCOL.read_text(encoding="utf-8"))
    payload["unexpected"] = True
    path = tmp_path / "bad.yaml"
    path.write_text(yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8")
    with pytest.raises(DataGateError, match="schema drift"):
        load_protocol(path)


def test_protocol_hash_drift_fails_closed(tmp_path: Path) -> None:
    payload = yaml.safe_load(PROTOCOL.read_text(encoding="utf-8"))
    payload["protocol_sha256"] = "0" * 64
    path = tmp_path / "bad.yaml"
    path.write_text(yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8")
    with pytest.raises(DataGateError, match="hash mismatch"):
        load_protocol(path)


def _daily_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "ts_code": "000699.SH",
                "trade_date": "20240820",
                "open": 1000.0,
                "high": 1010.0,
                "low": 990.0,
                "close": 1005.0,
                "pre_close": 1000.0,
                "change": 5.0,
                "pct_chg": 0.5,
                "vol": 1.0,
                "amount": 2.0,
            }
        ]
    )


def test_response_validation_and_hash_are_order_stable() -> None:
    request = Request("index_daily", "000699.SH", "20240820", "20241231", "2024")
    frame = _daily_frame()
    validated = validate_response(request, frame, 6000)
    assert canonical_frame_sha256("index_daily", validated) == canonical_frame_sha256(
        "index_daily", validated.iloc[::-1]
    )


def test_response_rejects_index_drift_and_bse() -> None:
    request = Request("index_daily", "000699.SH", "20240820", "20241231", "2024")
    bad = _daily_frame().assign(ts_code="000698.SH")
    with pytest.raises(DataGateError, match="identity mismatch"):
        validate_response(request, bad, 6000)
    weight_request = Request("index_weight", "000699.SH", "20240801", "20240831", "2024-08")
    weight = pd.DataFrame(
        [{"index_code": "000699.SH", "con_code": "920001.BJ", "trade_date": "20240830", "weight": 1.0}]
    )
    with pytest.raises(DataGateError, match="forbidden .BJ"):
        validate_response(weight_request, weight, 6000)


def test_immutable_json_reuses_exact_content_and_rejects_change(tmp_path: Path) -> None:
    path = tmp_path / "evidence.json"
    assert write_immutable_json(path, {"a": 1}) is True
    assert write_immutable_json(path, {"a": 1}) is False
    with pytest.raises(FileExistsError, match="differs"):
        write_immutable_json(path, {"a": 2})
