"""Audit official membership lineage and secondary provider evidence without strategy results."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from shaiwei.config import PROJECT_ROOT
from shaiwei.ingest.catalog import load_latest_api
from shaiwei.provenance import git_head
from tools.official_index_lineage.contract import (
    DataGateError,
    load_protocol,
    sha256_file,
    tool_snapshot_sha256,
    write_immutable_json,
)
from tools.official_index_lineage.parsers import (
    PARSER_VERSION,
    html_text,
    material_text,
    methodology_checks,
    parse_adjustment_material,
    parse_effective_date,
    parse_initial_xlsx,
    parse_page_date,
    pdf_text,
    source_path,
)
from tools.official_index_lineage.quality import (
    daily_quality,
    months,
    open_dates,
    weight_quality,
)

DEFAULT_PROTOCOL = PROJECT_ROOT / "config" / "m2_star200_v1.yaml"


def _canonical_sha256(payload: object) -> str:
    rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _frame_hash(frame: pd.DataFrame, columns: list[str]) -> str:
    rendered = frame.loc[:, columns].sort_values(columns, kind="stable").to_csv(
        index=False, lineterminator="\n"
    )
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _write_parquet_immutable(path: Path, frame: pd.DataFrame) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if not pd.read_parquet(path).equals(frame):
            raise DataGateError(f"immutable artifact differs: {path}")
        return False
    frame.to_parquet(path, index=False)
    return True


def _project(path: Path | str) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else PROJECT_ROOT / candidate


def _parse_events(
    sources: list[dict[str, object]],
    raw_root: Path,
    open_dates: list[str],
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[str]]:
    pages = [source for source in sources if source["purpose"] == "adjustment_candidate"]
    attachments: dict[str, list[dict[str, object]]] = {}
    for source in sources:
        if source["purpose"] == "official_attachment":
            attachments.setdefault(str(source["parent_url"]), []).append(source)
    events: list[dict[str, object]] = []
    checks = []
    errors = []
    for page in sorted(pages, key=lambda item: str(item["source_url"])):
        url = str(page["source_url"])
        page_path = source_path(raw_root, page)
        parsed = []
        relevant_unparsed = []
        for source in attachments.get(url, []):
            path = source_path(raw_root, source)
            try:
                material = parse_adjustment_material(path, "000699")
                if material is not None:
                    parsed.append((material, source))
                elif "科创200" in material_text(path).replace("板", "") or "000699" in material_text(path):
                    relevant_unparsed.append(str(source["source_file_sha256"]))
            except DataGateError as error:
                errors.append(f"{url}: {error}")
        distinct = {(item.pairs, item.explicit_no_change) for item, _ in parsed}
        if len(distinct) > 1:
            errors.append(f"{url}: official attachments disagree")
            continue
        if relevant_unparsed:
            errors.append(f"{url}: relevant official attachment was not parsed")
        if not parsed:
            checks.append({"source_url": url, "star200_material": False})
            continue
        material, source = parsed[0]
        try:
            effective = parse_effective_date(html_text(page_path), open_dates)
            announcement = parse_page_date(url)
            if announcement > effective.effective_date:
                raise DataGateError("announcement date is after effective date")
            for out_code, in_code in material.pairs:
                events.append(
                    {
                        "announcement_date": announcement,
                        "effective_date": effective.effective_date,
                        "official_reference_date": effective.official_reference_date,
                        "timing": effective.timing,
                        "event_type": "regular_adjustment",
                        "out_code": f"{out_code}.SH",
                        "in_code": f"{in_code}.SH",
                        "source_url": source["source_url"],
                        "source_file_sha256": source["source_file_sha256"],
                        "retrieved_at": source["retrieved_at"],
                        "parser_version": PARSER_VERSION,
                    }
                )
            checks.append(
                {
                    "source_url": url,
                    "star200_material": True,
                    "explicit_no_change": material.explicit_no_change,
                    "replacement_count": len(material.pairs),
                    "effective_date": effective.effective_date,
                }
            )
        except DataGateError as error:
            errors.append(f"{url}: {error}")
    return events, checks, errors


def _build_membership(
    initial: set[str],
    events: list[dict[str, object]],
    open_dates: list[str],
) -> tuple[dict[str, set[str]], list[str]]:
    grouped: dict[str, list[dict[str, object]]] = {}
    for event in events:
        grouped.setdefault(str(event["effective_date"]), []).append(event)
    members = set(initial)
    daily = {}
    errors = []
    for trade_date in open_dates:
        for event in grouped.get(trade_date, []):
            out_code, in_code = str(event["out_code"]), str(event["in_code"])
            if out_code not in members or in_code in members:
                errors.append(f"invalid replacement on {trade_date}: {out_code}->{in_code}")
                continue
            members.remove(out_code)
            members.add(in_code)
        if len(members) != 200:
            errors.append(f"member count on {trade_date} is {len(members)}")
        daily[trade_date] = set(members)
    return daily, errors


def _source_public(source: dict[str, object]) -> dict[str, object]:
    keys = ("source_url", "final_url", "source_file_sha256", "byte_count", "media_type", "retrieved_at", "purpose", "parent_url", "title")
    return {key: source.get(key) for key in keys}


def audit(
    protocol_path: Path,
    collection_path: Path,
    discovery_path: Path,
    *,
    report_override: Path | None = None,
    manifest_override: Path | None = None,
) -> dict[str, object]:
    protocol = load_protocol(protocol_path)
    collection = json.loads(collection_path.read_text(encoding="utf-8"))
    discovery = json.loads(discovery_path.read_text(encoding="utf-8"))
    config_hash = sha256_file(protocol_path)
    if collection.get("protocol_config_sha256") != config_hash or discovery.get("protocol_config_sha256") != config_hash:
        raise DataGateError("evidence is bound to another protocol config")
    sources = list(discovery["sources"])
    raw_root = PROJECT_ROOT / str(protocol["identity"]["raw_source_root"])
    for source in sources:
        source_path(raw_root, source)

    by_purpose: dict[str, list[dict[str, object]]] = {}
    for source in sources:
        by_purpose.setdefault(str(source["purpose"]), []).append(source)
    required_single = ("launch_publication", "launch_methodology", "launch_members", "methodology_revision", "current_methodology")
    if any(len(by_purpose.get(purpose, [])) != 1 for purpose in required_single):
        raise DataGateError("required official launch/methodology source is missing or ambiguous")
    launch_page = by_purpose["launch_publication"][0]
    launch_method = by_purpose["launch_methodology"][0]
    launch_members = by_purpose["launch_members"][0]
    revision_page = by_purpose["methodology_revision"][0]
    current_method = by_purpose["current_methodology"][0]
    members = parse_initial_xlsx(source_path(raw_root, launch_members), "000699", 200)
    launch_text = html_text(source_path(raw_root, launch_page))
    method_checks = methodology_checks(
        pdf_text(source_path(raw_root, launch_method)),
        html_text(source_path(raw_root, revision_page)),
        pdf_text(source_path(raw_root, current_method)),
    )
    launch_checks = {
        "official_live_date": "2024年8月20日正式发布" in launch_text.replace(" ", ""),
        "initial_member_count": len(members),
        "initial_unique_count": len(set(members)),
        "initial_bse_count": sum(item.endswith(".BJ") for item in members),
    }

    daily = load_latest_api("tushare.index_daily")
    daily = daily.loc[daily["ts_code"].astype(str).eq("000699.SH")].copy()
    weights = load_latest_api("tushare.index_weight")
    weights = weights.loc[weights["index_code"].astype(str).eq("000699.SH")].copy()
    calendar = load_latest_api("tushare.trade_cal")
    stock_basic = load_latest_api("tushare.stock_basic")
    daily["trade_date"] = daily["trade_date"].astype(str)
    start = str(protocol["tushare_source_contract"]["index_daily_start"]).replace("-", "")
    end = str(protocol["tushare_source_contract"]["index_daily_end"]).replace("-", "")
    open_dates_value = open_dates(calendar, start, end)
    daily_quality_result = daily_quality(daily, open_dates_value)
    expected_months = months(
        str(protocol["tushare_source_contract"]["index_weight_completed_month_start"]),
        str(protocol["tushare_source_contract"]["index_weight_completed_month_end"]),
    )
    weight_quality_result, snapshots = weight_quality(
        weights, expected_months, set(stock_basic["ts_code"].dropna().astype(str))
    )
    events, event_checks, parse_errors = _parse_events(sources, raw_root, open_dates_value)
    daily_members, membership_errors = _build_membership(
        {f"{item}.SH" for item in members}, events, open_dates_value
    )
    comparisons = []
    for month in expected_months:
        if month not in snapshots:
            continue
        trade_date, rows = snapshots[month]
        official = daily_members.get(trade_date, set())
        secondary = set(rows)
        comparisons.append(
            {
                "month": month,
                "trade_date": trade_date,
                "official_count": len(official),
                "tushare_row_count": len(rows),
                "tushare_unique_count": len(secondary),
                "official_only_count": len(official - secondary),
                "tushare_only_count": len(secondary - official),
                "official_only": sorted(official - secondary),
                "tushare_only": sorted(secondary - official),
                "exact_match": official == secondary and len(official) == 200 and len(rows) == 200,
            }
        )
    source_pass = (
        daily_quality_result["coverage"] == 1.0
        and not daily_quality_result["missing_trade_dates"]
        and not daily_quality_result["non_calendar_trade_dates"]
        and daily_quality_result["duplicate_key_count"] == 0
        and daily_quality_result["ohlc_or_nonnegative_violation_count"] == 0
        and daily_quality_result["pct_change_mismatch_count"] == 0
        and weight_quality_result["observed_completed_month_count"] == 24
        and not weight_quality_result["missing_months"]
        and not weight_quality_result["multi_snapshot_months"]
        and weight_quality_result["bad_snapshot_size_count"] == 0
        and weight_quality_result["duplicate_key_count"] == 0
        and weight_quality_result["bse_row_count"] == 0
        and weight_quality_result["unknown_code_count"] == 0
        and collection["revision_mismatch_count"] == 0
    )
    launch_complete = all((launch_checks["official_live_date"], launch_checks["initial_member_count"] == 200, launch_checks["initial_unique_count"] == 200, launch_checks["initial_bse_count"] == 0))
    method_complete = all(method_checks.values())
    crosscheck_pass = len(comparisons) == 24 and all(item["exact_match"] for item in comparisons)
    lineage_complete = bool(discovery["archive_boundary_crossed"] and not parse_errors and not membership_errors and crosscheck_pass)
    pit_constructible = launch_complete and method_complete and lineage_complete and source_pass
    verdict = "GO_OFFICIAL_LINEAGE_AND_SOURCE_DATA_ONLY" if pit_constructible else "NO_GO_M2_STAR200_DATA_GATE"

    initial_frame = pd.DataFrame(
        [{"code": f"{item}.SH", "source_url": launch_members["source_url"], "source_file_sha256": launch_members["source_file_sha256"], "retrieved_at": launch_members["retrieved_at"], "parser_version": PARSER_VERSION} for item in sorted(members)]
    )
    initial_path = _project(str(protocol["identity"]["initial_set_artifact"]))
    _write_parquet_immutable(initial_path, initial_frame)
    event_path = _project(str(protocol["identity"]["membership_events_artifact"]))
    daily_path = _project(str(protocol["identity"]["daily_membership_artifact"]))
    derived = {
        "initial_set": {"path": str(initial_path.relative_to(PROJECT_ROOT)), "rows": len(initial_frame), "sha256": sha256_file(initial_path), "canonical_sha256": _frame_hash(initial_frame, list(initial_frame.columns))}
    }
    if pit_constructible:
        event_frame = pd.DataFrame(events).sort_values(["effective_date", "out_code", "in_code"], kind="stable").reset_index(drop=True)
        daily_frame = pd.DataFrame(
            [{"trade_date": day, "code": member} for day in open_dates_value for member in sorted(daily_members[day])]
        )
        _write_parquet_immutable(event_path, event_frame)
        _write_parquet_immutable(daily_path, daily_frame)
        derived["membership_events"] = {"path": str(event_path.relative_to(PROJECT_ROOT)), "rows": len(event_frame), "sha256": sha256_file(event_path)}
        derived["daily_membership"] = {"path": str(daily_path.relative_to(PROJECT_ROOT)), "rows": len(daily_frame), "sha256": sha256_file(daily_path)}

    report = {
        "schema_version": "m2-star200-data-quality-v1",
        "protocol_config_sha256": config_hash,
        "protocol_document_sha256": protocol["protocol_sha256"],
        "tool_snapshot_sha256": tool_snapshot_sha256(),
        "git_head": git_head(),
        "index_code": "000699.SH",
        "official_launch_set_complete": launch_complete,
        "official_adjustment_lineage_complete": lineage_complete,
        "methodology_lineage_complete": method_complete,
        "tushare_source_collection_pass": source_pass,
        "tushare_crosscheck_pass": crosscheck_pass,
        "pit_constructible": pit_constructible,
        "engineering_complete": False,
        "strategy_results_inspected": False,
        "strategy_effective": "NOT_EVALUATED",
        "production_authorization": "none",
        "verdict": verdict,
        "launch_checks": launch_checks,
        "methodology_checks": method_checks,
        "daily_quality": daily_quality_result,
        "weight_quality": weight_quality_result,
        "event_parse_checks": event_checks,
        "event_parse_errors": parse_errors,
        "membership_errors": membership_errors,
        "parsed_replacement_count": len(events),
        "monthly_crosschecks": comparisons,
        "derived_artifacts": derived,
    }
    report_path = _project(
        report_override or str(protocol["identity"]["quality_report"])
    )
    write_immutable_json(report_path, report)
    manifest = {
        "schema_version": "m2-star200-tracked-manifest-v1",
        "protocol_config_sha256": config_hash,
        "protocol_document_sha256": protocol["protocol_sha256"],
        "tool_snapshot_sha256": report["tool_snapshot_sha256"],
        "verdict": verdict,
        "strategy_results_inspected": False,
        "production_authorization": "none",
        "immutable_evidence": {
            "collection_report": {"path": str(collection_path.relative_to(PROJECT_ROOT)), "sha256": sha256_file(collection_path)},
            "official_discovery_report": {"path": str(discovery_path.relative_to(PROJECT_ROOT)), "sha256": sha256_file(discovery_path)},
            "quality_report": {"path": str(report_path.relative_to(PROJECT_ROOT)), "sha256": sha256_file(report_path)},
            **derived,
        },
        "official_sources": [_source_public(source) for source in sources],
        "desensitization": {"absolute_paths_included": False, "credentials_included": False, "cookies_or_headers_included": False, "provider_token_included": False, "raw_business_rows_included": False},
    }
    manifest_path = _project(
        manifest_override or str(protocol["identity"]["tracked_manifest"])
    )
    write_immutable_json(manifest_path, manifest)
    return {"report": report, "report_path": report_path, "manifest_path": manifest_path}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--collection-report", type=Path, required=True)
    parser.add_argument("--discovery-report", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--manifest", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = audit(
        _project(args.protocol),
        _project(args.collection_report),
        _project(args.discovery_report),
        report_override=args.report,
        manifest_override=args.manifest,
    )
    report = result["report"]
    print(json.dumps({key: report[key] for key in ("official_launch_set_complete", "official_adjustment_lineage_complete", "methodology_lineage_complete", "tushare_source_collection_pass", "tushare_crosscheck_pass", "pit_constructible", "strategy_effective", "production_authorization", "verdict")}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
