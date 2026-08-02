"""Immutable M3 discovery inputs with adjusted OHLCV and PIT exposures."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch

from shaiwei.benchmark.fitness import industry_pit_exposure
from shaiwei.config import PROJECT_ROOT
from shaiwei.ledger import sha256_file
from shaiwei.research.llm_factor import D1ControlError
from shaiwei.research.m3_multi_pool_contract import M3Protocol, verify_m3_inputs
from shaiwei.research.m3_multi_pool_sources import load_m3_sources
from shaiwei.transform.market import sanitize_adj_factors, transform_market_data


FEATURES = ("open", "close", "high", "low", "volume", "vwap")


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _instrument(ts_code: str) -> str:
    symbol, separator, exchange = str(ts_code).upper().partition(".")
    if separator != "." or exchange not in {"SH", "SZ"} or len(symbol) != 6 or not symbol.isdigit():
        raise D1ControlError("M3-2 member is not an allowed A-share identity")
    return f"{exchange}{symbol}"


@dataclass(frozen=True)
class M3DiscoveryIdentity:
    snapshot_sha256: str
    source_snapshots: dict[str, str]
    source_rows: dict[str, int]
    calendar_start: str
    calendar_end: str
    panel_security_count: int
    discovery_trade_days: int
    exposure_rows: int


@dataclass
class PanelStockData:
    data: torch.Tensor
    max_backtrack_days: int
    max_future_days: int
    n_days: int
    n_stocks: int


@dataclass
class M3DiscoveryInput:
    identity: M3DiscoveryIdentity
    stock_data: PanelStockData
    instruments: tuple[str, ...]
    discovery_dates: tuple[pd.Timestamp, ...]
    labels: pd.DataFrame
    exposures: pd.DataFrame
    members: pd.DataFrame


def _calendar_window(trade_cal: pd.DataFrame, protocol: M3Protocol) -> tuple[list[str], int, int]:
    calendar = trade_cal.copy()
    if "exchange" in calendar:
        calendar = calendar.loc[calendar["exchange"].astype(str).eq("SSE")]
    open_days = sorted(
        calendar.loc[calendar["is_open"].astype(str).eq("1"), "cal_date"]
        .astype(str)
        .drop_duplicates()
    )
    data = protocol.document["data_contract"]
    start = str(data["discovery_signal_period"][0]).replace("-", "")
    signal_end = str(data["discovery_signal_period"][1]).replace("-", "")
    maturity = str(data["final_discovery_label_maturity_date"]).replace("-", "")
    start_index = open_days.index(start)
    end_index = open_days.index(signal_end)
    maturity_index = open_days.index(maturity)
    backtrack = int(data["maximum_lookback_trade_days"])
    future = int(data["horizon_trade_days"]) + 1
    if start_index < backtrack or end_index + future != maturity_index:
        raise D1ControlError("M3-2 discovery calendar or label maturity differs")
    return open_days[start_index - backtrack : maturity_index + 1], backtrack, future


def _build_panel(
    market: pd.DataFrame,
    calendar: list[str],
    codes: list[str],
    *,
    backtrack: int,
    future: int,
) -> PanelStockData:
    shape = (len(calendar), len(FEATURES), len(codes))
    values = np.full(shape, np.nan, dtype=np.float64)
    day_index = {day: index for index, day in enumerate(calendar)}
    code_index = {code: index for index, code in enumerate(codes)}
    selected = market.loc[market["trade_date"].astype(str).isin(day_index)].copy()
    for column in FEATURES:
        selected[column] = pd.to_numeric(selected[column], errors="coerce")
    rows = selected["trade_date"].astype(str).map(day_index).to_numpy(dtype=int)
    columns = selected["ts_code"].astype(str).map(code_index).to_numpy(dtype=int)
    for feature_index, feature in enumerate(FEATURES):
        values[rows, feature_index, columns] = selected[feature].to_numpy(dtype=float)
    n_days = len(calendar) - backtrack - future
    return PanelStockData(
        data=torch.from_numpy(values),
        max_backtrack_days=backtrack,
        max_future_days=future,
        n_days=n_days,
        n_stocks=len(codes),
    )


def build_m3_discovery_input(
    protocol: M3Protocol,
    *,
    project_root: Path = PROJECT_ROOT,
) -> M3DiscoveryInput:
    upstream = verify_m3_inputs(protocol, project_root=project_root)
    data_contract = protocol.document["data_contract"]
    member_path = project_root / protocol.document["upstream_contract"]["membership_path"]
    members = pd.read_parquet(
        member_path,
        columns=["trade_date", "universe_id", "ts_code"],
    )
    members["trade_date"] = members["trade_date"].astype(str)
    start, end = (str(value).replace("-", "") for value in data_contract["discovery_signal_period"])
    members = members.loc[members["trade_date"].between(start, end)].copy()
    if members.empty or members["ts_code"].astype(str).str.endswith(".BJ").any():
        raise D1ControlError("M3-2 discovery members are empty or contain .BJ")
    codes = sorted(members["ts_code"].astype(str).unique())
    frames, source_evidence = load_m3_sources(
        set(codes),
        str(data_contract["final_discovery_label_maturity_date"]).replace("-", ""),
    )
    calendar, backtrack, future = _calendar_window(frames["tushare.trade_cal"], protocol)
    exact = set(calendar)
    daily = frames["tushare.daily"].loc[
        frames["tushare.daily"]["trade_date"].astype(str).isin(exact)
    ].copy()
    daily_basic = frames["tushare.daily_basic"].loc[
        frames["tushare.daily_basic"]["trade_date"].astype(str).isin(exact)
    ].copy()
    adj_factor = frames["tushare.adj_factor"].loc[
        frames["tushare.adj_factor"]["trade_date"].astype(str).isin(exact)
    ].copy()
    keys = ["ts_code", "trade_date"]
    if any(frame.duplicated(keys).any() for frame in (daily, daily_basic, adj_factor)):
        raise D1ControlError("M3-2 market inputs contain duplicate security dates")
    corrected = sanitize_adj_factors(daily, adj_factor, frames["tushare.dividend"])
    market = transform_market_data(daily, corrected)
    if market["ts_code"].astype(str).str.endswith(".BJ").any():
        raise D1ControlError("M3-2 adjusted market contains .BJ")
    panel = _build_panel(
        market,
        calendar,
        codes,
        backtrack=backtrack,
        future=future,
    )
    if panel.n_days != upstream.discovery_trade_days:
        raise D1ControlError("M3-2 panel discovery day count differs")
    discovery_dates = tuple(pd.to_datetime(calendar[backtrack : len(calendar) - future]))
    open_values = panel.data[:, 0, :].numpy()
    labels = np.vstack(
        [
            open_values[backtrack + index + future]
            / open_values[backtrack + index + 1]
            - 1.0
            for index in range(panel.n_days)
        ]
    )
    instruments = tuple(_instrument(code) for code in codes)
    label_frame = pd.DataFrame(
        {
            "trade_date": np.repeat(discovery_dates, len(codes)),
            "instrument": np.tile(instruments, panel.n_days),
            "label": labels.reshape(-1),
        }
    )
    unique_members = members[["trade_date", "ts_code"]].drop_duplicates()
    size = daily_basic[["trade_date", "ts_code", "total_mv"]].copy()
    size["trade_date"] = size["trade_date"].astype(str)
    exposures = unique_members.merge(size, on=keys, how="left", validate="one_to_one")
    industry = industry_pit_exposure(exposures[keys], frames["tushare.index_member_all"])
    exposures["industry"] = industry["industry"].to_numpy()
    exposures["market_cap"] = pd.to_numeric(exposures["total_mv"], errors="coerce") * 10_000.0
    exposures["instrument"] = exposures["ts_code"].astype(str).map(_instrument)
    exposures["trade_date"] = pd.to_datetime(exposures["trade_date"], format="%Y%m%d")
    exposures = exposures[["trade_date", "instrument", "industry", "market_cap"]]
    if exposures.duplicated(["trade_date", "instrument"]).any():
        raise D1ControlError("M3-2 PIT exposures contain duplicate member days")
    source_snapshots = {
        api: str(evidence["selected_batch_snapshot_sha256"])
        for api, evidence in sorted(source_evidence.items())
    }
    source_rows = {
        api: int(evidence["loaded_row_count"])
        for api, evidence in sorted(source_evidence.items())
    }
    identity_payload = {
        "protocol_sha256": protocol.sha256,
        "membership_sha256": upstream.membership_sha256,
        "source_snapshots": source_snapshots,
        "calendar": [calendar[0], calendar[-1], len(calendar)],
        "panel_security_count": len(codes),
        "discovery_trade_days": panel.n_days,
        "exposure_rows": len(exposures),
        "market_transform_sha256": sha256_file(project_root / "src/shaiwei/transform/market.py"),
        "feature_order": FEATURES,
        "label": data_contract["label"],
    }
    identity = M3DiscoveryIdentity(
        snapshot_sha256=_sha256_json(identity_payload),
        source_snapshots=source_snapshots,
        source_rows=source_rows,
        calendar_start=calendar[0],
        calendar_end=calendar[-1],
        panel_security_count=len(codes),
        discovery_trade_days=panel.n_days,
        exposure_rows=len(exposures),
    )
    return M3DiscoveryInput(
        identity=identity,
        stock_data=panel,
        instruments=instruments,
        discovery_dates=discovery_dates,
        labels=label_frame,
        exposures=exposures,
        members=members,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--protocol",
        type=Path,
        default=PROJECT_ROOT / "config/m3_multi_pool_factor_research_v1.yaml",
    )
    parser.add_argument("--execution-release", type=Path, default=None)
    args = parser.parse_args(argv)
    try:
        protocol = M3Protocol.load(args.protocol)
        prepared = build_m3_discovery_input(protocol)
        release_sha256 = None
        if args.execution_release is not None:
            from shaiwei.research.m3_multi_pool_release import M3ExecutionRelease

            release = M3ExecutionRelease.load(args.execution_release, protocol)
            release.verify_input(prepared.identity)
            release_sha256 = release.sha256
    except (D1ControlError, OSError, RuntimeError, TypeError, ValueError) as error:
        print(_canonical_json({"status": "FAIL", "error_class": type(error).__name__}))
        return 2
    print(
        _canonical_json(
            {
                "status": "PASS",
                "input_snapshot_sha256": prepared.identity.snapshot_sha256,
                "execution_release_sha256": release_sha256,
                "source_snapshots": prepared.identity.source_snapshots,
                "source_rows": prepared.identity.source_rows,
                "calendar_start": prepared.identity.calendar_start,
                "calendar_end": prepared.identity.calendar_end,
                "panel_security_count": prepared.identity.panel_security_count,
                "discovery_trade_days": prepared.identity.discovery_trade_days,
                "exposure_rows": prepared.identity.exposure_rows,
                "factor_results_inspected": False,
                "provider_calls": 0,
                "api_key_read": False,
                "sealed_results_inspected": False,
                "strategy_effective": "NOT_EVALUATED",
                "production_authorization": "none",
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
