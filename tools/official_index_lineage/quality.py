"""Pure provider quality checks for official-index data gates."""

from __future__ import annotations

import pandas as pd


def open_dates(calendar: pd.DataFrame, start: str, end: str) -> list[str]:
    selected = calendar.loc[
        calendar["exchange"].astype(str).eq("SSE")
        & pd.to_numeric(calendar["is_open"], errors="coerce").eq(1)
    ].copy()
    dates = selected["cal_date"].astype(str)
    return sorted(set(dates.loc[dates.between(start, end)]))


def months(start: str, end: str) -> list[str]:
    return pd.period_range(start, end, freq="M").astype(str).tolist()


def daily_quality(daily: pd.DataFrame, expected_dates: list[str]) -> dict[str, object]:
    observed = set(daily["trade_date"].astype(str))
    numeric_columns = (
        "open", "high", "low", "close", "pre_close", "change", "pct_chg", "vol", "amount"
    )
    numeric = {column: pd.to_numeric(daily[column], errors="coerce") for column in numeric_columns}
    missing_numeric = int(pd.DataFrame(numeric).isna().any(axis=1).sum())
    invalid = int(
        (
            numeric["high"].lt(numeric["low"])
            | numeric["high"].lt(numeric["open"])
            | numeric["high"].lt(numeric["close"])
            | numeric["low"].gt(numeric["open"])
            | numeric["low"].gt(numeric["close"])
            | numeric["vol"].lt(0)
            | numeric["amount"].lt(0)
        ).sum()
    ) + missing_numeric
    recomputed = (numeric["close"] / numeric["pre_close"] - 1.0) * 100.0
    pct_mismatch = int(
        (numeric["pre_close"].gt(0) & recomputed.sub(numeric["pct_chg"]).abs().gt(0.02)).sum()
    )
    missing_dates = sorted(set(expected_dates) - observed)
    extra_dates = sorted(observed - set(expected_dates))
    return {
        "expected_trade_date_count": len(expected_dates),
        "observed_trade_date_count": len(observed),
        "missing_trade_dates": missing_dates,
        "non_calendar_trade_dates": extra_dates,
        "duplicate_key_count": int(daily.duplicated(["ts_code", "trade_date"]).sum()),
        "ohlc_or_nonnegative_violation_count": invalid,
        "pct_change_mismatch_count": pct_mismatch,
        "coverage": len(observed & set(expected_dates)) / len(expected_dates) if expected_dates else 0.0,
    }


def weight_quality(
    weights: pd.DataFrame,
    expected_months: list[str],
    known: set[str],
) -> tuple[dict[str, object], dict[str, tuple[str, list[str]]]]:
    weights = weights.copy()
    weights["trade_date"] = weights["trade_date"].astype(str)
    weights["month"] = (
        pd.to_datetime(weights["trade_date"], format="%Y%m%d").dt.to_period("M").astype(str)
    )
    selected = weights.loc[weights["month"].isin(expected_months)].copy()
    snapshots = (
        selected.groupby(["month", "trade_date"], sort=True)
        .agg(
            row_count=("con_code", "size"),
            constituent_count=("con_code", "nunique"),
            weight_sum=(
                "weight", lambda values: float(pd.to_numeric(values, errors="coerce").sum())
            ),
        )
        .reset_index()
    )
    counts = snapshots.groupby("month")["trade_date"].nunique().to_dict()
    missing_months = sorted(set(expected_months) - set(counts))
    multi_snapshot = sorted(month for month, count in counts.items() if count != 1)
    bad_size = snapshots.loc[
        snapshots["row_count"].ne(200) | snapshots["constituent_count"].ne(200)
    ]
    usable: dict[str, tuple[str, list[str]]] = {}
    for month in expected_months:
        month_rows = selected.loc[selected["month"].eq(month)]
        dates = sorted(set(month_rows["trade_date"]))
        if len(dates) == 1:
            rows = (
                month_rows.loc[month_rows["trade_date"].eq(dates[0]), "con_code"]
                .astype(str)
                .tolist()
            )
            if len(rows) == 200 and len(set(rows)) == 200:
                usable[month] = (dates[0], rows)
    unknown = sorted(set(selected["con_code"].dropna().astype(str)) - known)
    quality = {
        "expected_completed_month_count": len(expected_months),
        "observed_completed_month_count": len(counts),
        "missing_months": missing_months,
        "multi_snapshot_months": multi_snapshot,
        "bad_snapshot_size_count": len(bad_size),
        "duplicate_key_count": int(
            selected.duplicated(["index_code", "con_code", "trade_date"]).sum()
        ),
        "bse_row_count": int(
            selected["con_code"].astype("string").str.endswith(".BJ", na=False).sum()
        ),
        "unknown_code_count": len(unknown),
        "unknown_codes": unknown,
        "weight_sum_min": float(snapshots["weight_sum"].min()) if not snapshots.empty else None,
        "weight_sum_max": float(snapshots["weight_sum"].max()) if not snapshots.empty else None,
    }
    return quality, usable
