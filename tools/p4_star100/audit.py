"""Audit the frozen Star100 official-lineage and source-data gate."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

from bs4 import BeautifulSoup
import pandas as pd
import yaml

from shaiwei.config import PROJECT_ROOT
from shaiwei.ingest.catalog import load_latest_api
from tools.p4_star100.contract import (
    INDEX_CODE,
    PROTOCOL_PATH,
    canonical_frame_sha256,
    sha256_file,
    tool_snapshot_sha256,
    write_immutable_json,
)

PARSER_VERSION = "star100-data-audit-v1"
PROVIDER_CODE = "000698"
SECURITY_RE = re.compile(r"(?:688|689)\d{3}")


class Star100AuditError(RuntimeError):
    """Raised when captured evidence is internally inconsistent."""


def _canonical_frame_sha256(frame: pd.DataFrame, columns: list[str]) -> str:
    rendered = frame.loc[:, columns].sort_values(columns, kind="stable").to_csv(
        index=False,
        lineterminator="\n",
    )
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _source_path(raw_root: Path, source: dict[str, object]) -> Path:
    path = raw_root / str(source["stored_name"])
    if not path.is_file():
        raise Star100AuditError(f"official source is missing: {path.name}")
    if sha256_file(path) != source["source_file_sha256"]:
        raise Star100AuditError(f"official source hash mismatch: {path.name}")
    return path


def _compact(value: str) -> str:
    return re.sub(r"\s+", "", value)


def _html_text(path: Path) -> str:
    return BeautifulSoup(path.read_bytes(), "html.parser").get_text(" ", strip=True)


def _pdf_text(path: Path) -> str:
    from pypdf import PdfReader  # Docker-only runtime dependency; keep host imports light.

    reader = PdfReader(path)
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    if not text.strip():
        raise Star100AuditError(f"official PDF has no extractable text: {path.name}")
    return text


def _word_text(path: Path) -> str:
    try:
        with ZipFile(path) as archive:
            document = archive.read("word/document.xml")
    except (BadZipFile, KeyError) as exc:
        raise Star100AuditError(
            f"official WPS/DOCX attachment is not OOXML: {path.name}"
        ) from exc
    root = ElementTree.fromstring(document)
    return " ".join(node.text or "" for node in root.iter() if node.tag.endswith("}t"))


def _xlsx_text(path: Path) -> str:
    book = pd.ExcelFile(path)
    values = []
    for sheet in book.sheet_names:
        frame = pd.read_excel(path, sheet_name=sheet, header=None)
        values.extend(frame.fillna("").astype(str).to_numpy().ravel().tolist())
    return " ".join(values)


def _material_text(path: Path) -> str:
    if path.suffix.lower() in {".html", ".shtml"}:
        return _html_text(path)
    if path.suffix.lower() == ".pdf":
        return _pdf_text(path)
    if path.suffix.lower() in {".wps", ".docx"}:
        return _word_text(path)
    if path.suffix.lower() in {".xls", ".xlsx"}:
        return _xlsx_text(path)
    raise Star100AuditError(f"unsupported official material: {path.name}")


def _normalized_code(value: object) -> str | None:
    if pd.isna(value):
        return None
    rendered = str(value).strip().split(".")[0].zfill(6)
    return f"{rendered}.SH" if SECURITY_RE.fullmatch(rendered) else None


def parse_initial_xlsx(path: Path) -> list[str]:
    book = pd.ExcelFile(path)
    candidates: list[list[str]] = []
    for sheet in book.sheet_names:
        frame = pd.read_excel(path, sheet_name=sheet)
        index_columns = [column for column in frame if "指数代码" in str(column)]
        security_columns = [column for column in frame if "证券代码" in str(column)]
        if len(index_columns) != 1 or len(security_columns) != 1:
            continue
        index_values = frame[index_columns[0]].map(
            lambda value: str(value).strip().split(".")[0].zfill(6)
        )
        selected = frame.loc[index_values.eq(PROVIDER_CODE)]
        codes = [_normalized_code(value) for value in selected[security_columns[0]]]
        members = [code for code in codes if code is not None]
        if members:
            candidates.append(members)
    if len(candidates) != 1:
        raise Star100AuditError("initial workbook has no unique 000698 member table")
    members = candidates[0]
    if len(members) != 100 or len(set(members)) != 100:
        raise Star100AuditError(
            f"initial official member count is not 100: rows={len(members)}, "
            f"unique={len(set(members))}"
        )
    return sorted(members)


def _open_dates(calendar: pd.DataFrame, start: str, end: str) -> list[str]:
    rows = calendar.loc[
        calendar["exchange"].astype(str).eq("SSE")
        & pd.to_numeric(calendar["is_open"], errors="coerce").eq(1)
    ]
    dates = rows["cal_date"].astype(str)
    return sorted(set(dates.loc[dates.between(start, end)]))


def _months(start: str, end: str) -> list[str]:
    return [item.strftime("%Y-%m") for item in pd.period_range(start, end, freq="M")]


def _month_label(values: pd.Series) -> pd.Series:
    return pd.to_datetime(values.astype(str), format="%Y%m%d").dt.strftime("%Y-%m")


def _set_changes(weights: pd.DataFrame) -> list[dict[str, object]]:
    by_date = {
        day: set(group["con_code"].dropna().astype(str))
        for day, group in weights.groupby("trade_date", sort=True)
    }
    changes = []
    dates = sorted(by_date)
    for prior, current in zip(dates, dates[1:], strict=False):
        outgoing = sorted(by_date[prior] - by_date[current])
        incoming = sorted(by_date[current] - by_date[prior])
        if outgoing or incoming:
            changes.append(
                {
                    "prior_snapshot_date": prior,
                    "current_snapshot_date": current,
                    "out_count": len(outgoing),
                    "in_count": len(incoming),
                    "balanced": len(outgoing) == len(incoming),
                    "role": "TUSHARE_SECONDARY_NOT_FOR_VERDICT",
                }
            )
    return changes


def _write_initial_set(path: Path, frame: pd.DataFrame) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if not pd.read_parquet(path).equals(frame):
            raise Star100AuditError(f"immutable initial-set artifact differs: {path}")
        return False
    frame.to_parquet(path, index=False)
    return True


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--collection-report", type=Path, required=True)
    parser.add_argument("--discovery-report", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--manifest", type=Path)
    return parser.parse_args(argv)


def _project_path(path: Path) -> Path:
    return path if path.is_absolute() else PROJECT_ROOT / path


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    protocol = yaml.safe_load(PROTOCOL_PATH.read_text(encoding="utf-8"))
    protocol_sha256 = sha256_file(PROTOCOL_PATH)
    collection_path = _project_path(args.collection_report)
    discovery_path = _project_path(args.discovery_report)
    collection = json.loads(collection_path.read_text(encoding="utf-8"))
    discovery = json.loads(discovery_path.read_text(encoding="utf-8"))
    if collection.get("protocol_sha256") != protocol_sha256:
        raise Star100AuditError("collection report is bound to another protocol")
    if discovery.get("protocol_sha256") != protocol_sha256:
        raise Star100AuditError("official discovery is bound to another protocol")

    raw_root = PROJECT_ROOT / str(protocol["identity"]["raw_source_root"])
    sources = list(discovery["sources"])
    for source in sources:
        _source_path(raw_root, source)
    launch_url = str(protocol["official_source_policy"]["launch_announcement_url"])
    revision_url = str(protocol["official_source_policy"]["methodology_revision_url"])
    launch_page = next(
        source
        for source in sources
        if source["source_url"] == launch_url and source["purpose"] == "launch_publication"
    )
    revision_page = next(
        source
        for source in sources
        if source["source_url"] == revision_url and source["purpose"] == "methodology_revision"
    )
    launch_attachments = [source for source in sources if source.get("parent_url") == launch_url]
    launch_workbooks = [
        source for source in launch_attachments if str(source["stored_name"]).endswith(".xlsx")
    ]
    if len(launch_workbooks) != 1:
        raise Star100AuditError("official launch member workbook is missing or ambiguous")
    launch_member_source = launch_workbooks[0]
    members = parse_initial_xlsx(_source_path(raw_root, launch_member_source))
    launch_page_text = _compact(_html_text(_source_path(raw_root, launch_page)))
    revision_page_text = _compact(_html_text(_source_path(raw_root, revision_page)))

    methodology_texts = []
    for source in sources:
        if source["purpose"] != "official_attachment" or not str(
            source["stored_name"]
        ).endswith(".pdf"):
            continue
        text = _compact(_pdf_text(_source_path(raw_root, source)))
        if "上证科创板100指数编制方案" in text and "指数代码：000698" in text:
            methodology_texts.append((source, text))
    launch_methods = [item for item in methodology_texts if "版本号V1.0" in item[1]]
    current_methods = [item for item in methodology_texts if "版本号V1.1" in item[1]]
    methodology_checks = {
        "launch_page_live_date": "2023年8月7日正式发布" in launch_page_text,
        "launch_v1_0_rule": len(launch_methods) == 1 and "上市时间超过6个月" in launch_methods[0][1],
        "revision_page_effective_date": "2025年3月17日实施" in revision_page_text,
        "revision_page_grandfathering": "新老样本划断" in revision_page_text,
        "current_v1_1_rule": len(current_methods) == 1 and "上市时间超过12个月" in current_methods[0][1],
    }

    classified_pages = list(discovery["classified_pages"])
    quarterly_pages = [
        page
        for page in classified_pages
        if page["purpose"] == "adjustment_candidate" and "定期调整结果" in str(page["title"])
    ]
    quarterly_urls = {str(page["source_url"]) for page in quarterly_pages}
    quarterly_attachments = [
        source
        for source in sources
        if source["purpose"] == "official_attachment"
        and str(source.get("parent_url")) in quarterly_urls
    ]
    parsed_quarterly_attachment_count = 0
    star100_pair_materials = []
    for source in quarterly_attachments:
        text = _compact(_material_text(_source_path(raw_root, source)))
        parsed_quarterly_attachment_count += 1
        if "科创100" in text or "上证科创板100" in text or "000698" in text:
            star100_pair_materials.append(source)

    daily = load_latest_api("tushare.index_daily")
    daily = daily.loc[daily["ts_code"].astype(str).eq(INDEX_CODE)].copy()
    weights = load_latest_api("tushare.index_weight")
    weights = weights.loc[weights["index_code"].astype(str).eq(INDEX_CODE)].copy()
    calendar = load_latest_api("tushare.trade_cal")
    stock_basic = load_latest_api("tushare.stock_basic")
    daily["trade_date"] = daily["trade_date"].astype(str)
    weights["trade_date"] = weights["trade_date"].astype(str)

    expected_dates = _open_dates(calendar, "20230807", args.end_date)
    observed_dates = set(daily["trade_date"])
    missing_dates = sorted(set(expected_dates) - observed_dates)
    extra_dates = sorted(observed_dates - set(expected_dates))
    daily_duplicates = int(daily.duplicated(["ts_code", "trade_date"]).sum())
    numeric = {
        column: pd.to_numeric(daily[column], errors="coerce")
        for column in (
            "open",
            "high",
            "low",
            "close",
            "pre_close",
            "change",
            "pct_chg",
            "vol",
            "amount",
        )
    }
    required_numeric_missing = int(
        pd.DataFrame(numeric).isna().any(axis=1).sum()
    )
    daily_invalid = int(
        (
            numeric["high"].lt(numeric["low"])
            | numeric["high"].lt(numeric["open"])
            | numeric["high"].lt(numeric["close"])
            | numeric["low"].gt(numeric["open"])
            | numeric["low"].gt(numeric["close"])
            | numeric["vol"].lt(0)
            | numeric["amount"].lt(0)
        ).sum()
    ) + required_numeric_missing
    recomputed_pct = (numeric["close"] / numeric["pre_close"] - 1.0) * 100.0
    pct_mismatches = int(
        (
            numeric["pre_close"].gt(0)
            & recomputed_pct.sub(numeric["pct_chg"]).abs().gt(0.02)
        ).sum()
    )

    expected_months = _months("2023-08", "2026-06")
    weights["month"] = _month_label(weights["trade_date"])
    observed_completed = weights.loc[weights["month"].isin(expected_months)].copy()
    snapshots = (
        observed_completed.groupby(["month", "trade_date"], sort=True)
        .agg(
            row_count=("con_code", "size"),
            constituent_count=("con_code", "nunique"),
            weight_sum=("weight", lambda values: float(pd.to_numeric(values, errors="coerce").sum())),
        )
        .reset_index()
    )
    snapshot_counts = snapshots.groupby("month")["trade_date"].nunique().to_dict()
    missing_months = sorted(set(expected_months) - set(snapshot_counts))
    multi_snapshot_months = sorted(month for month, count in snapshot_counts.items() if count != 1)
    bad_snapshot_rows = snapshots.loc[
        snapshots["row_count"].ne(100) | snapshots["constituent_count"].ne(100)
    ]
    weight_duplicates = int(
        observed_completed.duplicated(["index_code", "con_code", "trade_date"]).sum()
    )
    bse_rows = int(
        observed_completed["con_code"].astype("string").str.endswith(".BJ", na=False).sum()
    )
    known_codes = set(stock_basic["ts_code"].dropna().astype(str))
    unknown_codes = sorted(
        set(observed_completed["con_code"].dropna().astype(str)) - known_codes
    )

    first_snapshot_date = snapshots["trade_date"].min() if not snapshots.empty else None
    first_snapshot_members = set(
        observed_completed.loc[
            observed_completed["trade_date"].eq(first_snapshot_date), "con_code"
        ].astype(str)
    )
    launch_crosscheck = set(members) == first_snapshot_members
    secondary_changes = _set_changes(observed_completed)
    unresolved_change_count = len(secondary_changes) if not star100_pair_materials else 0

    initial_frame = pd.DataFrame(
        [
            {
                "code": code,
                "source_url": launch_member_source["source_url"],
                "source_file_sha256": launch_member_source["source_file_sha256"],
                "retrieved_at": launch_member_source["retrieved_at"],
                "parser_version": PARSER_VERSION,
            }
            for code in members
        ]
    )
    initial_path = PROJECT_ROOT / str(protocol["identity"]["initial_set_artifact"])
    _write_initial_set(initial_path, initial_frame)

    source_checks = {
        "collection_double_query_stability": collection.get("revision_mismatch_count") == 0,
        "daily_full_calendar_coverage": not missing_dates and not extra_dates,
        "daily_duplicate_keys": daily_duplicates == 0,
        "daily_ohlc_and_nonnegative": daily_invalid == 0,
        "daily_pct_change": pct_mismatches == 0,
        "monthly_snapshot_coverage": not missing_months and not multi_snapshot_months,
        "monthly_snapshot_shape": bad_snapshot_rows.empty,
        "monthly_duplicate_keys": weight_duplicates == 0,
        "bse_exclusion": bse_rows == 0,
    }
    official_launch_set_complete = len(members) == 100 and len(set(members)) == 100
    methodology_lineage_complete = all(methodology_checks.values())
    tushare_source_collection_pass = all(source_checks.values())
    official_adjustment_lineage_complete = (
        len(quarterly_pages) == 12
        and unresolved_change_count == 0
        and bool(star100_pair_materials)
    )
    tushare_crosscheck_pass = False
    pit_constructible = (
        official_launch_set_complete
        and methodology_lineage_complete
        and official_adjustment_lineage_complete
        and tushare_crosscheck_pass
    )
    blocking_checks = [
        name
        for name, passed in {
            "official_launch_set_complete": official_launch_set_complete,
            "official_adjustment_lineage_complete": official_adjustment_lineage_complete,
            "methodology_lineage_complete": methodology_lineage_complete,
            "tushare_source_collection_pass": tushare_source_collection_pass,
            "tushare_crosscheck_pass": tushare_crosscheck_pass,
            "pit_constructible": pit_constructible,
        }.items()
        if not passed
    ]
    verdict = "GO_OFFICIAL_LINEAGE_AND_SOURCE_DATA_ONLY" if not blocking_checks else "NO_GO"
    payload = {
        "schema_version": "p4-star100-quality-v1",
        "protocol_sha256": protocol_sha256,
        "tool_snapshot_sha256": tool_snapshot_sha256(),
        "collection_report_sha256": sha256_file(collection_path),
        "collection_ingest_snapshot_sha256": collection["ingest_snapshot_sha256"],
        "official_discovery_report_sha256": sha256_file(discovery_path),
        "official_retrieval_index_sha256": sha256_file(raw_root / "retrieval_index.json"),
        "index_code": INDEX_CODE,
        "scope": protocol["scope"],
        "official": {
            "archive_scan_crossed_launch_boundary": discovery["archive_scan_crossed_launch_boundary"],
            "archive_page_count": discovery["archive_page_count"],
            "candidate_page_count": discovery["candidate_page_count"],
            "attachment_count": discovery["attachment_count"],
            "launch_member_count": len(members),
            "launch_member_unique_count": len(set(members)),
            "launch_member_bse_count": sum(code.endswith(".BJ") for code in members),
            "launch_page_sha256": launch_page["source_file_sha256"],
            "launch_workbook_sha256": launch_member_source["source_file_sha256"],
            "initial_set_artifact_sha256": sha256_file(initial_path),
            "initial_set_canonical_sha256": _canonical_frame_sha256(
                initial_frame, list(initial_frame.columns)
            ),
            "methodology_checks": methodology_checks,
            "quarterly_notice_count": len(quarterly_pages),
            "quarterly_attachment_count": len(quarterly_attachments),
            "parsed_quarterly_attachment_count": parsed_quarterly_attachment_count,
            "star100_membership_pair_material_count": len(star100_pair_materials),
            "star100_membership_pair_material_sha256": [
                source["source_file_sha256"] for source in star100_pair_materials
            ],
            "adjustment_lineage_status": "INCOMPLETE_HISTORICAL_PAIR_FILES_NOT_IN_CAPTURED_ARCHIVE",
        },
        "daily": {
            "row_count": len(daily),
            "min_trade_date": daily["trade_date"].min() if not daily.empty else None,
            "max_trade_date": daily["trade_date"].max() if not daily.empty else None,
            "official_trade_date_count": len(expected_dates),
            "missing_trade_date_count": len(missing_dates),
            "missing_trade_dates": missing_dates,
            "extra_noncalendar_date_count": len(extra_dates),
            "extra_noncalendar_dates": extra_dates,
            "duplicate_key_count": daily_duplicates,
            "invalid_ohlc_or_nonnegative_count": daily_invalid,
            "pct_change_mismatch_count": pct_mismatches,
            "canonical_sha256": canonical_frame_sha256("index_daily", daily),
        },
        "weights": {
            "row_count": len(observed_completed),
            "expected_completed_month_count": len(expected_months),
            "observed_completed_month_count": len(snapshot_counts),
            "snapshot_count": len(snapshots),
            "missing_months": missing_months,
            "multi_snapshot_months": multi_snapshot_months,
            "snapshot_shape_violation_count": len(bad_snapshot_rows),
            "row_count_minimum": int(snapshots["row_count"].min()) if not snapshots.empty else 0,
            "row_count_maximum": int(snapshots["row_count"].max()) if not snapshots.empty else 0,
            "constituent_count_minimum": int(snapshots["constituent_count"].min()) if not snapshots.empty else 0,
            "constituent_count_maximum": int(snapshots["constituent_count"].max()) if not snapshots.empty else 0,
            "weight_sum_minimum_not_for_verdict": float(snapshots["weight_sum"].min()) if not snapshots.empty else None,
            "weight_sum_maximum_not_for_verdict": float(snapshots["weight_sum"].max()) if not snapshots.empty else None,
            "duplicate_key_count": weight_duplicates,
            "bse_row_count": bse_rows,
            "unknown_constituent_count_not_for_verdict": len(unknown_codes),
            "unknown_constituents_not_for_verdict": unknown_codes,
            "launch_to_first_snapshot_exact_match": launch_crosscheck,
            "secondary_set_change_interval_count": len(secondary_changes),
            "secondary_set_changes": secondary_changes,
            "unresolved_change_interval_count": unresolved_change_count,
            "canonical_sha256": canonical_frame_sha256(
                "index_weight", observed_completed.drop(columns=["month"])
            ),
        },
        "source_checks": source_checks,
        "crosscheck_status": "NOT_EVALUABLE_WITHOUT_OFFICIAL_DAILY_LINEAGE",
        "blocking_checks": blocking_checks,
        "official_launch_set_complete": official_launch_set_complete,
        "official_adjustment_lineage_complete": official_adjustment_lineage_complete,
        "methodology_lineage_complete": methodology_lineage_complete,
        "tushare_source_collection_pass": tushare_source_collection_pass,
        "tushare_crosscheck_pass": tushare_crosscheck_pass,
        "pit_constructible": pit_constructible,
        "engineering_complete": False,
        "strategy_results_inspected": False,
        "strategy_effective": "NOT_EVALUATED",
        "production_authorization": "none",
        "verdict": verdict,
    }
    report_path = _project_path(args.report)
    created = write_immutable_json(report_path, payload)
    manifest_path = _project_path(
        args.manifest
        or Path(str(protocol["identity"]["tracked_manifest"]))
    )
    public_source_fields = (
        "source_url",
        "final_url",
        "source_file_sha256",
        "byte_count",
        "media_type",
        "retrieved_at",
        "purpose",
        "parent_url",
        "title",
    )
    manifest = {
        "schema_version": "p4-star100-tracked-manifest-v1",
        "index_code": INDEX_CODE,
        "scope": protocol["scope"],
        "verdict": verdict,
        "protocol": {
            "path": str(PROTOCOL_PATH.relative_to(PROJECT_ROOT)),
            "sha256": protocol_sha256,
        },
        "immutable_evidence": {
            "collection_report": {
                "path": str(collection_path.relative_to(PROJECT_ROOT)),
                "sha256": sha256_file(collection_path),
                "tool_snapshot_sha256": collection["tool_snapshot_sha256"],
                "ingest_snapshot_sha256": collection["ingest_snapshot_sha256"],
            },
            "official_discovery_report": {
                "path": str(discovery_path.relative_to(PROJECT_ROOT)),
                "sha256": sha256_file(discovery_path),
                "tool_snapshot_sha256": discovery["tool_snapshot_sha256"],
            },
            "official_retrieval_index": {
                "path": str((raw_root / "retrieval_index.json").relative_to(PROJECT_ROOT)),
                "sha256": sha256_file(raw_root / "retrieval_index.json"),
            },
            "initial_set": {
                "path": str(initial_path.relative_to(PROJECT_ROOT)),
                "sha256": sha256_file(initial_path),
                "canonical_sha256": payload["official"]["initial_set_canonical_sha256"],
            },
            "quality_report": {
                "path": str(report_path.relative_to(PROJECT_ROOT)),
                "sha256": sha256_file(report_path),
                "tool_snapshot_sha256": payload["tool_snapshot_sha256"],
            },
        },
        "official_sources": [
            {key: source.get(key) for key in public_source_fields}
            for source in sorted(sources, key=lambda item: str(item["source_url"]))
        ],
        "desensitization": {
            "absolute_paths_included": False,
            "credentials_included": False,
            "cookies_or_headers_included": False,
            "provider_token_included": False,
            "raw_business_rows_included": False,
        },
    }
    manifest_created = write_immutable_json(manifest_path, manifest)
    print(
        json.dumps(
            {
                "verdict": verdict,
                "source_collection_pass": tushare_source_collection_pass,
                "official_launch_set_complete": official_launch_set_complete,
                "official_adjustment_lineage_complete": official_adjustment_lineage_complete,
                "pit_constructible": pit_constructible,
                "blocking_checks": blocking_checks,
                "report": str(report_path.relative_to(PROJECT_ROOT)),
                "report_created": created,
                "manifest": str(manifest_path.relative_to(PROJECT_ROOT)),
                "manifest_created": manifest_created,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if verdict.startswith("GO_") else 2


if __name__ == "__main__":
    raise SystemExit(main())
