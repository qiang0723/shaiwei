"""Next-open paper execution using immutable signals and real Tushare opens."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from shaiwei.config import Settings
from shaiwei.ledger import sha256_file
from shaiwei.shadow.manifest import verify_signal_manifest
from shaiwei.transform.universe import st_flags_on


class ShadowReconciliationError(RuntimeError):
    pass


@dataclass(frozen=True)
class ReconciliationResult:
    signal_trade_date: str
    execution_trade_date: str
    signal_sha256: str
    artifact_path: Path
    artifact_sha256: str
    order_count: int
    trade_count: int
    executable_count: int
    turnover: float
    mean_abs_open_deviation: float
    estimated_cost: float


def tushare_code(instrument: str) -> str:
    value = instrument.upper()
    if value.startswith("SH") and len(value) == 8:
        return f"{value[2:]}.SH"
    if value.startswith("SZ") and len(value) == 8:
        return f"{value[2:]}.SZ"
    raise ShadowReconciliationError(f"unsupported qlib instrument: {instrument}")


def next_open_date(trade_cal: pd.DataFrame, signal_date: str) -> str | None:
    required = {"cal_date", "is_open"}
    if missing := required - set(trade_cal.columns):
        raise ShadowReconciliationError(f"trade calendar missing fields: {sorted(missing)}")
    future = sorted(
        day
        for day in trade_cal.loc[
            trade_cal["is_open"].astype(str).eq("1"), "cal_date"
        ].astype(str).unique()
        if day > signal_date
    )
    return future[0] if future else None


def _target_weights(document: dict[str, object]) -> dict[str, float]:
    orders = document.get("orders")
    if not isinstance(orders, list):
        raise ShadowReconciliationError("signal orders must be a list")
    weights: dict[str, float] = {}
    for order in orders:
        if not isinstance(order, dict):
            raise ShadowReconciliationError("signal order must be an object")
        code = tushare_code(str(order["instrument"]))
        if code.endswith(".BJ"):
            raise ShadowReconciliationError("BSE instrument is forbidden in shadow signals")
        if code in weights:
            raise ShadowReconciliationError(f"duplicate signal instrument: {code}")
        weights[code] = float(order["target_weight"])
    if not np.isclose(sum(weights.values()), 1.0, atol=1e-9):
        raise ShadowReconciliationError("signal target weights must sum to one")
    return weights


def _limit_thresholds(
    observations: pd.DataFrame,
    stock_basic: pd.DataFrame,
    namechange: pd.DataFrame,
    settings: Settings,
) -> pd.Series:
    codes = observations["ts_code"].astype("string")
    symbols = codes.str.split(".", n=1).str[0]
    dates = observations["trade_date"].astype("string")
    rules = settings.limit_rules
    thresholds = pd.Series(rules.main, index=observations.index, dtype=float)
    chinext = codes.str.endswith(".SZ", na=False) & symbols.str.startswith(("300", "301"), na=False)
    thresholds.loc[chinext & dates.lt("20200824")] = rules.chinext_before_20200824
    thresholds.loc[chinext & dates.ge("20200824")] = rules.chinext_after_20200824
    star = codes.str.endswith(".SH", na=False) & symbols.str.startswith(("688", "689"), na=False)
    thresholds.loc[star] = rules.star
    st = st_flags_on(namechange, observations.loc[:, ["ts_code", "trade_date"]])
    thresholds.loc[st.to_numpy()] = rules.st

    basic = stock_basic.sort_values("list_date").drop_duplicates("ts_code", keep="last")
    list_dates = codes.map(basic.set_index("ts_code")["list_date"].astype("string"))
    first_listing = dates.eq(list_dates)
    delisting_starts = {
        (str(row.ts_code), str(row.start_date))
        for row in namechange.loc[:, ["ts_code", "name", "start_date"]].itertuples(index=False)
        if str(row.name).strip().endswith("退")
    }
    first_delisting = pd.Series(
        ((str(code), str(day)) in delisting_starts for code, day in zip(codes, dates, strict=True)),
        index=observations.index,
    )
    return thresholds.mask(first_listing | first_delisting, np.inf)


def _paper_execution(
    *,
    current_weights: dict[str, float],
    previous_weights: dict[str, float],
    signal_daily: pd.DataFrame,
    execution_daily: pd.DataFrame,
    stock_basic: pd.DataFrame,
    namechange: pd.DataFrame,
    settings: Settings,
) -> tuple[pd.DataFrame, float, float]:
    codes = sorted(set(current_weights) | set(previous_weights))
    trades = pd.DataFrame(
        {
            "ts_code": codes,
            "previous_weight": [previous_weights.get(code, 0.0) for code in codes],
            "target_weight": [current_weights.get(code, 0.0) for code in codes],
        }
    )
    trades["delta_weight"] = trades["target_weight"] - trades["previous_weight"]
    signal_close = signal_daily.loc[:, ["ts_code", "close"]].rename(columns={"close": "reference_close"})
    execution = execution_daily.loc[:, ["ts_code", "trade_date", "open", "pre_close", "vol"]].copy()
    for column in ("open", "pre_close", "vol"):
        execution[column] = pd.to_numeric(execution[column], errors="coerce")
    execution = execution.merge(
        _limit_thresholds(execution, stock_basic, namechange, settings).rename("limit_threshold"),
        left_index=True,
        right_index=True,
        validate="one_to_one",
    )
    trades = trades.merge(signal_close, on="ts_code", how="left", validate="one_to_one")
    trades = trades.merge(execution, on="ts_code", how="left", validate="one_to_one")
    opening_change = trades["open"] / trades["pre_close"] - 1.0
    tolerance = settings.limit_rules.price_tick_tolerance / trades["pre_close"].replace(0, np.nan)
    trades["at_upper_limit"] = opening_change.ge(trades["limit_threshold"] - tolerance)
    trades["at_lower_limit"] = opening_change.le(-trades["limit_threshold"] + tolerance)
    has_bar = (
        trades["open"].notna()
        & trades["pre_close"].gt(0)
        & trades["open"].gt(0)
        & trades["vol"].gt(0)
    )
    buy = trades["delta_weight"].gt(0)
    sell = trades["delta_weight"].lt(0)
    trades["executable"] = has_bar & ~(
        (buy & trades["at_upper_limit"]) | (sell & trades["at_lower_limit"])
    )
    trades.loc[~(buy | sell), "executable"] = True
    trades["open_deviation"] = trades["open"] / pd.to_numeric(
        trades["reference_close"], errors="coerce"
    ) - 1.0
    trades["reconcile_status"] = "OK"
    trades.loc[~has_bar, "reconcile_status"] = "MISSING_PRICE"
    trades.loc[buy & trades["at_upper_limit"], "reconcile_status"] = "BUY_LIMIT_UP"
    trades.loc[sell & trades["at_lower_limit"], "reconcile_status"] = "SELL_LIMIT_DOWN"
    trades.loc[~(buy | sell), "reconcile_status"] = "NO_TRADE"

    previous_cash = max(0.0, 1.0 - sum(previous_weights.values()))
    current_cash = max(0.0, 1.0 - sum(current_weights.values()))
    turnover = 0.5 * (
        float(trades["delta_weight"].abs().sum()) + abs(current_cash - previous_cash)
    )
    account = settings.baseline.account
    executable_trades = trades.loc[(buy | sell) & trades["executable"]].copy()
    rates = np.where(
        executable_trades["delta_weight"].gt(0),
        settings.backtest.open_cost,
        settings.backtest.close_cost,
    )
    notional = executable_trades["delta_weight"].abs().to_numpy() * account
    estimated_cost = float(np.maximum(notional * rates, settings.backtest.min_cost).sum() / account)
    return trades, turnover, estimated_cost


def reconcile_forward_signal(
    settings: Settings,
    *,
    manifest_path: Path,
    execution_trade_date: str,
    signal_daily: pd.DataFrame,
    execution_daily: pd.DataFrame,
    stock_basic: pd.DataFrame,
    namechange: pd.DataFrame,
    previous_manifest_path: Path | None = None,
    output_root: Path | None = None,
) -> ReconciliationResult:
    signal_hash = verify_signal_manifest(manifest_path)
    document = json.loads(manifest_path.read_text(encoding="utf-8"))
    signal_date = str(document["signal_date"]).replace("-", "")
    current_weights = _target_weights(document)
    previous_weights: dict[str, float] = {}
    if previous_manifest_path is not None:
        verify_signal_manifest(previous_manifest_path)
        previous_weights = _target_weights(json.loads(previous_manifest_path.read_text(encoding="utf-8")))
    trades, turnover, estimated_cost = _paper_execution(
        current_weights=current_weights,
        previous_weights=previous_weights,
        signal_daily=signal_daily,
        execution_daily=execution_daily,
        stock_basic=stock_basic,
        namechange=namechange,
        settings=settings,
    )
    trade_rows = trades.loc[trades["delta_weight"].ne(0)]
    deviations = trades.loc[trades["target_weight"].gt(0), "open_deviation"].dropna().abs()
    mean_abs_deviation = float(deviations.mean()) if not deviations.empty else 0.0
    output_root = output_root or settings.runtime.data_root / "shadow"
    artifact = output_root / "reconciliations" / (
        f"{signal_date}-{execution_trade_date}-{signal_hash[:12]}.json"
    )
    summary = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "signal_trade_date": signal_date,
        "execution_trade_date": execution_trade_date,
        "signal_sha256": signal_hash,
        "order_count": len(current_weights),
        "trade_count": len(trade_rows),
        "executable_count": int(trade_rows["executable"].sum()),
        "turnover": turnover,
        "mean_abs_open_deviation": mean_abs_deviation,
        "estimated_cost": estimated_cost,
        "open_deviation_definition": "official_next_open / signal_day_close - 1",
        "rows": json.loads(trades.replace({np.nan: None}).to_json(orient="records")),
    }
    artifact.parent.mkdir(parents=True, exist_ok=True)
    if artifact.is_file():
        existing = json.loads(artifact.read_text(encoding="utf-8"))
        for key in ("signal_trade_date", "execution_trade_date", "signal_sha256"):
            if existing.get(key) != summary[key]:
                raise ShadowReconciliationError(f"existing reconciliation differs on {key}")
        summary = existing
    else:
        artifact.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8",
        )
    artifact_hash = sha256_file(artifact)
    return ReconciliationResult(
        signal_trade_date=signal_date,
        execution_trade_date=execution_trade_date,
        signal_sha256=signal_hash,
        artifact_path=artifact,
        artifact_sha256=artifact_hash,
        order_count=int(summary["order_count"]),
        trade_count=int(summary["trade_count"]),
        executable_count=int(summary["executable_count"]),
        turnover=float(summary["turnover"]),
        mean_abs_open_deviation=float(summary["mean_abs_open_deviation"]),
        estimated_cost=float(summary["estimated_cost"]),
    )
