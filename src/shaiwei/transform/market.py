"""daily + adj_factor → 后复权/统一量纲的研究表。"""

from collections.abc import Mapping

import numpy as np
import pandas as pd

from shaiwei.transform.universe import st_status_on

PRICE_COLUMNS = ("open", "high", "low", "close", "pre_close")


def transform_market_data(daily: pd.DataFrame, adj_factor: pd.DataFrame) -> pd.DataFrame:
    daily_required = {"ts_code", "trade_date", "vol", "amount", "pct_chg", *PRICE_COLUMNS}
    factor_required = {"ts_code", "trade_date", "adj_factor"}
    if missing := daily_required - set(daily.columns):
        raise ValueError(f"daily missing fields: {sorted(missing)}")
    if missing := factor_required - set(adj_factor.columns):
        raise ValueError(f"adj_factor missing fields: {sorted(missing)}")

    duplicate_daily = daily.duplicated(["ts_code", "trade_date"], keep=False)
    duplicate_factor = adj_factor.duplicated(["ts_code", "trade_date"], keep=False)
    if duplicate_daily.any() or duplicate_factor.any():
        raise ValueError("daily/adj_factor keys must be unique")

    merged = daily.merge(
        adj_factor.loc[:, ["ts_code", "trade_date", "adj_factor"]],
        on=["ts_code", "trade_date"],
        how="left",
        validate="one_to_one",
    ).sort_values(["ts_code", "trade_date"])
    if merged["adj_factor"].isna().any():
        keys = merged.loc[merged["adj_factor"].isna(), ["ts_code", "trade_date"]].head(10)
        raise ValueError(f"missing adj_factor for daily rows: {keys.to_dict('records')}")
    if (merged["adj_factor"] <= 0).any():
        raise ValueError("adj_factor must be positive")

    first_factor = merged.groupby("ts_code")["adj_factor"].transform("first")
    multiplier = merged["adj_factor"] / first_factor
    merged["factor"] = 1.0 / multiplier
    for column in PRICE_COLUMNS:
        merged[column] = pd.to_numeric(merged[column], errors="coerce") * multiplier

    # Tushare: vol=手, amount=千元. Adjusted volume keeps amount/volume aligned with adjusted prices.
    raw_volume_shares = pd.to_numeric(merged["vol"], errors="coerce") * 100.0
    merged["volume"] = raw_volume_shares / multiplier
    merged["amount"] = pd.to_numeric(merged["amount"], errors="coerce") * 1000.0
    merged["vwap"] = merged["amount"] / merged["volume"].replace(0, np.nan)
    merged["raw_volume"] = raw_volume_shares
    if "change" in merged:
        merged["price_change"] = merged["change"]
    merged["change"] = pd.to_numeric(merged["pct_chg"], errors="coerce") / 100.0
    return merged.reset_index(drop=True)


def attach_trade_limit_flags(
    market: pd.DataFrame,
    stock_basic: pd.DataFrame,
    namechange: pd.DataFrame,
    limit_rules: Mapping[str, float],
) -> pd.DataFrame:
    """Attach point-in-time direction-specific price-limit flags for qlib.

    Qlib's single float threshold cannot represent the A-share board/date/ST
    matrix.  These two explicit fields let the exchange block buying at limit-up
    and selling at limit-down while still allowing the opposite direction.
    """
    required = {"ts_code", "trade_date", "change"}
    if missing := required - set(market.columns):
        raise ValueError(f"market missing fields: {sorted(missing)}")
    basic_required = {"ts_code", "list_date"}
    if missing := basic_required - set(stock_basic.columns):
        raise ValueError(f"stock_basic missing fields: {sorted(missing)}")
    rule_names = {
        "main",
        "chinext_before_20200824",
        "chinext_after_20200824",
        "star",
        "st",
    }
    if missing := rule_names - set(limit_rules):
        raise ValueError(f"limit_rules missing fields: {sorted(missing)}")

    result = market.copy()
    codes = result["ts_code"].astype("string")
    if codes.str.endswith(".BJ", na=False).any():
        raise ValueError("BSE securities require an explicit limit rule before inclusion")
    symbols = codes.str.split(".", n=1).str[0]
    trade_dates = result["trade_date"].astype("string")
    thresholds = pd.Series(float(limit_rules["main"]), index=result.index, dtype=float)
    chinext = codes.str.endswith(".SZ", na=False) & symbols.str.startswith(("300", "301"), na=False)
    thresholds.loc[chinext & trade_dates.lt("20200824")] = float(limit_rules["chinext_before_20200824"])
    thresholds.loc[chinext & trade_dates.ge("20200824")] = float(limit_rules["chinext_after_20200824"])
    star = codes.str.endswith(".SH", na=False) & symbols.str.startswith(("688", "689"), na=False)
    thresholds.loc[star] = float(limit_rules["star"])

    status = st_status_on(namechange, result.loc[:, ["ts_code", "trade_date"]])
    thresholds.loc[status["is_st"].to_numpy()] = float(limit_rules["st"])
    result["effective_name"] = status["effective_name"].to_numpy()
    result["is_st"] = status["is_st"].to_numpy()
    result["limit_threshold"] = thresholds

    basic = stock_basic.sort_values("list_date").drop_duplicates("ts_code", keep="last")
    list_dates = codes.map(basic.set_index("ts_code")["list_date"].astype("string"))
    first_listing_day = trade_dates.eq(list_dates)
    delisting_starts = {
        (str(row.ts_code), str(row.start_date))
        for row in namechange.loc[:, ["ts_code", "name", "start_date"]].itertuples(index=False)
        if str(row.name).strip().endswith("退")
    }
    first_delisting_day = pd.Series(
        ((str(code), str(day)) in delisting_starts for code, day in zip(codes, trade_dates, strict=True)),
        index=result.index,
    )
    exempt = first_listing_day | first_delisting_day
    change = pd.to_numeric(result["change"], errors="coerce")
    result["limit_buy"] = change.ge(thresholds) & ~exempt
    result["limit_sell"] = change.le(-thresholds) & ~exempt
    return result
