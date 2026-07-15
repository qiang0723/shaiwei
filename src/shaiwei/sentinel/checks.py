"""S1-S10 的纯函数实现。FAIL 必须携带可复核指标。"""

import os
import subprocess
from dataclasses import asdict, dataclass, field
from typing import Literal

import duckdb
import numpy as np
import pandas as pd

from shaiwei.transform.market import (
    ADJ_FACTOR_ABSOLUTE_PRICE_TOLERANCE,
    ADJ_FACTOR_RELATIVE_PRICE_TOLERANCE,
    transform_market_data,
)
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
    include_bse: bool = True,
) -> SentinelResult:
    open_days = set(trade_cal.loc[trade_cal["is_open"].astype(str).eq("1"), "cal_date"].astype(str))
    open_days = {day for day in open_days if start <= day <= end}
    suspended = suspend_d.loc[suspend_d["suspend_type"].eq("S")].groupby("ts_code")["trade_date"].agg(set)
    bars = daily.groupby("ts_code")["trade_date"].agg(set)
    anomalies = []
    securities = stock_basic.drop_duplicates("ts_code")
    excluded_bse_count = 0
    if not include_bse:
        bse = securities["ts_code"].astype("string").str.endswith(".BJ", na=False)
        excluded_bse_count = int(bse.sum())
        securities = securities.loc[~bse]
    for security in securities.itertuples(index=False):
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
        {
            "security_count": int(securities["ts_code"].nunique()),
            "excluded_bse_count": excluded_bse_count,
            "anomaly_count": len(anomalies),
        },
        anomalies[:1000],
    )


def s2_dual_calculation(
    daily: pd.DataFrame,
    adj_factor: pd.DataFrame,
    tolerance: float = 1e-12,
    max_securities: int = 32,
) -> SentinelResult:
    securities = np.array(sorted(daily["ts_code"].dropna().astype(str).unique()))
    sample_size = min(len(securities), max_securities)
    positions = np.linspace(0, len(securities) - 1, sample_size, dtype=int) if sample_size else np.array([], dtype=int)
    selected = set(securities[positions])
    sample_daily = daily.loc[daily["ts_code"].astype(str).isin(selected)]
    sample_adj = adj_factor.loc[adj_factor["ts_code"].astype(str).isin(selected)]
    pandas_result = transform_market_data(sample_daily, sample_adj)
    connection = duckdb.connect(":memory:")
    connection.register("daily", sample_daily)
    connection.register("adj", sample_adj)
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
        {
            "row_count": len(comparison),
            "sample_security_count": len(selected),
            "total_security_count": len(securities),
            "tolerance": tolerance,
            "max_abs_error": errors,
        },
    )


def s3_reverse_adjustment(
    transformed: pd.DataFrame,
    daily: pd.DataFrame,
    tolerance: float = 1e-4,
    sample_codes: list[str] | None = None,
) -> SentinelResult:
    missing_samples = sorted(set(sample_codes or []) - set(daily["ts_code"].astype(str)))
    if sample_codes:
        transformed = transformed.loc[transformed["ts_code"].isin(sample_codes)]
        daily = daily.loc[daily["ts_code"].isin(sample_codes)]
    source = daily.loc[:, ["ts_code", "trade_date", "close"]].rename(columns={"close": "raw_close"})
    joined = transformed.merge(source, on=["ts_code", "trade_date"], validate="one_to_one")
    reversed_close = joined["close"] * joined["factor"]
    relative_error = ((reversed_close - joined["raw_close"]).abs() / joined["raw_close"].abs()).replace(
        [np.inf, -np.inf], np.nan
    )
    maximum = float(relative_error.max()) if relative_error.notna().any() else 0.0
    ordered = transformed.sort_values(["ts_code", "trade_date"])
    implied_return = pd.to_numeric(ordered["close"], errors="coerce").groupby(
        ordered["ts_code"]
    ).pct_change(fill_method=None)
    return_error = (implied_return - pd.to_numeric(ordered["pct_chg"], errors="coerce") / 100.0).abs()
    maximum_return_error = float(return_error.max()) if return_error.notna().any() else 0.0
    passed = not missing_samples and not joined.empty and maximum < tolerance and maximum_return_error < tolerance
    return SentinelResult(
        "S3",
        "PASS" if passed else "FAIL",
        {
            "sample_codes": sample_codes or sorted(daily["ts_code"].astype(str).unique()),
            "missing_sample_codes": missing_samples,
            "checked_rows": len(joined),
            "max_relative_error": maximum,
            "max_adjusted_return_error": maximum_return_error,
        },
    )


