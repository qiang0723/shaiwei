"""One-shot offline TS-1A-R2 result-blind profile orchestration."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import duckdb
import pyarrow.parquet as pq

from shaiwei.config import PROJECT_ROOT
from shaiwei.provenance import code_snapshot_sha256, git_head
from shaiwei.research.trend_swing.contract import (
    ALPHA158_PATH,
    TrendSwingError,
    canonical_sha256,
    sha256_file,
    write_once_json,
)
from shaiwei.research.trend_swing.recovery_candidate import (
    CANDIDATE_EVENT_PATH,
    candidate_summary,
    prepare_candidate_profile,
    write_candidate_events,
)
from shaiwei.research.trend_swing.recovery_contract import (
    DAILY_PROFILE_PATH,
    MANIFEST_PATH,
    NETWORK_RECEIPT_PATH,
    PROFILE_PATH,
    RECOVERY_OUTPUT_DIR,
    RecoveryAddendum,
    RecoveryProtocol,
    RecoveryR2,
    RecoveryR2Addendum,
    RecoveryRelease,
)
from shaiwei.research.trend_swing.recovery_r3_contract import RecoveryR3
from shaiwei.research.trend_swing.recovery_evidence import evidence_summary
from shaiwei.research.trend_swing.recovery_market import market_summary, prepare_market_and_sector
from shaiwei.research.trend_swing.recovery_store import configure_store, prepare_core_tables
from shaiwei.research.trend_swing.sources import collect_input_manifest


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TrendSwingError(f"TS recovery expected JSON mapping: {path.name}")
    return value


def collect_recovery_manifest(
    protocol: RecoveryProtocol,
    addendum: RecoveryAddendum,
    recovery_r2: RecoveryR2,
    recovery_r2_addendum: RecoveryR2Addendum,
    recovery_r3: RecoveryR3,
    release: RecoveryRelease,
) -> dict[str, Any]:
    base = collect_input_manifest(protocol)  # compatible required-source interface
    receipt = _load_json(NETWORK_RECEIPT_PATH)
    if receipt.get("release_scope_sha256") != release.scope_sha256:
        raise TrendSwingError("TS recovery network receipt release binding differs")
    return {
        **base,
        "schema_version": "ts-v3-data-recovery-input-manifest-r3-v1",
        "recovery_protocol_sha256": protocol.sha256,
        "operationalization_addendum_sha256": addendum.sha256,
        "recovery_r2_protocol_sha256": recovery_r2.sha256,
        "recovery_r2_addendum_sha256": recovery_r2_addendum.sha256,
        "recovery_r3_protocol_sha256": recovery_r3.sha256,
        "release_scope_sha256": release.scope_sha256,
        "release_file_sha256": release.sha256,
        "network_receipt_path": NETWORK_RECEIPT_PATH.relative_to(PROJECT_ROOT).as_posix(),
        "network_receipt_sha256": sha256_file(NETWORK_RECEIPT_PATH),
    }


def _write_daily_profile(connection: duckdb.DuckDBPyConnection) -> None:
    if DAILY_PROFILE_PATH.exists():
        raise TrendSwingError("TS recovery anonymous daily profile already exists")
    connection.execute(
        "COPY anonymous_daily TO ? (FORMAT PARQUET,COMPRESSION ZSTD)",
        [str(DAILY_PROFILE_PATH)],
    )


def build_profile(
    protocol: RecoveryProtocol,
    addendum: RecoveryAddendum,
    recovery_r2: RecoveryR2,
    recovery_r2_addendum: RecoveryR2Addendum,
    recovery_r3: RecoveryR3,
    release: RecoveryRelease,
    manifest: dict[str, Any],
) -> dict[str, Any]:
    temporary = RECOVERY_OUTPUT_DIR / "duckdb-tmp"
    connection = duckdb.connect(":memory:")
    try:
        configure_store(connection, temporary)
        prepare_core_tables(
            connection,
            manifest,
            start_date=protocol.start_date,
            end_date=protocol.end_date,
        )
        prepare_market_and_sector(connection)
        prepare_candidate_profile(connection)
        evidence = evidence_summary(connection, ALPHA158_PATH)
        candidates = candidate_summary(connection)
        markets = market_summary(connection)
        _write_daily_profile(connection)
        write_candidate_events(connection)
    finally:
        connection.close()
    if not evidence["data_gate_pass"]:
        verdict = "BLOCKED_DATA"
        next_status = "NOT_EVALUATED_UPSTREAM_BLOCKED"
    elif candidates["funnel"]["candidate_events"] == 0:
        verdict = "BLOCKED_ENTRY_RULE"
        next_status = "NO_EVENTS_FOR_FUTURE_EFFECT_PROTOCOL"
    else:
        verdict = "GO_TS_V3_FREEZE"
        next_status = "READY_FOR_SEPARATE_RESULT_BEFORE_EXIT_AND_EFFECT_PROTOCOL"
    return {
        "schema_version": "ts-v3-result-blind-data-recovery-profile-r3-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "protocol_identity": {
            "recovery_protocol_sha256": protocol.sha256,
            "operationalization_addendum_sha256": addendum.sha256,
            "recovery_r2_protocol_sha256": recovery_r2.sha256,
            "recovery_r2_addendum_sha256": recovery_r2_addendum.sha256,
            "recovery_r3_protocol_sha256": recovery_r3.sha256,
            "release_scope_sha256": release.scope_sha256,
        },
        "code_identity": {
            "git_head": git_head(),
            "code_snapshot_sha256": code_snapshot_sha256(),
        },
        "input_manifest_sha256": canonical_sha256(manifest),
        "authority": {
            "result_blind": True,
            "strategy_effect_attempt_count": 0,
            "strategy_results_inspected": False,
            "network_logical_request_count": 3,
            "production_authorization": "none",
            "security_level_recommendations_emitted": False,
        },
        "data_evidence": evidence,
        "market_and_sector_profile": markets,
        "anonymous_candidate_profile": candidates,
        "machine_artifacts": {
            "anonymous_daily_profile": {
                "path": DAILY_PROFILE_PATH.relative_to(PROJECT_ROOT).as_posix(),
                "row_count": pq.read_metadata(DAILY_PROFILE_PATH).num_rows,
                "sha256": sha256_file(DAILY_PROFILE_PATH),
                "contains_security_identity": False,
            },
            "candidate_event_intermediate": {
                "path": CANDIDATE_EVENT_PATH.relative_to(PROJECT_ROOT).as_posix(),
                "row_count": pq.read_metadata(CANDIDATE_EVENT_PATH).num_rows,
                "sha256": sha256_file(CANDIDATE_EVENT_PATH),
                "gitignored": True,
                "contains_post_entry_return": False,
                "included_in_report": False,
            },
        },
        "next_status": next_status,
        "strategy_effective": "NOT_EVALUATED",
        "production_authorization": "none",
        "verdict": verdict,
    }


def run_offline_once() -> dict[str, Any]:
    if MANIFEST_PATH.exists() or PROFILE_PATH.exists():
        raise TrendSwingError("TS recovery offline profile already exists; rerun is forbidden")
    protocol = RecoveryProtocol.load()
    addendum = RecoveryAddendum.load(protocol)
    recovery_r2 = RecoveryR2.load(protocol, addendum)
    recovery_r2_addendum = RecoveryR2Addendum.load(recovery_r2)
    recovery_r3 = RecoveryR3.load(recovery_r2, recovery_r2_addendum)
    release = RecoveryRelease.load(
        protocol, addendum, recovery_r2, recovery_r2_addendum, recovery_r3
    )
    manifest = collect_recovery_manifest(
        protocol, addendum, recovery_r2, recovery_r2_addendum, recovery_r3, release
    )
    manifest_file_sha, reused = write_once_json(MANIFEST_PATH, manifest)
    if reused:
        raise TrendSwingError("TS recovery manifest unexpectedly pre-existed")
    report = build_profile(
        protocol, addendum, recovery_r2, recovery_r2_addendum, recovery_r3, release, manifest
    )
    report["input_manifest_file_sha256"] = manifest_file_sha
    write_once_json(PROFILE_PATH, report)
    return report
