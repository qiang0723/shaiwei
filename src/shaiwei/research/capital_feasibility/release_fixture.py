"""Pure synthetic daemon fixture for the M6-5B release image."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from shaiwei.research.model_attribution.contract import canonical_sha256
from shaiwei.research.production_conversion.real_contract import write_once_document

from .audit_statistics import independently_evaluate
from .release_contract import ReleaseProtocol
from .release_metrics import evaluate
from .simulation import run_all
from .source_reader import RawSources


def _synthetic() -> tuple[dict, RawSources]:
    calendar = pd.bdate_range("2020-01-02", periods=55)
    dates = [day.strftime("%Y%m%d") for day in calendar]
    codes = [f"{600000 + index:06d}.SH" for index in range(30)]
    qlib_codes = [f"SH{code[:6]}" for code in codes]
    daily_rows = []
    for offset, day in enumerate(dates):
        price = 10.0 * (1.001**max(0, offset - 25))
        for code in codes:
            daily_rows.append({
                "ts_code": code, "trade_date": day, "open": price,
                "pre_close": price / 1.001 if offset > 25 else price,
                "close": price, "vol": 1000000.0, "amount": 100000.0,
                "amount_rmb": 100000000.0,
            })
    test_dates = dates[25:]
    treatment = {
        "daily": [
            {"date": pd.Timestamp(day).strftime("%Y-%m-%d"), "gross_return": 0.001, "recorded_cost": 0.0}
            for day in calendar[25:]
        ],
        "rebalances": [{
            "trade_date": pd.Timestamp(calendar[25]).strftime("%Y-%m-%d"),
            "signal_date": pd.Timestamp(calendar[24]).strftime("%Y-%m-%d"),
            "targets": qlib_codes,
        }],
    }
    bundle = {"treatments": {f"W{index}": treatment for index in range(1, 7)}}
    sources = RawSources(
        daily=pd.DataFrame(daily_rows),
        index_daily=pd.DataFrame([
            {"ts_code": "000906.SH", "trade_date": day, "open": 100.0, "close": 100.0}
            for day in test_dates
        ]),
        stock_basic=pd.DataFrame([
            {"ts_code": code, "list_date": "20100101", "delist_date": ""} for code in codes
        ]),
        namechange=pd.DataFrame(columns=["ts_code", "name", "start_date", "end_date"]),
        suspend=pd.DataFrame(columns=["ts_code", "trade_date", "suspend_type", "suspend_timing"]),
        dividends=pd.DataFrame(columns=[
            "ts_code", "end_date", "ann_date", "div_proc", "stk_div", "cash_div_tax",
            "record_date", "pay_date", "div_listdate", "imp_ann_date",
        ]),
        trade_cal=pd.DataFrame([
            {"exchange": "SSE", "cal_date": day, "is_open": "1"} for day in dates
        ]),
        manifest_sha256="0" * 64,
    )
    return bundle, sources


def build_fixture() -> dict:
    protocol = ReleaseProtocol.load()
    bundle, sources = _synthetic()
    first = run_all(bundle, sources)
    first["result"] = evaluate(first)
    replay = run_all(bundle, sources)
    replay["result"] = evaluate(replay)
    independent = independently_evaluate(first)
    if first != replay or canonical_sha256(first["result"]) != canonical_sha256(independent):
        raise RuntimeError("M6-5B synthetic replay or independent audit differs")
    if first["result"]["decision"] != "CAPITAL_FEASIBLE_RESEARCH_ONLY":
        raise RuntimeError("M6-5B synthetic feasible path failed")
    return {
        "schema_version": "m6-head30-500k-release-fixture-v1", "status": "PASS",
        "protocol_sha256": protocol.sha256, "recovery_sha256": protocol.recovery_sha256,
        "execute_day_reused": True, "deterministic_replay": True,
        "independent_reconstruction": True, "real_target_read": False,
        "real_price_or_effect_read": False, "network_used": False,
        "model_fit_count": 0, "production_authorization": "none",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    document = build_fixture()
    digest, reused = write_once_document(parser.parse_args().output, document)
    print(json.dumps({**document, "sha256": digest, "reused": reused}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
