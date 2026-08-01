"""Load and verify the narrow immutable source set for M3-0."""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any, Callable

import duckdb
import pandas as pd
import pyarrow.parquet as pq

from shaiwei.ingest.catalog import canonical_params_key
from shaiwei.ledger import INGEST, resolve_artifact_path, sha256_file

from tools.m3_star_custom_pit.contract import GateFailure, PROJECT_ROOT, canonical_sha256


ParamsPredicate = Callable[[dict[str, Any]], bool]


@dataclass(frozen=True)
class InputBundle:
    stock_basic: pd.DataFrame
    namechange: pd.DataFrame
    trade_cal: pd.DataFrame
    daily: pd.DataFrame
    daily_basic: pd.DataFrame
    star_codes: tuple[str, ...]
    evidence: dict[str, Any]


def _date_key(value: object) -> str:
    rendered = str(value).replace("-", "")
    return rendered[:8] if rendered and rendered.lower() not in {"nan", "nat", "none"} else ""


def _all(_: dict[str, Any]) -> bool:
    return True


def latest_entries(source_api: str, predicate: ParamsPredicate = _all) -> pd.DataFrame:
    entries = pd.read_csv(INGEST, dtype=str, keep_default_na=False)
    entries = entries.loc[entries["source_api"].eq(source_api)].copy()
    if entries.empty:
        raise GateFailure(f"no immutable ledger rows for {source_api}")
    entries["_params"] = entries["params_json"].map(json.loads)
    entries["_params_key"] = entries["_params"].map(canonical_params_key)
    entries["_time"] = pd.to_datetime(entries["ingest_time"], utc=True, errors="raise")
    latest = entries.sort_values(["_time", "batch_id"]).drop_duplicates("_params_key", keep="last")
    selected = latest.loc[latest["_params"].map(predicate)].copy()
    if selected.empty:
        raise GateFailure(f"no relevant immutable ledger rows for {source_api}")
    return selected.sort_values(["_params_key", "batch_id"]).reset_index(drop=True)


def _verify_entries(entries: pd.DataFrame, source_api: str) -> tuple[list[str], dict[str, Any]]:
    paths: list[str] = []
    identities: list[dict[str, Any]] = []
    for _, row in entries.iterrows():
        path = resolve_artifact_path(row["parquet_path"]).resolve()
        try:
            path.relative_to(PROJECT_ROOT)
        except ValueError as error:
            raise GateFailure(f"source artifact escapes project: {source_api}") from error
        if not path.is_file():
            raise GateFailure(f"source artifact is missing: {source_api}")
        metadata = pq.read_metadata(path)
        if metadata.num_rows != int(row["row_count"]):
            raise GateFailure(f"source row count mismatch: {source_api}")
        if sha256_file(path) != row["content_sha256"]:
            raise GateFailure(f"source content hash mismatch: {source_api}")
        paths.append(str(path))
        identities.append(
            {
                "batch_id": str(row["batch_id"]),
                "params_sha256": canonical_sha256(row["_params"]),
                "row_count": int(row["row_count"]),
                "content_sha256": str(row["content_sha256"]),
                "ingest_time": row["_time"].isoformat(),
            }
        )
    return paths, {
        "source_api": source_api,
        "selected_batch_count": len(identities),
        "selected_batch_row_count": sum(row["row_count"] for row in identities),
        "selected_batch_snapshot_sha256": canonical_sha256(identities),
        "latest_ingest_time": max(row["ingest_time"] for row in identities),
        "earliest_latest_ingest_time": min(row["ingest_time"] for row in identities),
    }


def _read_paths(
    paths: list[str],
    *,
    codes: tuple[str, ...] | None = None,
    date_column: str | None = None,
    start: str | None = None,
    end: str | None = None,
) -> pd.DataFrame:
    connection = duckdb.connect(":memory:")
    try:
        conditions: list[str] = []
        joins = ""
        if codes is not None:
            connection.register("wanted_codes", pd.DataFrame({"ts_code": list(codes)}))
            joins = " INNER JOIN wanted_codes c ON CAST(p.ts_code AS VARCHAR) = c.ts_code"
        params: list[Any] = [paths]
        if date_column and start and end:
            conditions.append(f"CAST(p.{date_column} AS VARCHAR) BETWEEN ? AND ?")
            params.extend([start, end])
        where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
        return connection.execute(
            "SELECT p.* FROM read_parquet(?, union_by_name=true, hive_partitioning=false) p"
            + joins
            + where,
            params,
        ).df()
    finally:
        connection.close()


def _minimum_ingest_date(entries: pd.DataFrame, minimum: str, label: str) -> None:
    minimum_day = pd.Timestamp(minimum, tz="Asia/Shanghai").date()
    local_days = entries["_time"].dt.tz_convert("Asia/Shanghai").dt.date
    if bool(local_days.lt(minimum_day).any()):
        raise GateFailure(f"{label} source freshness is earlier than {minimum}")


