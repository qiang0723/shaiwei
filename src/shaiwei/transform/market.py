"""daily + adj_factor → 后复权/统一量纲的研究表。"""

import numpy as np
import pandas as pd

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
