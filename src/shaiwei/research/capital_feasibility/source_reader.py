"""Read only exact, hash-verified raw batches needed by the paper-v1 engine."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from shaiwei.research.production_conversion.contract import ProtocolError

from .raw_manifest import load_and_verify_manifest


@dataclass(frozen=True)
class RawSources:
    daily: pd.DataFrame
    index_daily: pd.DataFrame
    stock_basic: pd.DataFrame
    namechange: pd.DataFrame
    suspend: pd.DataFrame
    dividends: pd.DataFrame
    trade_cal: pd.DataFrame
    manifest_sha256: str


def _code(value: str) -> str:
    value = str(value)
    if len(value) == 8 and value[:2] in {"SH", "SZ", "BJ"}:
        return f"{value[2:]}.{value[:2]}"
    return value


def _date(value: object) -> str:
    return str(value).replace("-", "")[:8]


def _read_api(
    connection: duckdb.DuckDBPyConnection,
    entries: list[dict[str, Any]],
    api: str,
    project_root: Path,
    *,
    codes: set[str] | None = None,
    date_column: str | None = None,
    start: str = "",
    end: str = "",
) -> pd.DataFrame:
    selected = [entry for entry in entries if entry["source_api"] == api]
    paths = [str((project_root / entry["path"]).resolve()) for entry in selected]
    if not paths:
        raise ProtocolError(f"M6-5B raw API is absent: {api}")
    relation = connection.from_parquet(paths, union_by_name=True, filename=True)
    relation.create_view("raw_api", replace=True)
    identity = pd.DataFrame({
        "filename": paths,
        "_ingest_time": [entry["ingest_time"] for entry in selected],
    })
    connection.register("raw_identity", identity)
    joins = "JOIN raw_identity i USING(filename)"
    where: list[str] = []
    parameters: list[str] = []
    if codes is not None:
        connection.register("target_codes", pd.DataFrame({"ts_code": sorted(codes)}))
        joins += " JOIN target_codes c ON r.ts_code = c.ts_code"
    if date_column:
        where.append(f"CAST(r.{date_column} AS VARCHAR) BETWEEN ? AND ?")
        parameters.extend((start, end))
    clause = " WHERE " + " AND ".join(where) if where else ""
    return connection.execute(
        f"SELECT r.*, i._ingest_time FROM raw_api r {joins}{clause}", parameters,
    ).df()


def _latest(frame: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    if any(key not in frame for key in keys):
        raise ProtocolError(f"M6-5B raw schema lacks keys: {keys}")
    return frame.sort_values("_ingest_time").drop_duplicates(keys, keep="last").drop(
        columns=["_ingest_time", "filename"], errors="ignore"
    )


def _target_context(bundle: dict[str, Any]) -> tuple[set[str], str, str]:
    codes: set[str] = set()
    dates: list[str] = []
    for treatment in bundle["treatments"].values():
        dates.extend(_date(row["date"]) for row in treatment["daily"])
        for row in treatment["rebalances"]:
            dates.extend((_date(row["signal_date"]), _date(row["trade_date"])))
            codes.update(_code(code) for code in row["targets"])
    start = (datetime.strptime(min(dates), "%Y%m%d") - timedelta(days=90)).strftime("%Y%m%d")
    return codes, start, max(dates)


def load_sources(
    manifest_path: Path,
    bundle: dict[str, Any],
    *,
    project_root: Path,
) -> RawSources:
    manifest = load_and_verify_manifest(manifest_path, project_root=project_root)
    codes, start, end = _target_context(bundle)
    connection = duckdb.connect(":memory:")
    try:
        entries = manifest["entries"]
        frames = {
            "tushare.daily": _read_api(connection, entries, "tushare.daily", project_root, codes=codes, date_column="trade_date", start=start, end=end),
            "tushare.index_daily": _read_api(connection, entries, "tushare.index_daily", project_root, codes={"000906.SH"}, date_column="trade_date", start=start, end=end),
            "tushare.stock_basic": _read_api(connection, entries, "tushare.stock_basic", project_root, codes=codes),
            "tushare.namechange": _read_api(connection, entries, "tushare.namechange", project_root, codes=codes),
            "tushare.suspend_d": _read_api(connection, entries, "tushare.suspend_d", project_root, codes=codes, date_column="trade_date", start=start, end=end),
            "tushare.dividend": _read_api(connection, entries, "tushare.dividend", project_root, codes=codes),
            "tushare.trade_cal": _read_api(connection, entries, "tushare.trade_cal", project_root, date_column="cal_date", start=start, end=end),
        }
    finally:
        connection.close()
    daily = _latest(frames["tushare.daily"], ["ts_code", "trade_date"])
    daily["trade_date"] = daily["trade_date"].map(_date)
    daily["amount_rmb"] = pd.to_numeric(daily["amount"], errors="coerce") * 1000.0
    daily = daily.loc[daily["ts_code"].isin(codes) & daily["trade_date"].between(start, end)].copy()
    if daily.duplicated(["ts_code", "trade_date"]).any() or daily["ts_code"].str.endswith(".BJ").any():
        raise ProtocolError("M6-5B daily keys are duplicated or contain Beijing rows")
    index = _latest(frames["tushare.index_daily"], ["ts_code", "trade_date"])
    index["trade_date"] = index["trade_date"].map(_date)
    index = index.loc[index["ts_code"].eq("000906.SH") & index["trade_date"].between(start, end)]
    stock = _latest(frames["tushare.stock_basic"], ["ts_code"])
    stock = stock.loc[stock["ts_code"].isin(codes)]
    name = _latest(frames["tushare.namechange"], ["ts_code", "start_date", "end_date", "name"])
    name = name.loc[name["ts_code"].isin(codes)]
    for column in ("start_date", "end_date", "ann_date"):
        if column in name:
            name[column] = name[column].map(_date)
    suspend_keys = [key for key in ("ts_code", "trade_date", "suspend_type") if key in frames["tushare.suspend_d"]]
    suspend = _latest(frames["tushare.suspend_d"], suspend_keys)
    suspend = suspend.loc[suspend["ts_code"].isin(codes)]
    if "trade_date" in suspend:
        suspend["trade_date"] = suspend["trade_date"].map(_date)
    dividends = _latest(frames["tushare.dividend"], ["ts_code", "end_date"])
    dividends = dividends.loc[dividends["ts_code"].isin(codes)]
    for column in ("end_date", "ann_date", "record_date", "ex_date", "pay_date", "div_listdate"):
        if column in dividends:
            dividends[column] = dividends[column].map(_date)
    trade_cal = _latest(frames["tushare.trade_cal"], ["exchange", "cal_date"])
    trade_cal["cal_date"] = trade_cal["cal_date"].map(_date)
    trade_cal = trade_cal.loc[trade_cal["cal_date"].between(start, end)]
    from shaiwei.research.model_attribution.contract import sha256_file
    return RawSources(
        daily, index, stock, name, suspend, dividends, trade_cal,
        sha256_file(manifest_path),
    )
