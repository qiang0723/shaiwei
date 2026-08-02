"""Narrow immutable-ledger source selection for M3 discovery inputs."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Callable

import duckdb
import pandas as pd
import pyarrow.parquet as pq

from shaiwei.config import PROJECT_ROOT
from shaiwei.ledger import INGEST, resolve_artifact_path, sha256_file
from shaiwei.research.llm_factor import D1ControlError


SOURCE_START = "20201001"


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _date_key(value: object) -> str:
    rendered = str(value).replace("-", "")
    return rendered[:8] if rendered and rendered.lower() not in {"nan", "nat", "none"} else ""


def _overlaps(params: dict[str, Any], start: str, end: str) -> bool:
    exact = _date_key(params.get("trade_date", ""))
    if exact:
        return start <= exact <= end
    request_start = _date_key(params.get("start_date", "")) or "00000000"
    request_end = _date_key(params.get("end_date", "")) or "99999999"
    return request_start <= end and request_end >= start


def _latest_entries(
    source_api: str,
    predicate: Callable[[dict[str, Any]], bool],
) -> pd.DataFrame:
    rows = pd.read_csv(INGEST, dtype=str, keep_default_na=False)
    rows = rows.loc[rows["source_api"].eq(source_api)].copy()
    if rows.empty:
        raise D1ControlError(f"M3-2 source is absent: {source_api}")
    rows["_params"] = rows["params_json"].map(json.loads)
    rows["_params_key"] = rows["_params"].map(_canonical_json)
    rows["_time"] = pd.to_datetime(rows["ingest_time"], utc=True, errors="raise")
    latest = rows.sort_values(["_time", "batch_id"]).drop_duplicates("_params_key", keep="last")
    selected = latest.loc[latest["_params"].map(predicate)].copy()
    if selected.empty:
        raise D1ControlError(f"M3-2 relevant source is absent: {source_api}")
    return selected.sort_values(["_params_key", "batch_id"]).reset_index(drop=True)


def _source_entries(source_api: str, codes: set[str] | None, end: str) -> pd.DataFrame:
    def selected(params: dict[str, Any]) -> bool:
        code = str(params.get("ts_code", ""))
        if codes is not None and code and code not in codes:
            return False
        return _overlaps(params, SOURCE_START, end)

    return _latest_entries(source_api, selected)


def _read_verified(
    entries: pd.DataFrame,
    source_api: str,
    *,
    codes: set[str] | None = None,
    date_column: str | None = None,
    end: str,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    paths: list[str] = []
    identities: list[dict[str, Any]] = []
    root = PROJECT_ROOT.resolve()
    for _, row in entries.iterrows():
        path = resolve_artifact_path(row["parquet_path"]).resolve()
        try:
            path.relative_to(root)
        except ValueError as error:
            raise D1ControlError(f"M3-2 source escapes project: {source_api}") from error
        if not path.is_file() or pq.read_metadata(path).num_rows != int(row["row_count"]):
            raise D1ControlError(f"M3-2 source size differs: {source_api}")
        if sha256_file(path) != row["content_sha256"]:
            raise D1ControlError(f"M3-2 source hash differs: {source_api}")
        paths.append(str(path))
        identities.append(
            {
                "batch_id": str(row["batch_id"]),
                "params_sha256": _sha256_json(row["_params"]),
                "row_count": int(row["row_count"]),
                "content_sha256": str(row["content_sha256"]),
                "ingest_time": row["_time"].isoformat(),
            }
        )
    connection = duckdb.connect(":memory:")
    try:
        joins = ""
        parameters: list[Any] = [paths]
        conditions: list[str] = []
        if codes is not None:
            connection.register("wanted_codes", pd.DataFrame({"ts_code": sorted(codes)}))
            joins = " INNER JOIN wanted_codes c ON CAST(p.ts_code AS VARCHAR)=c.ts_code"
        if date_column is not None:
            conditions.append(f"CAST(p.{date_column} AS VARCHAR) BETWEEN ? AND ?")
            parameters.extend((SOURCE_START, end))
        where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
        frame = connection.execute(
            "SELECT p.* FROM read_parquet(?, union_by_name=true, hive_partitioning=false) p"
            + joins
            + where,
            parameters,
        ).df()
    finally:
        connection.close()
    return frame, {
        "source_api": source_api,
        "selected_batch_count": len(identities),
        "selected_batch_row_count": sum(item["row_count"] for item in identities),
        "selected_batch_snapshot_sha256": _sha256_json(identities),
        "loaded_row_count": len(frame),
    }


def load_m3_sources(
    codes: set[str], end: str
) -> tuple[dict[str, pd.DataFrame], dict[str, dict[str, Any]]]:
    frames: dict[str, pd.DataFrame] = {}
    evidence: dict[str, dict[str, Any]] = {}
    specifications = {
        "tushare.trade_cal": (None, "cal_date"),
        "tushare.daily": (codes, "trade_date"),
        "tushare.daily_basic": (codes, "trade_date"),
        "tushare.adj_factor": (codes, "trade_date"),
        "tushare.dividend": (codes, None),
        "tushare.index_member_all": (codes, None),
    }
    for api, (source_codes, date_column) in specifications.items():
        entries = _source_entries(api, source_codes, end)
        frames[api], evidence[api] = _read_verified(
            entries,
            api,
            codes=source_codes,
            date_column=date_column,
            end=end,
        )
    return frames, evidence
