"""Source normalization and structural data-quality gates for M3-0."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from tools.m3_star_custom_pit.contract import GateFailure


def dates(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series.astype("string"), format="%Y%m%d", errors="coerce")


def date_keys(series: pd.Series) -> pd.Series:
    return dates(series).dt.strftime("%Y%m%d").astype("string")


def normalize_calendar(frame: pd.DataFrame, protocol: dict[str, Any]) -> list[str]:
    required = {"exchange", "cal_date", "is_open"}
    if missing := required - set(frame.columns):
        raise GateFailure(f"trade_cal missing fields: {sorted(missing)}")
    calendar = frame.loc[
        frame["exchange"].astype("string").eq(protocol["formation"]["calendar_exchange"])
    ].copy()
    calendar["cal_date"] = date_keys(calendar["cal_date"])
    duplicate_count = int(calendar.duplicated("cal_date", keep=False).sum())
    if duplicate_count > int(protocol["sources"]["duplicate_trade_calendar_date_maximum"]):
        raise GateFailure(f"trade_cal duplicate dates exceed maximum: {duplicate_count}")
    opened = calendar.loc[pd.to_numeric(calendar["is_open"], errors="coerce").eq(1), "cal_date"]
    result = sorted(str(value) for value in opened.dropna().unique())
    expected_start = str(protocol["identity"]["board_launch_date"]).replace("-", "")
    expected_end = str(protocol["identity"]["source_cutoff_date"]).replace("-", "")
    if not result or result[0] > expected_start or result[-1] != expected_end:
        raise GateFailure("trade_cal does not cover the frozen STAR interval through cutoff")
    return result


def normalize_stock(frame: pd.DataFrame) -> pd.DataFrame:
    stock = frame.loc[:, ["ts_code", "list_date", "delist_date"]].copy()
    stock["ts_code"] = stock["ts_code"].astype("string")
    stock["_list"] = dates(stock["list_date"])
    stock["_delist"] = dates(stock["delist_date"])
    if stock["_list"].isna().any():
        raise GateFailure("STAR stock_basic contains invalid list_date")
    return stock.sort_values("ts_code").reset_index(drop=True)


def normalize_market(
    daily: pd.DataFrame,
    basic: pd.DataFrame,
    protocol: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    if missing := {"ts_code", "trade_date", "amount"} - set(daily.columns):
        raise GateFailure(f"daily missing fields: {sorted(missing)}")
    if missing := {"ts_code", "trade_date", "total_mv"} - set(basic.columns):
        raise GateFailure(f"daily_basic missing fields: {sorted(missing)}")
    market = daily.loc[:, ["ts_code", "trade_date", "amount"]].copy()
    size = basic.loc[:, ["ts_code", "trade_date", "total_mv"]].copy()
    for frame in (market, size):
        frame["ts_code"] = frame["ts_code"].astype("string")
        frame["trade_date"] = date_keys(frame["trade_date"])
    duplicate_daily = int(market.duplicated(["ts_code", "trade_date"], keep=False).sum())
    duplicate_basic = int(size.duplicated(["ts_code", "trade_date"], keep=False).sum())
    sources = protocol["sources"]
    if duplicate_daily > int(sources["duplicate_daily_key_maximum"]):
        raise GateFailure(f"daily duplicate keys exceed maximum: {duplicate_daily}")
    if duplicate_basic > int(sources["duplicate_daily_basic_key_maximum"]):
        raise GateFailure(f"daily_basic duplicate keys exceed maximum: {duplicate_basic}")
    market["amount_rmb"] = (
        pd.to_numeric(market.pop("amount"), errors="coerce")
        * float(sources["daily_amount_tushare_unit_rmb"])
    )
    size["total_mv_rmb"] = (
        pd.to_numeric(size.pop("total_mv"), errors="coerce")
        * float(sources["total_mv_tushare_unit_rmb"])
    )
    positive_bars = market.loc[
        np.isfinite(market["amount_rmb"]) & market["amount_rmb"].gt(0),
        ["ts_code", "trade_date"],
    ]
    positive_sizes = size.loc[
        np.isfinite(size["total_mv_rmb"]) & size["total_mv_rmb"].gt(0),
        ["ts_code", "trade_date"],
    ].drop_duplicates()
    covered = positive_bars.merge(
        positive_sizes,
        on=["ts_code", "trade_date"],
        how="left",
        indicator=True,
    )
    coverage = float(covered["_merge"].eq("both").mean()) if len(covered) else 0.0
    if coverage < float(sources["positive_bar_daily_basic_coverage_minimum"]):
        raise GateFailure(f"positive bar daily_basic coverage failed: {coverage:.8f}")
    bse_rows = int(
        market["ts_code"].str.endswith(sources["bse_suffix_forbidden"], na=False).sum()
        + size["ts_code"].str.endswith(sources["bse_suffix_forbidden"], na=False).sum()
    )
    if bse_rows:
        raise GateFailure("M3 source frames contain forbidden .BJ rows")
    return market, size, {
        "daily_row_count": int(len(market)),
        "daily_basic_row_count": int(len(size)),
        "positive_bar_count": int(len(positive_bars)),
        "positive_bar_daily_basic_coverage": coverage,
        "duplicate_daily_key_count": duplicate_daily,
        "duplicate_daily_basic_key_count": duplicate_basic,
        "bse_row_count": bse_rows,
    }