def s4_units(transformed: pd.DataFrame, price_band_tolerance: float = 0.02) -> SentinelResult:
    required = {"ts_code", "trade_date", "low", "high", "amount", "volume", "vwap"}
    if missing := required - set(transformed.columns):
        raise ValueError(f"transformed market missing fields: {sorted(missing)}")
    calculated = transformed["amount"] / transformed["volume"].replace(0, np.nan)
    ratio = (transformed["vwap"] / calculated).replace([np.inf, -np.inf], np.nan).dropna()
    identity_outliers = ratio.loc[~ratio.between(0.5, 2.0)]
    low = pd.to_numeric(transformed["low"], errors="coerce")
    high = pd.to_numeric(transformed["high"], errors="coerce")
    vwap = pd.to_numeric(transformed["vwap"], errors="coerce")
    comparable = low.notna() & high.notna() & vwap.notna() & transformed["volume"].gt(0)
    outside_band = comparable & (
        vwap.lt(low * (1.0 - price_band_tolerance)) | vwap.gt(high * (1.0 + price_band_tolerance))
    )
    anomaly_index = identity_outliers.index.union(transformed.index[outside_band])
    passed = anomaly_index.empty
    return SentinelResult(
        "S4",
        "PASS" if passed and not ratio.empty and comparable.any() else "FAIL",
        {
            "checked_rows": len(ratio),
            "price_band_checked_rows": int(comparable.sum()),
            "identity_ratio_min": float(ratio.min()) if not ratio.empty else None,
            "identity_ratio_max": float(ratio.max()) if not ratio.empty else None,
            "price_band_tolerance": price_band_tolerance,
            "outside_price_band_rows": int(outside_band.sum()),
        },
        transformed.loc[anomaly_index, ["ts_code", "trade_date"]].head(100).to_dict("records"),
    )


def s5_financial_pit(
    statements: pd.DataFrame,
    trade_cal: pd.DataFrame,
    statement_tables: dict[str, pd.DataFrame] | None = None,
) -> SentinelResult:
    tables = {"income": statements, **(statement_tables or {})}
    table_metrics = {}
    structural_failures = []
    open_days_text = trade_cal.loc[trade_cal["is_open"].astype(str).eq("1"), "cal_date"].astype(str)
    latest_open_day = open_days_text.max() if not open_days_text.empty else None
    for name, table in tables.items():
        required = {"ts_code", "f_ann_date", "end_date", "report_type", "update_flag"}
        missing = required - set(table.columns)
        if missing or table.empty or latest_open_day is None:
            structural_failures.append({"table": name, "missing_fields": sorted(missing), "row_count": len(table)})
            continue
        snapshot = financial_pit_snapshot(table, trade_cal, latest_open_day)
        duplicate_period_ratio = float(table.duplicated(["ts_code", "end_date"], keep=False).mean())
        table_metrics[name] = {
            "source_rows": len(table),
            "snapshot_rows": len(snapshot),
            "duplicate_period_ratio": duplicate_period_ratio,
        }
        if snapshot.empty:
            structural_failures.append({"table": name, "reason": "latest PIT snapshot is empty"})
    sample = statements.loc[statements["ts_code"].eq("688502.SH")].copy()
    sample["_f_ann"] = pd.to_datetime(sample["f_ann_date"], format="%Y%m%d", errors="coerce")
    old = sample.loc[
        sample["report_type"].astype(str).eq("5") & sample["update_flag"].astype(str).eq("0")
    ]
    new = sample.loc[
        sample["report_type"].astype(str).eq("1") & sample["update_flag"].astype(str).eq("1")
    ]
    pairs = old.merge(new, on=["ts_code", "end_date"], suffixes=("_old", "_new"))
    pairs = pairs.loc[
        pairs["end_date"].astype(str).eq("20221231")
        & pairs["_f_ann_old"].lt(pairs["_f_ann_new"])
    ]
    if pairs.empty:
        return SentinelResult(
            "S5",
            "FAIL",
            {"reason": "688502.SH 2022 restatement pair not found", "tables": table_metrics},
            structural_failures,
        )
    pair = pairs.sort_values("_f_ann_new").iloc[0]
    open_days = pd.to_datetime(
        trade_cal.loc[trade_cal["is_open"].astype(str).eq("1"), "cal_date"], format="%Y%m%d", errors="coerce"
    ).dropna().sort_values()
    between = open_days.loc[open_days.gt(pair["_f_ann_old"]) & open_days.lt(pair["_f_ann_new"])]
    after = open_days.loc[open_days.gt(pair["_f_ann_new"])]
    if between.empty or after.empty:
        return SentinelResult(
            "S5",
            "FAIL",
            {"reason": "calendar cannot bracket 688502.SH correction", "tables": table_metrics},
            structural_failures,
        )
    before_snapshot = financial_pit_snapshot(sample, trade_cal, between.iloc[-1].strftime("%Y-%m-%d"))
    after_snapshot = financial_pit_snapshot(sample, trade_cal, after.iloc[0].strftime("%Y-%m-%d"))
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
    passed = passed and not structural_failures
    return SentinelResult(
        "S5",
        "PASS" if passed else "FAIL",
        {
            "period": period,
            "old_f_ann_date": pair["f_ann_date_old"],
            "new_f_ann_date": pair["f_ann_date_new"],
            "tables": table_metrics,
        },
        structural_failures,
    )


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


