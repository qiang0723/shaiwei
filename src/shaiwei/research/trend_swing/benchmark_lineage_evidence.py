"""Canonical persistence shared by network and offline H00906 transports."""

from __future__ import annotations

import hashlib
from io import BytesIO
import json
from pathlib import Path
from typing import Any

from shaiwei.config import PROJECT_ROOT
from shaiwei.ledger import INGEST
from shaiwei.provenance import code_snapshot_sha256, git_head
from shaiwei.research.trend_swing.benchmark_lineage import (
    BenchmarkLineageError,
    DAILY_PATH,
    FACTSHEET_PATH,
    FIRST_HISTORY_PATH,
    MANIFEST_DRAFT_PATH,
    PROTOCOL_SHA256,
    RECOVERY_R2_SHA256,
    RECOVERY_R3_SHA256,
    REPORT_PATH,
    SECOND_HISTORY_PATH,
    evaluate_quality,
    load_calendar_evidence,
    load_protocol,
    parse_history,
)
from shaiwei.research.trend_swing.contract import canonical_sha256, sha256_file
from shaiwei.research.trend_swing.v5_evidence import write_once


def factsheet_text(raw: bytes) -> str:
    try:
        from pypdf import PdfReader

        reader = PdfReader(BytesIO(raw))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception as exc:  # pypdf exposes multiple backend-specific exceptions
        raise BenchmarkLineageError("official H00906 factsheet cannot be parsed") from exc


def _write_once_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(payload)
    except FileExistsError as exc:
        raise BenchmarkLineageError(f"H00906 output already exists: {path.name}") from exc


def artifact(path: Path, root: Path = PROJECT_ROOT) -> dict[str, Any]:
    return {
        "path": path.relative_to(root).as_posix(),
        "sha256": sha256_file(path),
        "byte_count": path.stat().st_size,
    }


def _manifest(report: dict[str, Any]) -> dict[str, Any]:
    derived = artifact(DAILY_PATH)
    manifest = {
        "schema_version": "ts-v5-r3g2-h00906-benchmark-manifest-v1",
        "protocol_id": report["protocol_id"],
        "protocol_sha256": PROTOCOL_SHA256,
        "authority": "official.csi_total_return",
        "sources": {
            "official.csi_total_return": {
                "artifact_count": 1,
                "row_count": report["row_count"],
                "artifacts": [
                    {
                        "params": {
                            "index_id": "H00906",
                            "start_date": "20190101",
                            "end_date": "20260811",
                        },
                        "path": derived["path"],
                        "content_sha256": derived["sha256"],
                        "row_count": report["row_count"],
                    }
                ],
            }
        },
        "raw_evidence": {
            "factsheet": artifact(FACTSHEET_PATH),
            "history_first": artifact(FIRST_HISTORY_PATH),
            "history_second": artifact(SECOND_HISTORY_PATH),
        },
        "data_gate_report": artifact(REPORT_PATH),
        "calendar_ledger_sha256": report["calendar_ledger_sha256"],
        "verdict": report["verdict"],
        "strategy_effective": "NOT_EVALUATED",
        "production_authorization": "none",
    }
    if "transport_recovery_sha256" in report:
        manifest["transport_recovery_sha256"] = report["transport_recovery_sha256"]
    return manifest


def evaluate_and_persist(
    factsheet: bytes,
    first_raw: bytes,
    second_raw: bytes,
    *,
    raw_already_persisted: bool,
    ledger_path: Path = INGEST,
    transport_recovery: dict[str, int] | None = None,
) -> dict[str, Any]:
    protocol = load_protocol()
    first = parse_history(first_raw)
    second = parse_history(second_raw)
    calendar = load_calendar_evidence(
        ledger_path,
        start_date=protocol["benchmark"]["required_start_date"],
        end_date=protocol["benchmark"]["required_end_date"],
    )
    report = evaluate_quality(
        first,
        second,
        identity_text=factsheet_text(factsheet),
        calendar=calendar,
        start_date=protocol["benchmark"]["required_start_date"],
        end_date=protocol["benchmark"]["required_end_date"],
    )
    report["implementation_git_head"] = git_head()
    report["implementation_snapshot_sha256"] = code_snapshot_sha256()
    if transport_recovery is not None:
        report["transport_recovery"] = transport_recovery
        report["transport_recovery_sha256"] = RECOVERY_R3_SHA256
        report["parent_transport_recovery_sha256"] = RECOVERY_R2_SHA256
    if raw_already_persisted:
        expected = (
            (FACTSHEET_PATH, factsheet),
            (FIRST_HISTORY_PATH, first_raw),
            (SECOND_HISTORY_PATH, second_raw),
        )
        if any(sha256_file(path) != hashlib.sha256(payload).hexdigest() for path, payload in expected):
            raise BenchmarkLineageError("host-transferred H00906 bytes changed during evaluation")
    else:
        _write_once_bytes(FACTSHEET_PATH, factsheet)
        _write_once_bytes(FIRST_HISTORY_PATH, first_raw)
        _write_once_bytes(SECOND_HISTORY_PATH, second_raw)
    if any(path.exists() for path in (DAILY_PATH, REPORT_PATH, MANIFEST_DRAFT_PATH)):
        raise BenchmarkLineageError("H00906 derived scope was already consumed")
    DAILY_PATH.parent.mkdir(parents=True, exist_ok=True)
    first.to_parquet(DAILY_PATH, index=False)
    report["artifacts"] = {
        "factsheet": artifact(FACTSHEET_PATH),
        "history_first": artifact(FIRST_HISTORY_PATH),
        "history_second": artifact(SECOND_HISTORY_PATH),
        "derived_daily": artifact(DAILY_PATH),
    }
    write_once(REPORT_PATH, json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    manifest = _manifest(report)
    write_once(
        MANIFEST_DRAFT_PATH,
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    return {**report, "manifest_sha256": canonical_sha256(manifest)}
