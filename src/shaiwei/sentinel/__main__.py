"""加载已提交数据并执行 S1-S10；任一必要哨兵 FAIL 则退出非零。"""

import gc
import json
import os
from datetime import datetime, timezone

import pandas as pd

from shaiwei.config import PROJECT_ROOT, load
from shaiwei.ingest.catalog import load_latest_api
from shaiwei.ledger import ingest_snapshot_sha256
from shaiwei.provenance import code_snapshot_sha256, git_head
from shaiwei.sentinel.checks import (
    s1_completeness,
    s2_dual_calculation,
    s3_reverse_adjustment,
    s4_units,
    s5_financial_pit,
    s6_suspensions,
    s7_price_volume_logic,
    s8_cross_source,
    s9_st_status,
    s10_git_consistency,
)
from shaiwei.transform.market import attach_trade_limit_flags, sanitize_adj_factors, transform_market_data
from shaiwei.transform.universe import active_securities


def main() -> int:
    settings = load()
    trade_cal = load_latest_api("tushare.trade_cal")
    stock_basic = load_latest_api("tushare.stock_basic")
    suspend_d = load_latest_api("tushare.suspend_d")
    daily = load_latest_api("tushare.daily")
    adj_factor = load_latest_api("tushare.adj_factor")
    namechange = load_latest_api("tushare.namechange")
    dividend = load_latest_api("tushare.dividend")
    adj_factor = sanitize_adj_factors(daily, adj_factor, dividend)
    results = {}
    results["S1"] = s1_completeness(
        trade_cal,
        stock_basic,
        daily,
        suspend_d,
        start=settings.backtest.start.strftime("%Y%m%d"),
        end=max(daily["trade_date"].astype(str)),
    )
    results["S2"] = s2_dual_calculation(
        daily,
        adj_factor,
        max_securities=settings.sentinels.dual_calculation_max_securities,
    )
    transformed = transform_market_data(daily, adj_factor)
    results["S3"] = s3_reverse_adjustment(
        transformed,
        daily,
        sample_codes=list(settings.sentinels.reverse_adjustment_samples.model_dump().values()),
    )
    results["S4"] = s4_units(transformed)
    attach_trade_limit_flags(
        transformed, stock_basic, namechange, settings.limit_rules.model_dump(), copy=False
    )

    suspended_keys = suspend_d.loc[
        suspend_d["suspend_type"].eq("S"), ["ts_code", "trade_date"]
    ].drop_duplicates()
    aligned_suspended = suspended_keys.merge(transformed, on=["ts_code", "trade_date"], how="left")
    results["S6"] = s6_suspensions(aligned_suspended, suspend_d)
    results["S7"] = s7_price_volume_logic(transformed, dividend)
    akshare = load_latest_api("akshare.stock_zh_a_hist")
    results["S8"] = s8_cross_source(daily, akshare)
    observation_date = settings.evaluation.forward_oos_start.strftime("%Y%m%d")
    active_codes = active_securities(
        stock_basic,
        settings.evaluation.forward_oos_start,
        include_bse=settings.universe.include_bse,
    )["ts_code"]
    st_observations = pd.DataFrame(
        {
            "ts_code": namechange.loc[namechange["ts_code"].isin(active_codes), "ts_code"].dropna().drop_duplicates(),
            "trade_date": observation_date,
        }
    )
    results["S9"] = s9_st_status(namechange, st_observations)
    del adj_factor, akshare, aligned_suspended, daily, dividend, transformed
    gc.collect()

    income = load_latest_api("tushare.income")
    balancesheet = load_latest_api("tushare.balancesheet")
    cashflow = load_latest_api("tushare.cashflow")
    results["S5"] = s5_financial_pit(
        income,
        trade_cal,
        statement_tables={"balancesheet": balancesheet, "cashflow": cashflow},
    )
    results["S10"] = s10_git_consistency(
        environment=settings.runtime.environment,
        expected_commit=os.getenv("SHAIWEI_EXPECTED_COMMIT"),
    )
    ordered_results = [results[f"S{number}"] for number in range(1, 11)]
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_head": git_head(),
        "code_snapshot_sha256": code_snapshot_sha256(),
        "data_snapshot_sha256": ingest_snapshot_sha256(),
        "required_failures": [result.sentinel for result in ordered_results if result.status == "FAIL"],
        "results": [result.to_dict() for result in ordered_results],
    }
    report_dir = PROJECT_ROOT / "logs" / "sentinels"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"{datetime.now(timezone.utc):%Y%m%dT%H%M%S.%fZ}.json"
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({**payload, "report_path": str(report_path)}, ensure_ascii=False, sort_keys=True))
    return 1 if payload["required_failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