def s7_price_volume_logic(
    market: pd.DataFrame,
    corporate_actions: pd.DataFrame | None = None,
    factor_tolerance: float = 1e-12,
) -> SentinelResult:
    numeric = market.loc[:, ["open", "high", "low", "close", "volume"]].apply(pd.to_numeric, errors="coerce")
    bad_mask = (
        numeric["high"].lt(numeric["low"])
        | numeric["low"].lt(0)
        | numeric["high"].lt(numeric[["open", "close"]].max(axis=1))
        | numeric["low"].gt(numeric[["open", "close"]].min(axis=1))
        | numeric["volume"].lt(0)
    )
    if {"limit_buy", "limit_sell"}.issubset(market.columns):
        contradictory_limit = market["limit_buy"].astype(bool) & market["limit_sell"].astype(bool)
        bad_mask |= contradictory_limit
    else:
        contradictory_limit = pd.Series(False, index=market.index)
    bad = market.loc[bad_mask]
    unmatched_factor_jumps = pd.DataFrame(columns=["ts_code", "trade_date"])
    factor_jump_count = 0
    corrected_factor_rows = int(
        market.get("factor_corrected", pd.Series(False, index=market.index)).fillna(False).astype(bool).sum()
    )
    correction_columns = [
        column
        for column in ("ts_code", "trade_date", "raw_adj_factor", "adj_factor")
        if column in market.columns
    ]
    corrected_factor_sample = (
        market.loc[market["factor_corrected"].fillna(False).astype(bool), correction_columns]
        .head(20)
        .to_dict("records")
        if "factor_corrected" in market.columns
        else []
    )
    if corporate_actions is not None:
        required = {"ts_code", "ex_date", "div_proc"}
        if missing := required - set(corporate_actions.columns):
            raise ValueError(f"corporate_actions missing fields: {sorted(missing)}")
        ordered = market.sort_values(["ts_code", "trade_date"])
        factor_change = pd.to_numeric(ordered["adj_factor"], errors="coerce").groupby(
            ordered["ts_code"]
        ).pct_change(fill_method=None).abs()
        factor_jumps = ordered.loc[factor_change.gt(factor_tolerance), ["ts_code", "trade_date"]].drop_duplicates()
        factor_jump_count = len(factor_jumps)
        implemented = corporate_actions.loc[
            corporate_actions["div_proc"].astype("string").str.contains("实施", na=False)
            & corporate_actions["ex_date"].notna()
        ].copy()
        implemented["trade_date"] = implemented["ex_date"].astype("string")
        event_keys = implemented.loc[:, ["ts_code", "trade_date"]].drop_duplicates()
        unmatched_factor_jumps = factor_jumps.merge(
            event_keys.assign(_matched=True), on=["ts_code", "trade_date"], how="left"
        )
        if "factor_change_supported" in ordered.columns:
            supported_keys = ordered.loc[
                ordered["factor_change_supported"].fillna(False).astype(bool),
                ["ts_code", "trade_date"],
            ].drop_duplicates()
            unmatched_factor_jumps = unmatched_factor_jumps.merge(
                supported_keys.assign(_supported=True), on=["ts_code", "trade_date"], how="left"
            )
        else:
            unmatched_factor_jumps["_supported"] = pd.NA
        unmatched_factor_jumps = unmatched_factor_jumps.loc[
            unmatched_factor_jumps["_matched"].isna() & unmatched_factor_jumps["_supported"].isna(),
            ["ts_code", "trade_date"],
        ]
    passed = bad.empty and unmatched_factor_jumps.empty
    anomalies = bad.loc[:, ["ts_code", "trade_date"]].assign(reason="price_volume_or_limit")
    if not unmatched_factor_jumps.empty:
        anomalies = pd.concat(
            [unmatched_factor_jumps.assign(reason="adj_factor_without_implemented_dividend"), anomalies],
            ignore_index=True,
        )
    return SentinelResult(
        "S7", "PASS" if passed else "FAIL",
        {
            "bad_rows": len(bad),
            "limit_buy_days": int(market.get("limit_buy", pd.Series(False, index=market.index)).sum()),
            "limit_sell_days": int(market.get("limit_sell", pd.Series(False, index=market.index)).sum()),
            "contradictory_limit_rows": int(contradictory_limit.sum()),
            "factor_jump_rows": factor_jump_count,
            "factor_sanitizer_applied": "factor_change_supported" in market.columns,
            "factor_absolute_price_tolerance": ADJ_FACTOR_ABSOLUTE_PRICE_TOLERANCE,
            "factor_relative_price_tolerance": ADJ_FACTOR_RELATIVE_PRICE_TOLERANCE,
            "corrected_factor_rows": corrected_factor_rows,
            "corrected_factor_sample": corrected_factor_sample,
            "unmatched_factor_jump_rows": len(unmatched_factor_jumps),
        },
        anomalies.head(100).to_dict("records"),
    )


