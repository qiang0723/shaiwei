"""S1-S10 的纯函数实现。FAIL 必须携带可复核指标。"""

import os
import subprocess
from dataclasses import asdict, dataclass, field
from typing import Literal

import duckdb
import numpy as np
import pandas as pd

from shaiwei.transform.market import transform_market_data
from shaiwei.transform.pit import financial_pit_snapshot
from shaiwei.transform.universe import st_status_on

Status = Literal["PASS", "FAIL", "NOT_APPLICABLE"]


@dataclass(frozen=True)
class SentinelResult:
    sentinel: str
    status: Status
    metrics: dict[str, object] = field(default_factory=dict)
    anomalies: list[dict[str, object]] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def s1_completeness(
    trade_cal: pd.DataFrame,
    stock_basic: pd.DataFrame,
    daily: pd.DataFrame,
    suspend_d: pd.DataFrame,
    *,
    start: str,
    end: str,
) -> SentinelResult:
    open_days = set(trade_cal.loc[trade_cal["is_open"].astype(str).eq("1"), "cal_date"].astype(str))
    open_days = {day for day in open_days if start <= day <= end}
    suspended = suspend_d.loc[suspend_d["suspend_type"].eq("S")].groupby("ts_code")["trade_date"].agg(set)
    bars = daily.groupby("ts_code")["trade_date"].agg(set)
    anomalies = []
    for security in stock_basic.drop_duplicates("ts_code").itertuples(index=False):
        life_start = max(start, str(security.list_date))
        delist = str(security.delist_date) if pd.notna(security.delist_date) and str(security.delist_date) else end
        life_end = min(end, delist)
        if life_start > life_end:
            continue
        expected_days = {day for day in open_days if life_start <= day <= life_end}
        security_bars = bars.get(security.ts_code, set())
        security_suspensions = suspended.get(security.ts_code, set()) & expected_days
        missing = expected_days - security_bars
        unresolved = missing - security_suspensions
        unexpected = security_bars - expected_days
        if unresolved or unexpected or missing != security_suspensions:
            anomalies.append(
                {
                    "ts_code": security.ts_code,
                    "expected_open_days": len(expected_days),
                    "bar_days": len(security_bars & expected_days),
                    "suspend_days": len(security_suspensions),
                    "unresolved_missing_days": len(unresolved),
                    "unexpected_bar_days": len(unexpected),
                }
            )
    return SentinelResult(
        "S1",
        "PASS" if not anomalies else "FAIL",
        {"security_count": int(stock_basic["ts_code"].nunique()), "anomaly_count": len(anomalies)},
        anomalies[:1000],
    )


def s2_dual_calculation(daily: pd.DataFrame, adj_factor: pd.DataFrame, tolerance: float = 1e-12) -> SentinelResult:
    pandas_result = transform_market_data(daily, adj_factor)
    connection = duckdb.connect(":memory:")
    connection.register("daily", daily)
    connection.register("adj", adj_factor)
    sql_result = connection.execute(
        """
        WITH joined AS (
          SELECT d.*, a.adj_factor,
                 first_value(a.adj_factor) OVER (
                   PARTITION BY d.ts_code ORDER BY d.trade_date
                   ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
                 ) AS first_factor
          FROM daily d JOIN adj a USING (ts_code, trade_date)
        ), adjusted AS (
          SELECT ts_code, trade_date,
                 close * adj_factor / first_factor AS close,
                 amount * 1000.0 / (vol * 100.0 / (adj_factor / first_factor)) AS vwap
          FROM joined
        ), with_return AS (
          SELECT *, close / lag(close) OVER (PARTITION BY ts_code ORDER BY trade_date) - 1 AS ret
          FROM adjusted
        )
        SELECT ts_code, trade_date, close, vwap,
               avg(ret) OVER (PARTITION BY trade_date) AS equal_weight_return
        FROM with_return ORDER BY ts_code, trade_date
        """
    ).df()
    connection.close()
    pandas_result["equal_weight_return"] = pandas_result.groupby("ts_code")["close"].pct_change(fill_method=None)
    pandas_result["equal_weight_return"] = pandas_result.groupby("trade_date")["equal_weight_return"].transform("mean")
    comparison = pandas_result.merge(sql_result, on=["ts_code", "trade_date"], suffixes=("_pd", "_sql"))
    errors = {}
    for field_name in ("close", "vwap", "equal_weight_return"):
        delta = (comparison[f"{field_name}_pd"] - comparison[f"{field_name}_sql"]).abs().dropna()
        errors[field_name] = float(delta.max()) if not delta.empty else 0.0
    passed = len(comparison) == len(pandas_result) == len(sql_result) and max(errors.values()) < tolerance
    return SentinelResult(
        "S2",
        "PASS" if passed else "FAIL",
        {"row_count": len(comparison), "tolerance": tolerance, "max_abs_error": errors},
    )


