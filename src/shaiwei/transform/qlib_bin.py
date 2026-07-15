"""从已校验研究表直接构建 qlib 原生 day bin；bin 是可重建缓存。"""

from collections import defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path

import numpy as np
import pandas as pd

QLIB_FIELDS = (
    "open",
    "high",
    "low",
    "close",
    "volume",
    "vwap",
    "factor",
    "change",
    "limit_buy",
    "limit_sell",
)


def qlib_code(ts_code: str) -> str:
    symbol, separator, exchange = str(ts_code).partition(".")
    if not separator or not symbol or not exchange:
        raise ValueError(f"invalid Tushare code: {ts_code!r}")
    return f"{exchange.upper()}{symbol.upper()}"


def benchmark_frame(index_daily: pd.DataFrame) -> pd.DataFrame:
    required = {"ts_code", "trade_date", "open", "high", "low", "close", "vol", "amount", "pct_chg"}
    if missing := required - set(index_daily.columns):
        raise ValueError(f"index_daily missing fields: {sorted(missing)}")
    frame = index_daily.copy()
    for column in ("open", "high", "low", "close"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame["volume"] = pd.to_numeric(frame["vol"], errors="coerce") * 100.0
    amount = pd.to_numeric(frame["amount"], errors="coerce") * 1000.0
    frame["vwap"] = amount / frame["volume"].replace(0, np.nan)
    frame["factor"] = 1.0
    frame["change"] = pd.to_numeric(frame["pct_chg"], errors="coerce") / 100.0
    frame["limit_buy"] = False
    frame["limit_sell"] = False
    return frame


def membership_intervals(index_weight: pd.DataFrame, calendar: list[str]) -> pd.DataFrame:
    required = {"con_code", "trade_date"}
    if missing := required - set(index_weight.columns):
        raise ValueError(f"index_weight missing fields: {sorted(missing)}")
    if not calendar:
        raise ValueError("calendar must not be empty")
    calendar_index = pd.Index(calendar)
    snapshots = index_weight.copy()
    snapshots["trade_date"] = snapshots["trade_date"].astype(str)
    dates = sorted(date for date in snapshots["trade_date"].unique() if date <= calendar[-1])
    spans: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for position, snapshot_date in enumerate(dates):
        start_index = int(calendar_index.searchsorted(snapshot_date, side="left"))
        next_date = dates[position + 1] if position + 1 < len(dates) else None
        end_index = (
            int(calendar_index.searchsorted(next_date, side="left")) - 1 if next_date is not None else len(calendar) - 1
        )
        if start_index > end_index or start_index >= len(calendar):
            continue
        members = snapshots.loc[snapshots["trade_date"].eq(snapshot_date), "con_code"].dropna().unique()
        for member in members:
            member_spans = spans[str(member)]
            if member_spans and member_spans[-1][1] + 1 == start_index:
                member_spans[-1] = (member_spans[-1][0], end_index)
            else:
                member_spans.append((start_index, end_index))
    rows = [
        {"instrument": qlib_code(code), "start": calendar[start], "end": calendar[end]}
        for code, ranges in spans.items()
        for start, end in ranges
    ]
    return pd.DataFrame(rows, columns=["instrument", "start", "end"]).sort_values(
        ["instrument", "start"]
    ).reset_index(drop=True)


def _write_lines(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_qlib_bin(
    output_root: Path,
    market: pd.DataFrame,
    trade_cal: pd.DataFrame,
    stock_basic: pd.DataFrame,
    index_weight: pd.DataFrame,
    index_daily: pd.DataFrame,
    instrument_indices: dict[str, str],
) -> Path:
    output_root = Path(output_root)
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"qlib output is not empty: {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)
    open_calendar = sorted(
        trade_cal.loc[trade_cal["is_open"].astype(str).eq("1"), "cal_date"].astype(str).drop_duplicates()
    )
    if not open_calendar:
        raise ValueError("trade calendar has no open dates")
    _write_lines(output_root / "calendars/day.txt", open_calendar)

    combined = pd.concat([market, benchmark_frame(index_daily)], ignore_index=True, sort=False)
    calendar_index = pd.Index(open_calendar)
    instrument_lines = []
    for ts_code, frame in combined.groupby("ts_code", sort=True):
        frame = frame.copy()
        frame["trade_date"] = frame["trade_date"].astype(str)
        frame = frame.loc[frame["trade_date"].isin(calendar_index)].sort_values("trade_date")
        if frame.empty:
            continue
        if frame["trade_date"].duplicated().any():
            raise ValueError(f"duplicate qlib dates for {ts_code}")
        first_index = int(calendar_index.get_loc(frame["trade_date"].iloc[0]))
        last_index = int(calendar_index.get_loc(frame["trade_date"].iloc[-1]))
        aligned_dates = calendar_index[first_index : last_index + 1]
        aligned = frame.set_index("trade_date").reindex(aligned_dates)
        code = qlib_code(ts_code)
        feature_dir = output_root / "features" / code.lower()
        feature_dir.mkdir(parents=True, exist_ok=True)
        for field_name in QLIB_FIELDS:
            values = pd.to_numeric(aligned[field_name], errors="coerce").to_numpy(dtype="float32")
            payload = np.concatenate([np.array([first_index], dtype="float32"), values]).astype("<f4")
            payload.tofile(feature_dir / f"{field_name}.day.bin")
        instrument_lines.append(f"{code}\t{aligned_dates[0]}\t{aligned_dates[-1]}")

    _write_lines(output_root / "instruments/all.txt", sorted(instrument_lines))
    if "index_code" not in index_weight.columns:
        raise ValueError("index_weight missing fields: ['index_code']")
    for instrument_name, index_code in instrument_indices.items():
        snapshots = index_weight.loc[index_weight["index_code"].eq(index_code)]
        if snapshots.empty:
            raise ValueError(f"index_weight has no snapshots for {instrument_name}={index_code}")
        intervals = membership_intervals(snapshots, open_calendar)
        if intervals.empty or intervals["start"].min() != open_calendar[0]:
            raise ValueError(f"{instrument_name} membership does not cover the first qlib trading day")
        _write_lines(
            output_root / f"instruments/{instrument_name}.txt",
            [f"{row.instrument}\t{row.start}\t{row.end}" for row in intervals.itertuples(index=False)],
        )
    return output_root


def main() -> int:
    from shaiwei.config import load
    from shaiwei.ingest.catalog import load_latest_api
    from shaiwei.ledger import ingest_snapshot_sha256
    from shaiwei.provenance import code_snapshot_sha256
    from shaiwei.sentinel.__main__ import main as run_sentinels
    from shaiwei.transform.market import attach_trade_limit_flags, transform_market_data

    if run_sentinels() != 0:
        raise SystemExit("sentinels failed; qlib bin build is blocked")
    settings = load()
    daily = load_latest_api("tushare.daily")
    adj_factor = load_latest_api("tushare.adj_factor")
    stock_basic = load_latest_api("tushare.stock_basic")
    namechange = load_latest_api("tushare.namechange")
    market = attach_trade_limit_flags(
        transform_market_data(daily, adj_factor),
        stock_basic,
        namechange,
        settings.limit_rules.model_dump(),
    )
    output_root = settings.runtime.data_root / "qlib_bin"
    build_qlib_bin(
        output_root,
        market,
        load_latest_api("tushare.trade_cal"),
        stock_basic,
        load_latest_api("tushare.index_weight"),
        load_latest_api("tushare.index_daily"),
        {
            settings.baseline.instrument: settings.universe.index_code,
            settings.alphagen_benchmark.instrument: settings.alphagen_benchmark.index_code,
        },
    )
    (output_root / "_shaiwei_manifest.json").write_text(
        json.dumps(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "code_snapshot_sha256": code_snapshot_sha256(),
                "data_snapshot_sha256": ingest_snapshot_sha256(),
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    print(output_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