def s8_cross_source(tushare_daily: pd.DataFrame, akshare_daily: pd.DataFrame, tolerance: float = 0.01) -> SentinelResult:
    fields = ["ts_code", "trade_date", "close", "vol"]
    compare_amount = "amount" in tushare_daily.columns and "amount" in akshare_daily.columns
    if compare_amount:
        fields.append("amount")
    left = tushare_daily.loc[:, fields]
    right = akshare_daily.loc[:, fields]
    joined = left.merge(right, on=["ts_code", "trade_date"], suffixes=("_ts", "_ak"))
    if joined.empty:
        return SentinelResult("S8", "FAIL", {"reason": "no overlapping AKShare observations"})
    close_diff = (joined["close_ts"] / joined["close_ak"] - 1).abs()
    volume_diff = (joined["vol_ts"] / joined["vol_ak"] - 1).abs()
    bad_mask = close_diff.gt(tolerance) | volume_diff.gt(tolerance)
    amount_diff = pd.Series(np.nan, index=joined.index)
    if compare_amount:
        # Tushare amount is thousand yuan; AKShare stock_zh_a_hist amount is yuan.
        amount_diff = (joined["amount_ts"] * 1000.0 / joined["amount_ak"] - 1).abs()
        bad_mask |= amount_diff.gt(tolerance)
    bad = joined.loc[bad_mask]
    return SentinelResult(
        "S8", "PASS" if bad.empty else "FAIL",
        {
            "overlap_rows": len(joined),
            "bad_rows": len(bad),
            "tolerance": tolerance,
            "amount_unit_crosscheck": compare_amount,
            "max_close_relative_diff": float(close_diff.max()),
            "max_volume_relative_diff": float(volume_diff.max()),
            "max_amount_relative_diff": float(amount_diff.max()) if amount_diff.notna().any() else None,
        },
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