def s3_reverse_adjustment(transformed: pd.DataFrame, daily: pd.DataFrame, tolerance: float = 1e-4) -> SentinelResult:
    source = daily.loc[:, ["ts_code", "trade_date", "close"]].rename(columns={"close": "raw_close"})
    joined = transformed.merge(source, on=["ts_code", "trade_date"], validate="one_to_one")
    reversed_close = joined["close"] * joined["factor"]
    relative_error = ((reversed_close - joined["raw_close"]).abs() / joined["raw_close"].abs()).replace(
        [np.inf, -np.inf], np.nan
    )
    maximum = float(relative_error.max()) if relative_error.notna().any() else 0.0
    return SentinelResult("S3", "PASS" if maximum < tolerance else "FAIL", {"max_relative_error": maximum})


def s4_units(transformed: pd.DataFrame) -> SentinelResult:
    calculated = transformed["amount"] / transformed["volume"].replace(0, np.nan)
    ratio = (transformed["vwap"] / calculated).replace([np.inf, -np.inf], np.nan).dropna()
    outliers = ratio.loc[~ratio.between(0.5, 2.0)]
    return SentinelResult(
        "S4",
        "PASS" if outliers.empty and not ratio.empty else "FAIL",
        {"checked_rows": len(ratio), "ratio_min": float(ratio.min()), "ratio_max": float(ratio.max())},
        transformed.loc[outliers.index, ["ts_code", "trade_date"]].head(100).to_dict("records"),
    )


def s5_financial_pit(statements: pd.DataFrame, trade_cal: pd.DataFrame) -> SentinelResult:
    boe = statements.loc[statements["ts_code"].eq("000725.SZ")].copy()
    boe["_f_ann"] = pd.to_datetime(boe["f_ann_date"], format="%Y%m%d", errors="coerce")
    old = boe.loc[boe["report_type"].astype(str).eq("5") & boe["update_flag"].astype(str).eq("0")]
    new = boe.loc[boe["report_type"].astype(str).eq("1") & boe["update_flag"].astype(str).eq("1")]
    pairs = old.merge(new, on=["ts_code", "end_date"], suffixes=("_old", "_new"))
    pairs = pairs.loc[pairs["_f_ann_old"].lt(pairs["_f_ann_new"])]
    if pairs.empty:
        return SentinelResult("S5", "FAIL", {"reason": "BOE 2023 restatement pair not found"})
    pair = pairs.sort_values("_f_ann_new").iloc[0]
    open_days = pd.to_datetime(
        trade_cal.loc[trade_cal["is_open"].astype(str).eq("1"), "cal_date"], format="%Y%m%d", errors="coerce"
    ).dropna().sort_values()
    between = open_days.loc[open_days.gt(pair["_f_ann_old"]) & open_days.lt(pair["_f_ann_new"])]
    after = open_days.loc[open_days.gt(pair["_f_ann_new"])]
    if between.empty or after.empty:
        return SentinelResult("S5", "FAIL", {"reason": "calendar cannot bracket BOE correction"})
    before_snapshot = financial_pit_snapshot(boe, trade_cal, between.iloc[-1].strftime("%Y-%m-%d"))
    after_snapshot = financial_pit_snapshot(boe, trade_cal, after.iloc[0].strftime("%Y-%m-%d"))
    period = pair["end_date"]
    before_row = before_snapshot.loc[before_snapshot["end_date"].eq(period)]
    after_row = after_snapshot.loc[after_snapshot["end_date"].eq(period)]
    passed = (
        not before_row.empty
        and not after_row.empty
        and str(before_row.iloc[0]["report_type"]) == "5"
        and str(before_row.iloc[0]["update_flag"]) == "0"
        and str(after_row.iloc[0]["report_type"]) == "1"
        and str(after_row.iloc[0]["update_flag"]) == "1"
    )
    return SentinelResult("S5", "PASS" if passed else "FAIL", {"period": period})


