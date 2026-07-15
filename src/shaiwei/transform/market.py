"""daily + adj_factor → 后复权/统一量纲的研究表。"""

from collections.abc import Mapping

import numpy as np
import pandas as pd

from shaiwei.transform.universe import st_flags_on

PRICE_COLUMNS = ("open", "high", "low", "close", "pre_close")
ADJ_FACTOR_ABSOLUTE_PRICE_TOLERANCE = 0.011
ADJ_FACTOR_RELATIVE_PRICE_TOLERANCE = 0.001


def sanitize_adj_factors(
    daily: pd.DataFrame,
    adj_factor: pd.DataFrame,
    corporate_actions: pd.DataFrame | None = None,
    *,
    absolute_price_tolerance: float = ADJ_FACTOR_ABSOLUTE_PRICE_TOLERANCE,
    relative_price_tolerance: float = ADJ_FACTOR_RELATIVE_PRICE_TOLERANCE,
) -> pd.DataFrame:
    """Remove unsubstantiated source-factor patches from the cumulative chain.

    Tushare ``daily.pre_close`` is the ex-right previous close.  A real factor
    ratio must therefore imply that price within the exchange tick/rounding
    tolerance, unless an implemented dividend explicitly identifies the date.
    Unsupported raw ratios are retained for audit but contribute a neutral
    ratio to the cleaned cumulative factor.
    """
    daily_required = {"ts_code", "trade_date", "close", "pre_close"}
    factor_required = {"ts_code", "trade_date", "adj_factor"}
    if missing := daily_required - set(daily.columns):
        raise ValueError(f"daily missing fields: {sorted(missing)}")
    if missing := factor_required - set(adj_factor.columns):
        raise ValueError(f"adj_factor missing fields: {sorted(missing)}")
    keys = ["ts_code", "trade_date"]
    if daily.duplicated(keys, keep=False).any() or adj_factor.duplicated(keys, keep=False).any():
        raise ValueError("daily/adj_factor keys must be unique")
    frame = daily.loc[:, [*keys, "close", "pre_close"]].merge(
        adj_factor.loc[:, [*keys, "adj_factor"]],
        on=keys,
        how="left",
        validate="one_to_one",
    ).sort_values(keys)
    if frame["adj_factor"].isna().any():
        missing_keys = frame.loc[frame["adj_factor"].isna(), keys].head(10)
        raise ValueError(f"missing adj_factor for daily rows: {missing_keys.to_dict('records')}")
    for column in ("close", "pre_close", "adj_factor"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    if frame[["close", "pre_close", "adj_factor"]].isna().any().any():
        raise ValueError("factor sanitization inputs must be numeric")
    if frame["adj_factor"].le(0).any():
        raise ValueError("adj_factor must be positive")

    grouped = frame.groupby("ts_code", sort=False)
    previous_close = grouped["close"].shift()
    previous_factor = grouped["adj_factor"].shift()
    raw_ratio = frame["adj_factor"] / previous_factor
    implied_pre_close = previous_close / raw_ratio
    price_supported = np.isclose(
        implied_pre_close,
        frame["pre_close"],
        atol=absolute_price_tolerance,
        rtol=relative_price_tolerance,
        equal_nan=False,
    )
    first_observation = previous_factor.isna()

    event_supported = pd.Series(False, index=frame.index, dtype=bool)
    if corporate_actions is not None:
        required = {"ts_code", "ex_date", "div_proc"}
        if missing := required - set(corporate_actions.columns):
            raise ValueError(f"corporate_actions missing fields: {sorted(missing)}")
        implemented = corporate_actions.loc[
            corporate_actions["div_proc"].astype("string").str.contains("实施", na=False)
            & corporate_actions["ex_date"].notna(),
            ["ts_code", "ex_date"],
        ].drop_duplicates()
        event_keys = pd.MultiIndex.from_frame(
            implemented.rename(columns={"ex_date": "trade_date"}).astype("string")
        )
        frame_keys = pd.MultiIndex.from_frame(frame.loc[:, keys].astype("string"))
        event_supported = pd.Series(frame_keys.isin(event_keys), index=frame.index)

    supported = first_observation | price_supported | event_supported
    corrected = raw_ratio.notna() & ~supported
    effective_ratio = raw_ratio.mask(corrected, 1.0).fillna(1.0)
    effective_multiplier = effective_ratio.groupby(frame["ts_code"], sort=False).cumprod()
    first_factor = frame.groupby("ts_code", sort=False)["adj_factor"].transform("first")
    frame["raw_adj_factor"] = frame["adj_factor"]
    frame["adj_factor"] = first_factor * effective_multiplier
    frame["factor_corrected"] = corrected
    frame["factor_change_supported"] = supported
    return frame.loc[
        :, [*keys, "adj_factor", "raw_adj_factor", "factor_corrected", "factor_change_supported"]
    ].reset_index(drop=True)


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

    factor_columns = ["ts_code", "trade_date", "adj_factor"]
    factor_columns.extend(
        column
        for column in ("raw_adj_factor", "factor_corrected", "factor_change_supported")
        if column in adj_factor.columns
    )
    merged = daily.merge(
        adj_factor.loc[:, factor_columns],
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
    *,
    copy: bool = True,
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

    result = market.copy() if copy else market
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

    st_flags = st_flags_on(namechange, result.loc[:, ["ts_code", "trade_date"]])
    thresholds.loc[st_flags.to_numpy()] = float(limit_rules["st"])

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
