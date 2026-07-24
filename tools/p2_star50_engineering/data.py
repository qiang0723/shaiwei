"""Build the isolated P2-1 real-data engineering artifacts without strategy results."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
from typing import Any, Callable
import uuid

import duckdb
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from shaiwei.benchmark.fitness import industry_pit_exposure
from shaiwei.config import PROJECT_ROOT, load
from shaiwei.ingest.catalog import canonical_params_key
from shaiwei.ledger import INGEST, resolve_artifact_path, sha256_file
from shaiwei.transform.market import attach_trade_limit_flags, sanitize_adj_factors, transform_market_data
from shaiwei.transform.qlib_bin import (
    QLIB_FIELDS,
    QLIB_MANIFEST,
    benchmark_frame,
    qlib_code,
    qlib_tree_integrity,
)
from shaiwei.transform.universe import st_flags_on

from tools.p2_star50_engineering.contract import (
    GateFailure,
    V2_PATHS,
    canonical_sha256,
    load_protocol,
    normalize_daily_membership,
    verify_monthly_crosscheck,
    verify_official_daily_membership,
    verify_upstream_evidence,
)


BatchPredicate = Callable[[dict[str, Any]], bool]


def _date_key(value: object) -> str:
    rendered = str(value).replace("-", "")
    return rendered[:8] if rendered and rendered.lower() not in {"nan", "nat", "none"} else ""


def _latest_batch_entries(source_api: str, predicate: BatchPredicate) -> pd.DataFrame:
    entries = pd.read_csv(INGEST, dtype=str, keep_default_na=False)
    entries = entries.loc[entries["source_api"].eq(source_api)].copy()
    if entries.empty:
        raise GateFailure(f"no committed batches for {source_api}")
    entries["_params"] = entries["params_json"].map(json.loads)
    entries["_params_key"] = entries["_params"].map(canonical_params_key)
    entries["_time"] = pd.to_datetime(entries["ingest_time"], utc=True, errors="raise")
    latest = entries.sort_values("_time").drop_duplicates("_params_key", keep="last")
    selected = latest.loc[latest["_params"].map(predicate)].copy()
    if selected.empty:
        raise GateFailure(f"no relevant committed batches for {source_api}")
    return selected.sort_values(["_time", "batch_id"]).reset_index(drop=True)


def _load_selected_api(
    source_api: str,
    predicate: BatchPredicate,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    entries = _latest_batch_entries(source_api, predicate)
    paths: list[str] = []
    identities: list[dict[str, Any]] = []
    for _, entry in entries.iterrows():
        path = resolve_artifact_path(entry["parquet_path"])
        if not path.is_file():
            raise GateFailure(f"committed batch is missing for {source_api}")
        metadata = pq.read_metadata(path)
        if metadata.num_rows != int(entry["row_count"]):
            raise GateFailure(f"committed batch row count mismatch for {source_api}")
        if sha256_file(path) != entry["content_sha256"]:
            raise GateFailure(f"committed batch hash mismatch for {source_api}")
        paths.append(str(path))
        identities.append(
            {
                "batch_id": str(entry["batch_id"]),
                "params_sha256": canonical_sha256(entry["_params"]),
                "row_count": int(entry["row_count"]),
                "content_sha256": str(entry["content_sha256"]),
            }
        )
    connection = duckdb.connect(":memory:")
    try:
        frame = connection.execute(
            "SELECT * FROM read_parquet(?, union_by_name = true, hive_partitioning = false)",
            [paths],
        ).df()
    finally:
        connection.close()
    return frame, {
        "source_api": source_api,
        "selected_batch_count": len(identities),
        "selected_batch_row_count": sum(row["row_count"] for row in identities),
        "selected_batch_snapshot_sha256": canonical_sha256(identities),
    }


def _overlaps(params: dict[str, Any], start: str, end: str) -> bool:
    trade_date = _date_key(params.get("trade_date", ""))
    if trade_date:
        return start <= trade_date <= end
    request_start = _date_key(params.get("start_date", "")) or "00000000"
    request_end = _date_key(params.get("end_date", "")) or "99999999"
    return request_start <= end and request_end >= start


def _code_or_date_predicate(codes: set[str], start: str, end: str) -> BatchPredicate:
    def selected(params: dict[str, Any]) -> bool:
        code = str(params.get("ts_code", ""))
        if code:
            return code in codes and _overlaps(params, start, end)
        return bool(_date_key(params.get("trade_date", ""))) and _overlaps(params, start, end)

    return selected


def _code_predicate(codes: set[str]) -> BatchPredicate:
    return lambda params: str(params.get("ts_code", "")) in codes


def _all_predicate(_: dict[str, Any]) -> bool:
    return True


def _benchmark_predicate(index_code: str, start: str, end: str) -> BatchPredicate:
    def selected(params: dict[str, Any]) -> bool:
        code = str(params.get("ts_code", params.get("index_code", "")))
        return code == index_code and _overlaps(params, start, end)

    return selected


def _filter_codes_dates(
    frame: pd.DataFrame,
    codes: set[str],
    start: str,
    end: str,
    *,
    code_column: str = "ts_code",
    date_column: str = "trade_date",
) -> pd.DataFrame:
    result = frame.copy()
    result[code_column] = result[code_column].astype("string")
    result[date_column] = (
        pd.to_datetime(result[date_column].astype("string"), format="%Y%m%d", errors="coerce")
        .dt.strftime("%Y%m%d")
        .astype("string")
    )
    return result.loc[
        result[code_column].isin(codes) & result[date_column].between(start, end, inclusive="both")
    ].reset_index(drop=True)


def _ensure_unique(frame: pd.DataFrame, keys: list[str], label: str, maximum: int) -> int:
    count = int(frame.duplicated(keys, keep=False).sum())
    if count > maximum:
        raise GateFailure(f"{label} duplicate key count exceeds frozen maximum: {count}")
    return count


def _write_immutable_parquet(frame: pd.DataFrame, path: Path) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    staging = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    frame.to_parquet(staging, index=False, compression="zstd")
    digest = sha256_file(staging)
    if path.exists():
        if sha256_file(path) != digest:
            staging.unlink()
            raise GateFailure(f"immutable dataset artifact differs: {path.relative_to(PROJECT_ROOT)}")
        staging.unlink()
    else:
        os.replace(staging, path)
    return {
        "path": path.relative_to(PROJECT_ROOT).as_posix(),
        "sha256": digest,
        "row_count": int(len(frame)),
    }


def _load_and_check_inputs(protocol: dict[str, Any]) -> dict[str, Any]:
    contract = protocol["dataset_contract"]
    strategy_start = str(contract["strategy_usable_start"]).replace("-", "")
    cutoff = str(contract["source_cutoff_date"]).replace("-", "")

    upstream = verify_upstream_evidence(protocol)
    official = normalize_daily_membership(pd.read_parquet(V2_PATHS["v2_daily_membership_sha256"]))
    official_report = verify_official_daily_membership(official, protocol)
    codes = set(official["code"].astype(str))

    trade_cal, trade_cal_evidence = _load_selected_api("tushare.trade_cal", _all_predicate)
    trade_cal["cal_date"] = trade_cal["cal_date"].astype("string")
    sse_calendar = sorted(
        trade_cal.loc[
            trade_cal["exchange"].astype("string").eq("SSE")
            & trade_cal["is_open"].astype("string").eq("1")
            & trade_cal["cal_date"].astype("string").le(cutoff),
            "cal_date",
        ]
        .astype(str)
        .drop_duplicates()
    )
    if strategy_start not in sse_calendar:
        raise GateFailure("strategy usable start is not an SSE trading day")
    start_position = sse_calendar.index(strategy_start)
    warmup_days = int(contract["feature_warmup_trade_days"])
    if start_position < warmup_days:
        raise GateFailure("trade calendar cannot satisfy the frozen feature warmup")
    warmup_start = sse_calendar[start_position - warmup_days]
    calendar = [date for date in sse_calendar if warmup_start <= date <= cutoff]

    index_weight, index_weight_evidence = _load_selected_api(
        "tushare.index_weight",
        _benchmark_predicate(protocol["identity"]["benchmark_source_code"], strategy_start, cutoff),
    )
    index_weight["trade_date"] = (
        pd.to_datetime(index_weight["trade_date"].astype("string"), format="%Y%m%d", errors="coerce")
        .dt.strftime("%Y%m%d")
        .astype("string")
    )
    monthly_report = verify_monthly_crosscheck(index_weight, official, protocol)

    evidence = {
        "tushare.trade_cal": trade_cal_evidence,
        "tushare.index_weight": index_weight_evidence,
    }
    return {
        "upstream": upstream,
        "official": official,
        "official_report": official_report,
        "monthly_report": monthly_report,
        "codes": codes,
        "strategy_start": strategy_start,
        "cutoff": cutoff,
        "warmup_start": warmup_start,
        "calendar": calendar,
        "trade_cal": trade_cal,
        "evidence": evidence,
    }


def _suspension_flags(suspend: pd.DataFrame, codes: set[str], start: str, end: str) -> pd.DataFrame:
    required = {"ts_code", "trade_date", "suspend_timing"}
    if missing := required - set(suspend.columns):
        raise GateFailure(f"suspend_d missing fields: {sorted(missing)}")
    frame = _filter_codes_dates(suspend, codes, start, end)
    timing = frame["suspend_timing"].astype("string").fillna("").str.strip()
    frame["full_day_suspend"] = timing.eq("")
    frame["intraday_suspend"] = ~frame["full_day_suspend"]
    return (
        frame.groupby(["ts_code", "trade_date"], as_index=False)[["full_day_suspend", "intraday_suspend"]]
        .max()
        .reset_index(drop=True)
    )


def _listing_quality(member_days: pd.DataFrame, stock_basic: pd.DataFrame) -> tuple[int, int]:
    required = {"ts_code", "list_date", "delist_date"}
    if missing := required - set(stock_basic.columns):
        raise GateFailure(f"stock_basic missing fields: {sorted(missing)}")
    basic = stock_basic.loc[:, list(required)].copy()
    basic = basic.sort_values(["ts_code", "list_date"]).drop_duplicates("ts_code", keep="last")
    joined = member_days.merge(basic, on="ts_code", how="left", validate="many_to_one")
    point = pd.to_datetime(joined["trade_date"], format="%Y%m%d", errors="coerce")
    listed = pd.to_datetime(joined["list_date"].astype("string"), format="%Y%m%d", errors="coerce")
    delisted = pd.to_datetime(joined["delist_date"].astype("string"), format="%Y%m%d", errors="coerce")
    before_listing = int((listed.isna() | point.lt(listed)).sum())
    on_or_after_delisting = int((delisted.notna() & point.ge(delisted)).sum())
    return before_listing, on_or_after_delisting


def build_dataset() -> dict[str, Any]:
    """Build only structural real-data artifacts; never calculate strategy effects."""
    protocol = load_protocol()
    inputs = _load_and_check_inputs(protocol)
    contract = protocol["dataset_contract"]
    codes = inputs["codes"]
    warmup_start = inputs["warmup_start"]
    strategy_start = inputs["strategy_start"]
    cutoff = inputs["cutoff"]
    evidence = dict(inputs["evidence"])

    market_apis = ("tushare.daily", "tushare.adj_factor", "tushare.daily_basic")
    loaded: dict[str, pd.DataFrame] = {}
    for api in market_apis:
        frame, api_evidence = _load_selected_api(
            api,
            _code_or_date_predicate(codes, warmup_start, cutoff),
        )
        loaded[api] = _filter_codes_dates(frame, codes, warmup_start, cutoff)
        evidence[api] = api_evidence

    for api in ("tushare.stock_basic",):
        frame, api_evidence = _load_selected_api(api, _all_predicate)
        loaded[api] = frame.loc[frame["ts_code"].astype("string").isin(codes)].reset_index(drop=True)
        evidence[api] = api_evidence
    for api in ("tushare.namechange", "tushare.index_member_all", "tushare.dividend"):
        frame, api_evidence = _load_selected_api(api, _code_predicate(codes))
        loaded[api] = frame.loc[frame["ts_code"].astype("string").isin(codes)].reset_index(drop=True)
        evidence[api] = api_evidence
    suspend, suspend_evidence = _load_selected_api(
        "tushare.suspend_d",
        lambda params: _overlaps(params, warmup_start, cutoff),
    )
    loaded["tushare.suspend_d"] = suspend
    evidence["tushare.suspend_d"] = suspend_evidence
    index_daily, index_daily_evidence = _load_selected_api(
        "tushare.index_daily",
        _benchmark_predicate(protocol["identity"]["benchmark_source_code"], warmup_start, cutoff),
    )
    loaded["tushare.index_daily"] = _filter_codes_dates(
        index_daily,
        {protocol["identity"]["benchmark_source_code"]},
        warmup_start,
        cutoff,
    )
    evidence["tushare.index_daily"] = index_daily_evidence

    daily = loaded["tushare.daily"]
    adj_factor = loaded["tushare.adj_factor"]
    daily_basic = loaded["tushare.daily_basic"]
    duplicate_daily = _ensure_unique(
        daily, ["ts_code", "trade_date"], "daily", int(contract["duplicate_market_key_count_maximum"])
    )
    duplicate_factor = _ensure_unique(
        adj_factor,
        ["ts_code", "trade_date"],
        "adj_factor",
        int(contract["duplicate_factor_key_count_maximum"]),
    )
    duplicate_basic = _ensure_unique(
        daily_basic,
        ["ts_code", "trade_date"],
        "daily_basic",
        int(contract["duplicate_basic_key_count_maximum"]),
    )

    corrected_factors = sanitize_adj_factors(daily, adj_factor, loaded["tushare.dividend"])
    market = attach_trade_limit_flags(
        transform_market_data(daily, corrected_factors),
        loaded["tushare.stock_basic"],
        loaded["tushare.namechange"],
        load().limit_rules.model_dump(),
        copy=False,
    )
    market = (
        market.loc[market["trade_date"].astype("string").between(warmup_start, cutoff, inclusive="both")]
        .sort_values(["ts_code", "trade_date"])
        .reset_index(drop=True)
    )
    if market["ts_code"].astype("string").str.endswith(".BJ", na=False).any():
        raise GateFailure("derived market contains forbidden .BJ securities")
    if (market["limit_buy"].astype(bool) & market["limit_sell"].astype(bool)).any():
        raise GateFailure("a market row cannot be both buy- and sell-limited")

    member_days = inputs["official"].rename(columns={"code": "ts_code"})
    member_days = member_days.loc[
        member_days["trade_date"].between(strategy_start, cutoff, inclusive="both")
    ].reset_index(drop=True)
    before_listing, on_or_after_delisting = _listing_quality(member_days, loaded["tushare.stock_basic"])
    if before_listing > int(contract["member_before_listing_count_maximum"]):
        raise GateFailure(f"official member days before listing: {before_listing}")
    if on_or_after_delisting > int(contract["member_on_or_after_delisting_count_maximum"]):
        raise GateFailure(f"official member days on/after delisting: {on_or_after_delisting}")

    qlib_columns = ["ts_code", "trade_date", *QLIB_FIELDS]
    enriched = member_days.merge(
        market.loc[:, qlib_columns],
        on=["ts_code", "trade_date"],
        how="left",
        validate="one_to_one",
    )
    enriched["has_market_bar"] = enriched["close"].notna()
    suspensions = _suspension_flags(loaded["tushare.suspend_d"], codes, strategy_start, cutoff)
    enriched = enriched.merge(
        suspensions,
        on=["ts_code", "trade_date"],
        how="left",
        validate="one_to_one",
    )
    enriched[["full_day_suspend", "intraday_suspend"]] = enriched[
        ["full_day_suspend", "intraday_suspend"]
    ].fillna(False)
    missing_market = ~enriched["has_market_bar"]
    unaccounted_market = missing_market & ~enriched["full_day_suspend"].astype(bool)
    intraday_explained_missing = missing_market & enriched["intraday_suspend"].astype(bool)
    coverage = float((~unaccounted_market).mean())
    if coverage < float(contract["market_bar_or_full_day_suspend_coverage_minimum"]):
        raise GateFailure(f"market bar/full-day suspension coverage below frozen threshold: {coverage:.8f}")
    if bool(contract["intraday_suspend_cannot_explain_missing_bar"]) and intraday_explained_missing.any():
        raise GateFailure("intraday suspension was used to explain a missing market bar")

    basic_columns = [
        column
        for column in ("turnover_rate", "volume_ratio", "pe", "pb", "total_mv", "circ_mv")
        if column in daily_basic.columns
    ]
    basic_slice = daily_basic.loc[:, ["ts_code", "trade_date", *basic_columns]].copy()
    basic_slice["has_daily_basic"] = True
    enriched = enriched.merge(
        basic_slice,
        on=["ts_code", "trade_date"],
        how="left",
        validate="one_to_one",
    )
    enriched["has_daily_basic"] = enriched["has_daily_basic"].astype("boolean").fillna(False).astype(bool)
    bar_mask = enriched["has_market_bar"].astype(bool)
    daily_basic_coverage = float(enriched.loc[bar_mask, "has_daily_basic"].mean())
    if daily_basic_coverage < float(contract["daily_basic_member_bar_coverage_minimum"]):
        raise GateFailure(
            f"daily_basic member-bar coverage below frozen threshold: {daily_basic_coverage:.8f}"
        )

    industry = industry_pit_exposure(member_days, loaded["tushare.index_member_all"])
    enriched = enriched.merge(
        industry,
        on=["ts_code", "trade_date"],
        how="left",
        validate="one_to_one",
    )
    industry_coverage = float(enriched.loc[bar_mask, "industry"].notna().mean())
    if industry_coverage < float(contract["pit_sw_l1_industry_coverage_minimum"]):
        raise GateFailure(f"PIT SW L1 industry coverage below frozen threshold: {industry_coverage:.8f}")
    enriched["is_st"] = st_flags_on(
        loaded["tushare.namechange"],
        enriched.loc[:, ["ts_code", "trade_date"]],
    ).to_numpy()

    dataset_root = PROJECT_ROOT / protocol["identity"]["dataset_root"]
    artifacts = {
        "market": _write_immutable_parquet(market, dataset_root / "market.parquet"),
        "member_days": _write_immutable_parquet(
            enriched.sort_values(["trade_date", "ts_code"]).reset_index(drop=True),
            dataset_root / "member_days.parquet",
        ),
        "benchmark": _write_immutable_parquet(
            loaded["tushare.index_daily"].sort_values("trade_date").reset_index(drop=True),
            dataset_root / "benchmark.parquet",
        ),
    }
    selected_input_sha256 = canonical_sha256(evidence)
    builder_code_sha256 = canonical_sha256(
        {
            "contract.py": sha256_file(Path(__file__).with_name("contract.py")),
            "data.py": sha256_file(Path(__file__)),
            "market.py": sha256_file(PROJECT_ROOT / "src/shaiwei/transform/market.py"),
            "qlib_bin.py": sha256_file(PROJECT_ROOT / "src/shaiwei/transform/qlib_bin.py"),
        }
    )
    quality = {
        "schema_version": "p2-star50-engineering-quality-v1",
        "protocol_sha256": sha256_file(PROJECT_ROOT / "config/p2_star50_engineering_v1.yaml"),
        "builder_code_sha256": builder_code_sha256,
        "upstream_artifact_hashes": inputs["upstream"]["artifact_hashes"],
        "selected_input_sha256": selected_input_sha256,
        "batch_evidence": evidence,
        "input_gate": {
            "upstream": inputs["upstream"],
            "official_daily_membership": inputs["official_report"],
            "monthly_crosscheck": inputs["monthly_report"],
        },
        "dataset": {
            "warmup_start": warmup_start,
            "strategy_usable_start": strategy_start,
            "source_cutoff_date": cutoff,
            "calendar_trade_date_count": len(inputs["calendar"]),
            "member_day_count": int(len(enriched)),
            "market_row_count": int(len(market)),
            "market_bar_count": int(bar_mask.sum()),
            "full_day_suspension_without_bar_count": int(
                (missing_market & enriched["full_day_suspend"].astype(bool)).sum()
            ),
            "unaccounted_missing_market_count": int(unaccounted_market.sum()),
            "intraday_suspend_explained_missing_count": int(intraday_explained_missing.sum()),
            "market_bar_or_full_day_suspend_coverage": coverage,
            "daily_basic_member_bar_coverage": daily_basic_coverage,
            "pit_sw_l1_industry_member_bar_coverage": industry_coverage,
            "member_before_listing_count": before_listing,
            "member_on_or_after_delisting_count": on_or_after_delisting,
            "st_member_day_count": int(enriched["is_st"].sum()),
            "limit_buy_member_day_count": int(
                enriched.loc[bar_mask, "limit_buy"].fillna(False).astype(bool).sum()
            ),
            "limit_sell_member_day_count": int(
                enriched.loc[bar_mask, "limit_sell"].fillna(False).astype(bool).sum()
            ),
            "bse_row_count": 0,
            "duplicate_market_key_count": duplicate_daily,
            "duplicate_factor_key_count": duplicate_factor,
            "duplicate_basic_key_count": duplicate_basic,
            "artifacts": artifacts,
        },
        "input_gate_pass": True,
        "dataset_complete": True,
        "strategy_results_inspected": False,
        "strategy_effective": "NOT_EVALUATED",
        "production_authorization": "none",
    }
    quality_path = PROJECT_ROOT / protocol["identity"]["quality_report"]
    quality_path.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(quality, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if quality_path.exists() and quality_path.read_text(encoding="utf-8") != rendered:
        raise GateFailure("immutable P2-1 quality report differs from requested build")
    quality_path.write_text(rendered, encoding="utf-8")
    quality["quality_report_sha256"] = sha256_file(quality_path)
    return {
        "protocol": protocol,
        "quality": quality,
        "market": market,
        "official": inputs["official"],
        "trade_cal": inputs["trade_cal"],
        "index_daily": loaded["tushare.index_daily"],
        "calendar": inputs["calendar"],
        "data_snapshot_sha256": canonical_sha256(
            {
                "selected_input_sha256": selected_input_sha256,
                "artifacts": {name: value["sha256"] for name, value in artifacts.items()},
            }
        ),
    }


def membership_intervals_from_daily(
    official_daily: pd.DataFrame,
    calendar: list[str],
) -> pd.DataFrame:
    daily = normalize_daily_membership(official_daily)
    calendar_positions = {date: position for position, date in enumerate(calendar)}
    if missing := set(daily["trade_date"]) - set(calendar_positions):
        raise GateFailure(f"official membership dates absent from qlib calendar: {len(missing)}")
    spans: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for code, group in daily.groupby("code", sort=True):
        positions = sorted(calendar_positions[date] for date in group["trade_date"])
        start = previous = positions[0]
        for position in positions[1:]:
            if position == previous + 1:
                previous = position
                continue
            spans[str(code)].append((start, previous))
            start = previous = position
        spans[str(code)].append((start, previous))
    rows = [
        {
            "instrument": qlib_code(code),
            "start": calendar[start],
            "end": calendar[end],
        }
        for code, ranges in spans.items()
        for start, end in ranges
    ]
    return pd.DataFrame(rows).sort_values(["instrument", "start"]).reset_index(drop=True)


def _write_lines(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_qlib_payload(
    output_root: Path,
    market: pd.DataFrame,
    index_daily: pd.DataFrame,
    official_daily: pd.DataFrame,
    calendar: list[str],
    instrument_id: str,
) -> None:
    output_root.mkdir(parents=True, exist_ok=False)
    _write_lines(output_root / "calendars/day.txt", calendar)
    calendar_index = pd.Index(calendar)
    instrument_lines: list[str] = []
    seen: set[str] = set()
    benchmark = benchmark_frame(index_daily)
    for source in (market, benchmark):
        for ts_code, frame in source.groupby("ts_code", sort=True):
            code = qlib_code(str(ts_code))
            if code in seen:
                raise GateFailure(f"duplicate qlib instrument: {code}")
            seen.add(code)
            frame = frame.copy()
            frame["trade_date"] = frame["trade_date"].astype("string")
            frame = frame.loc[frame["trade_date"].isin(calendar_index)].sort_values("trade_date")
            if frame.empty:
                continue
            if frame["trade_date"].duplicated().any():
                raise GateFailure(f"duplicate qlib date for {code}")
            first = int(calendar_index.get_loc(frame["trade_date"].iloc[0]))
            last = int(calendar_index.get_loc(frame["trade_date"].iloc[-1]))
            aligned_dates = calendar_index[first : last + 1]
            aligned = frame.set_index("trade_date").reindex(aligned_dates)
            feature_dir = output_root / "features" / code.lower()
            feature_dir.mkdir(parents=True)
            for field in QLIB_FIELDS:
                values = pd.to_numeric(aligned[field], errors="coerce").to_numpy(dtype="float32")
                np.concatenate([np.array([first], dtype="<f4"), values.astype("<f4")]).tofile(
                    feature_dir / f"{field}.day.bin"
                )
            instrument_lines.append(f"{code}\t{aligned_dates[0]}\t{aligned_dates[-1]}")
    _write_lines(output_root / "instruments/all.txt", sorted(instrument_lines))
    intervals = membership_intervals_from_daily(official_daily, calendar)
    _write_lines(
        output_root / f"instruments/{instrument_id}.txt",
        [f"{row.instrument}\t{row.start}\t{row.end}" for row in intervals.itertuples(index=False)],
    )


def build_or_reuse_qlib(dataset: dict[str, Any]) -> dict[str, Any]:
    protocol = dataset["protocol"]
    provider = PROJECT_ROOT / protocol["identity"]["qlib_provider"]
    code_snapshot_sha256 = canonical_sha256(
        {
            path.name: sha256_file(path)
            for path in (
                Path(__file__),
                Path(__file__).with_name("contract.py"),
                PROJECT_ROOT / "src/shaiwei/transform/qlib_bin.py",
                PROJECT_ROOT / "src/shaiwei/transform/market.py",
            )
        }
    )
    identity = {
        "schema_version": "p2-star50-qlib-manifest-v1",
        "dataset_id": protocol["identity"]["dataset_id"],
        "instrument_id": protocol["identity"]["instrument_id"],
        "benchmark_source_code": protocol["identity"]["benchmark_source_code"],
        "protocol_sha256": sha256_file(PROJECT_ROOT / "config/p2_star50_engineering_v1.yaml"),
        "data_snapshot_sha256": dataset["data_snapshot_sha256"],
        "code_snapshot_sha256": code_snapshot_sha256,
        "strategy_results_inspected": False,
        "production_authorization": "none",
    }
    identity_sha256 = canonical_sha256(identity)
    manifest_path = provider / QLIB_MANIFEST
    if provider.exists():
        if not manifest_path.is_file():
            raise GateFailure("P2-1 qlib provider exists without an immutable manifest")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("build_identity_sha256") != identity_sha256:
            raise GateFailure("P2-1 qlib provider belongs to a different frozen input")
        integrity = qlib_tree_integrity(provider)
        if any(manifest.get(key) != value for key, value in integrity.items()):
            raise GateFailure("P2-1 qlib provider failed content integrity verification")
        return {
            **integrity,
            "build_identity_sha256": identity_sha256,
            "provider_reused": True,
            "qlib_complete": True,
        }

    staging = provider.with_name(f".{provider.name}.building.{uuid.uuid4().hex}")
    try:
        _write_qlib_payload(
            staging,
            dataset["market"],
            dataset["index_daily"],
            dataset["official"],
            dataset["calendar"],
            protocol["identity"]["instrument_id"],
        )
        integrity = qlib_tree_integrity(staging)
        manifest = {
            **identity,
            **integrity,
            "build_identity_sha256": identity_sha256,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        (staging / QLIB_MANIFEST).write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        provider.parent.mkdir(parents=True, exist_ok=True)
        os.replace(staging, provider)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return {
        **integrity,
        "build_identity_sha256": identity_sha256,
        "provider_reused": False,
        "qlib_complete": True,
    }
