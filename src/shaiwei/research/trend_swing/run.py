"""One-shot, result-blind TS-1A data preflight and profile entrypoint."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from shaiwei.provenance import code_snapshot_sha256, git_head
from shaiwei.research.trend_swing.data_quality import profile_universe_quality
from shaiwei.research.trend_swing.contract import (
    MANIFEST_PATH,
    REPORT_PATH,
    TrendSwingError,
    TrendSwingProtocol,
    canonical_sha256,
    write_once_json,
)
from shaiwei.research.trend_swing.sources import (
    alpha158_coverage,
    calendar_coverage,
    collect_input_manifest,
    index_coverage,
)


EXPECTED_BENCHMARKS = {
    "main": "000906.SH",
    "chinext": "399006.SZ",
    "star": "000688.SH",
}


def judge_preflight(
    protocol: TrendSwingProtocol,
    manifest: dict[str, Any],
    indexes: list[dict[str, Any]],
) -> tuple[list[str], list[dict[str, Any]]]:
    blocks = []
    details = []
    missing_sources = list(manifest.get("required_sources_missing", []))
    if missing_sources:
        blocks.append("BLOCKED_DATA")
        details.append({"code": "REQUIRED_SOURCE_MISSING", "sources": missing_sources})
    available = {row["ts_code"]: row for row in indexes}
    for segment, code in EXPECTED_BENCHMARKS.items():
        row = available.get(code)
        if row is None:
            blocks.append("BLOCKED_MARKET_RULE")
            details.append(
                {
                    "code": "OFFICIAL_SEGMENT_INDEX_MISSING",
                    "segment": segment,
                    "benchmark_code": code,
                }
            )
        elif int(row["duplicate_date_count"]) != 0:
            blocks.append("BLOCKED_DATA")
            details.append(
                {
                    "code": "INDEX_DUPLICATE_DATE",
                    "benchmark_code": code,
                    "duplicate_date_count": int(row["duplicate_date_count"]),
                }
            )
    alpha = manifest.get("alpha158", {})
    if not alpha.get("present"):
        blocks.append("BLOCKED_FACTOR_LINEAGE")
        details.append({"code": "FROZEN_ALPHA158_CACHE_MISSING"})
    return sorted(set(blocks)), details


def build_report(
    protocol: TrendSwingProtocol,
    manifest: dict[str, Any],
    *,
    generated_at: str,
) -> dict[str, Any]:
    indexes = index_coverage(manifest)
    blocks, details = judge_preflight(protocol, manifest, indexes)
    quality = profile_universe_quality(protocol, manifest)
    failed_quality = [key for key, value in quality.get("gate_checks", {}).items() if not value]
    if failed_quality:
        blocks = sorted(set([*blocks, "BLOCKED_DATA"]))
        details.append({"code": "UNIVERSE_DATA_GATE_FAILED", "failed_checks": failed_quality})
    if blocks:
        verdict = blocks[0] if len(blocks) == 1 else "MULTIPLE_BLOCKS"
    else:
        verdict = "GO_TS_V3_FREEZE"
    return {
        "schema_version": "ts-v3-result-blind-data-gate-report-v1",
        "protocol_id": protocol.document["protocol_id"],
        "protocol_sha256": protocol.sha256,
        "generated_at": generated_at,
        "code_identity": {
            "git_head": git_head(),
            "code_snapshot_sha256": code_snapshot_sha256(),
        },
        "input_manifest_sha256": canonical_sha256(manifest),
        "authority": {
            "result_blind": True,
            "strategy_effect_attempt_count": 0,
            "strategy_results_inspected": False,
            "network_request_count": 0,
            "production_authorization": "none",
        },
        "scope": {
            "start_date": protocol.start_date,
            "end_date": protocol.end_date,
            "universe_id": protocol.document["scope"]["universe_id"],
        },
        "source_summary": {
            key: {
                "batch_count": value["batch_count"],
                "row_count": value["row_count"],
                "artifact_bundle_sha256": value.get("artifact_bundle_sha256"),
            }
            for key, value in manifest["sources"].items()
        },
        "calendar_coverage": calendar_coverage(manifest),
        "official_index_coverage": indexes,
        "alpha158_coverage": alpha158_coverage(manifest),
        "universe_data_quality": quality,
        "data_profile": {
            "completed": not blocks,
            "candidate_funnel_status": "NOT_EVALUATED_UPSTREAM_BLOCKED" if blocks else "READY_FOR_PROFILE",
            "sector_profile_status": "NOT_EVALUATED_UPSTREAM_BLOCKED" if blocks else "READY_FOR_PROFILE",
            "stock_structure_profile_status": "NOT_EVALUATED_UPSTREAM_BLOCKED" if blocks else "READY_FOR_PROFILE",
        },
        "blocking_verdicts": blocks,
        "blocking_details": details,
        "recovery_plan": [
            {
                "source_api": "tushare.index_daily",
                "params": {
                    "ts_code": "399006.SZ",
                    "start_date": protocol.start_date,
                    "end_date": protocol.end_date,
                    "fields": "ts_code,trade_date,open,high,low,close,pre_close,change,pct_chg,vol,amount",
                },
                "policy": "new_recovery_protocol_and_network_authorization_required",
            }
        ]
        if any(detail["code"] == "OFFICIAL_SEGMENT_INDEX_MISSING" for detail in details)
        else [],
        "verdict": verdict,
    }


def run_once() -> dict[str, Any]:
    if REPORT_PATH.exists():
        raise TrendSwingError("TS-1A real profile already exists; same-scope rerun is forbidden")
    protocol = TrendSwingProtocol.load()
    manifest = collect_input_manifest(protocol)
    manifest_sha, reused = write_once_json(MANIFEST_PATH, manifest)
    if reused:
        raise TrendSwingError("TS-1A manifest already existed before the real profile")
    report = build_report(
        protocol,
        manifest,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
    if report["input_manifest_sha256"] != canonical_sha256(manifest):
        raise TrendSwingError("TS-1A report manifest binding differs")
    report["input_manifest_file_sha256"] = manifest_sha
    write_once_json(REPORT_PATH, report)
    return report