def s6_suspensions(aligned_market: pd.DataFrame, suspend_d: pd.DataFrame) -> SentinelResult:
    suspended = suspend_d.loc[suspend_d["suspend_type"].eq("S"), ["ts_code", "trade_date"]].drop_duplicates()
    checked = suspended.merge(aligned_market, on=["ts_code", "trade_date"], how="left")
    fields = [field for field in ("open", "high", "low", "close", "volume") if field in checked]
    bad = checked.loc[checked[fields].notna().any(axis=1)] if fields else checked
    return SentinelResult(
        "S6", "PASS" if not fields or bad.empty else "FAIL",
        {"suspension_days": len(checked), "bad_rows": len(bad)},
        bad.loc[:, ["ts_code", "trade_date"]].head(100).to_dict("records"),
    )


def s7_price_volume_logic(market: pd.DataFrame) -> SentinelResult:
    numeric = market.loc[:, ["open", "high", "low", "close", "volume"]].apply(pd.to_numeric, errors="coerce")
    bad_mask = (
        numeric["high"].lt(numeric["low"])
        | numeric["low"].lt(0)
        | numeric["high"].lt(numeric[["open", "close"]].max(axis=1))
        | numeric["low"].gt(numeric[["open", "close"]].min(axis=1))
        | numeric["volume"].lt(0)
    )
    bad = market.loc[bad_mask]
    return SentinelResult(
        "S7", "PASS" if bad.empty else "FAIL", {"bad_rows": len(bad)},
        bad.loc[:, ["ts_code", "trade_date"]].head(100).to_dict("records"),
    )


def s8_cross_source(tushare_daily: pd.DataFrame, akshare_daily: pd.DataFrame, tolerance: float = 0.01) -> SentinelResult:
    left = tushare_daily.loc[:, ["ts_code", "trade_date", "close", "vol"]]
    right = akshare_daily.loc[:, ["ts_code", "trade_date", "close", "vol"]]
    joined = left.merge(right, on=["ts_code", "trade_date"], suffixes=("_ts", "_ak"))
    if joined.empty:
        return SentinelResult("S8", "FAIL", {"reason": "no overlapping AKShare observations"})
    close_diff = (joined["close_ts"] / joined["close_ak"] - 1).abs()
    volume_diff = (joined["vol_ts"] / joined["vol_ak"] - 1).abs()
    bad = joined.loc[close_diff.gt(tolerance) | volume_diff.gt(tolerance)]
    return SentinelResult(
        "S8", "PASS" if bad.empty else "FAIL",
        {"overlap_rows": len(joined), "bad_rows": len(bad), "tolerance": tolerance},
        bad.loc[:, ["ts_code", "trade_date"]].head(100).to_dict("records"),
    )


def s9_st_status(namechange: pd.DataFrame, observations: pd.DataFrame) -> SentinelResult:
    status = st_status_on(namechange, observations)
    historical_st = set(namechange.loc[namechange["name"].astype(str).str.upper().str.contains("ST"), "ts_code"])
    removed = status.loc[status["ts_code"].isin(historical_st) & ~status["is_st"]]
    falsely_st = status.loc[status["effective_name"].astype("string").str.endswith("退", na=False) & status["is_st"]]
    passed = not removed.empty and falsely_st.empty
    return SentinelResult(
        "S9", "PASS" if passed else "FAIL",
        {"removed_st_samples": len(removed), "delisting_false_st": len(falsely_st)},
        falsely_st.head(100).to_dict("records"),
    )


def s10_git_consistency(*, environment: str, expected_commit: str | None = None) -> SentinelResult:
    expected = expected_commit or os.getenv("SHAIWEI_EXPECTED_COMMIT")
    if not expected:
        status: Status = "FAIL" if environment == "prod" else "NOT_APPLICABLE"
        return SentinelResult("S10", status, {"reason": "expected commit not configured", "environment": environment})
    actual = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    return SentinelResult("S10", "PASS" if actual == expected else "FAIL", {"expected": expected, "actual": actual})