def load_stock_identity(protocol: dict[str, Any]) -> tuple[pd.DataFrame, tuple[str, ...], dict[str, Any]]:
    sources = protocol["sources"]
    entries = latest_entries("tushare.stock_basic")
    _minimum_ingest_date(entries, sources["stock_basic_latest_ingest_date_minimum"], "stock_basic")
    paths, evidence = _verify_entries(entries, "tushare.stock_basic")
    frame = _read_paths(paths)
    required = {"ts_code", "market", "exchange", "list_date", "delist_date"}
    if missing := required - set(frame.columns):
        raise GateFailure(f"stock_basic missing fields: {sorted(missing)}")
    frame["ts_code"] = frame["ts_code"].astype("string")
    duplicate_count = int(frame.duplicated("ts_code", keep=False).sum())
    if duplicate_count > int(sources["duplicate_stock_code_maximum"]):
        raise GateFailure(f"stock_basic duplicate codes exceed maximum: {duplicate_count}")
    market_mask = frame["market"].astype("string").eq(sources["star_market_value"])
    market_mask &= frame["exchange"].astype("string").eq(sources["star_exchange_value"])
    code_mask = frame["ts_code"].str.match(re.compile(sources["star_code_pattern"]), na=False)
    mismatch = int((market_mask ^ code_mask).sum())
    if mismatch > int(sources["market_code_selector_mismatch_maximum"]):
        raise GateFailure(f"STAR market/code selector mismatch exceeds maximum: {mismatch}")
    star = frame.loc[market_mask & code_mask].sort_values("ts_code").reset_index(drop=True)
    if star.empty:
        raise GateFailure("STAR stock identity set is empty")
    codes = tuple(star["ts_code"].astype(str))
    if any(code.endswith(sources["bse_suffix_forbidden"]) for code in codes):
        raise GateFailure("STAR stock identity contains forbidden .BJ")
    evidence.update(
        {
            "duplicate_stock_code_count": duplicate_count,
            "market_code_selector_mismatch_count": mismatch,
            "star_security_count": len(codes),
        }
    )
    return star, codes, evidence


def _overlaps(params: dict[str, Any], start: str, end: str) -> bool:
    exact = _date_key(params.get("trade_date", ""))
    if exact:
        return start <= exact <= end
    request_start = _date_key(params.get("start_date", "")) or "00000000"
    request_end = _date_key(params.get("end_date", "")) or "99999999"
    return request_start <= end and request_end >= start


def _market_predicate(codes: set[str], start: str, end: str) -> ParamsPredicate:
    def selected(params: dict[str, Any]) -> bool:
        code = str(params.get("ts_code", ""))
        if code:
            return code in codes and _overlaps(params, start, end)
        return bool(_date_key(params.get("trade_date", ""))) and _overlaps(params, start, end)

    return selected


def load_inputs(protocol: dict[str, Any]) -> InputBundle:
    identity = protocol["identity"]
    sources = protocol["sources"]
    start = str(identity["board_launch_date"]).replace("-", "")
    end = str(identity["source_cutoff_date"]).replace("-", "")
    stock, codes, stock_evidence = load_stock_identity(protocol)
    code_set = set(codes)
    evidence: dict[str, Any] = {"tushare.stock_basic": stock_evidence}

    name_entries = latest_entries(
        "tushare.namechange",
        lambda params: str(params.get("ts_code", "")) in code_set,
    )
    params_codes = {str(params.get("ts_code", "")) for params in name_entries["_params"]}
    if missing_codes := code_set - params_codes:
        raise GateFailure(f"namechange source is missing STAR requests: {len(missing_codes)}")
    _minimum_ingest_date(name_entries, sources["namechange_latest_ingest_date_minimum"], "namechange")
    paths, evidence["tushare.namechange"] = _verify_entries(name_entries, "tushare.namechange")
    namechange = _read_paths(paths, codes=codes)

    cal_entries = latest_entries("tushare.trade_cal")
    paths, evidence["tushare.trade_cal"] = _verify_entries(cal_entries, "tushare.trade_cal")
    trade_cal = _read_paths(paths, date_column="cal_date", start=start, end=end)

    loaded_market: dict[str, pd.DataFrame] = {}
    predicate = _market_predicate(code_set, start, end)
    for api in ("tushare.daily", "tushare.daily_basic"):
        entries = latest_entries(api, predicate)
        paths, evidence[api] = _verify_entries(entries, api)
        loaded_market[api] = _read_paths(
            paths,
            codes=codes,
            date_column="trade_date",
            start=start,
            end=end,
        )

    evidence["selected_input_sha256"] = canonical_sha256(evidence)
    return InputBundle(
        stock_basic=stock,
        namechange=namechange,
        trade_cal=trade_cal,
        daily=loaded_market["tushare.daily"],
        daily_basic=loaded_market["tushare.daily_basic"],
        star_codes=codes,
        evidence=evidence,
    )
