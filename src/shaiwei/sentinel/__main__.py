"""加载已提交数据并执行 S1-S10；任一必要哨兵 FAIL 则退出非零。"""

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
from shaiwei.transform.market import attach_trade_limit_flags, transform_market_data
from shaiwei.transform.universe import active_securities


def main() -> int:
    settings = load()
    trade_cal = load_latest_api("tushare.trade_cal")
    stock_basic = load_latest_api("tushare.stock_basic")
    namechange = load_latest_api("tushare.namechange")
    suspend_d = load_latest_api("tushare.suspend_d")
    daily = load_latest_api("tushare.daily")
    adj_factor = load_latest_api("tushare.adj_factor")
    income = load_latest_api("tushare.income")
    akshare = load_latest_api("akshare.stock_zh_a_hist")
    transformed = transform_market_data(daily, adj_factor)
    market_with_limits = attach_trade_limit_flags(
        transformed,
        stock_basic,
        namechange,
        settings.limit_rules.model_dump(),
    )

    suspended_keys = suspend_d.loc[
        suspend_d["suspend_type"].eq("S"), ["ts_code", "trade_date"]
    ].drop_duplicates()
    aligned_suspended = suspended_keys.merge(transformed, on=["ts_code", "trade_date"], how="left")
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
    results = [
        s1_completeness(
            trade_cal,
            stock_basic,
            daily,
            suspend_d,
            start=settings.backtest.start.strftime("%Y%m%d"),
            end=max(daily["trade_date"].astype(str)),
        ),
        s2_dual_calculation(daily, adj_factor),
        s3_reverse_adjustment(transformed, daily),
        s4_units(transformed),
        s5_financial_pit(income, trade_cal),
        s6_suspensions(aligned_suspended, suspend_d),
        s7_price_volume_logic(market_with_limits),
        s8_cross_source(daily, akshare),
        s9_st_status(namechange, st_observations),
        s10_git_consistency(
            environment=settings.runtime.environment,
            expected_commit=os.getenv("SHAIWEI_EXPECTED_COMMIT"),
        ),
    ]
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_head": git_head(),
        "code_snapshot_sha256": code_snapshot_sha256(),
        "data_snapshot_sha256": ingest_snapshot_sha256(),
        "required_failures": [result.sentinel for result in results if result.status == "FAIL"],
        "results": [result.to_dict() for result in results],
    }
    report_dir = PROJECT_ROOT / "logs" / "sentinels"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"{datetime.now(timezone.utc):%Y%m%dT%H%M%S.%fZ}.json"
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({**payload, "report_path": str(report_path)}, ensure_ascii=False, sort_keys=True))
    return 1 if payload["required_failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
