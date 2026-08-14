"""One-shot official network adapter for the frozen H00906 lineage gate."""

from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
from typing import Any

import httpx
from pypdf import PdfReader

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
    REPORT_PATH,
    SECOND_HISTORY_PATH,
    canonical_history_data,
    evaluate_quality,
    load_calendar_evidence,
    load_protocol,
    parse_history,
)
from shaiwei.research.trend_swing.contract import canonical_sha256, sha256_file
from shaiwei.research.trend_swing.v5_evidence import write_once


def _get(client: httpx.Client, url: str, params: dict[str, str] | None = None) -> bytes:
    response = client.get(url, params=params)
    response.raise_for_status()
    if not response.content:
        raise BenchmarkLineageError("official H00906 response is empty")
    return response.content


def _factsheet_text(raw: bytes) -> str:
    try:
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


def _artifact(path: Path, root: Path = PROJECT_ROOT) -> dict[str, Any]:
    return {
        "path": path.relative_to(root).as_posix(),
        "sha256": sha256_file(path),
        "byte_count": path.stat().st_size,
    }


def _manifest(report: dict[str, Any]) -> dict[str, Any]:
    derived = _artifact(DAILY_PATH)
    return {
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
            "factsheet": _artifact(FACTSHEET_PATH),
            "history_first": _artifact(FIRST_HISTORY_PATH),
            "history_second": _artifact(SECOND_HISTORY_PATH),
        },
        "data_gate_report": _artifact(REPORT_PATH),
        "calendar_ledger_sha256": report["calendar_ledger_sha256"],
        "verdict": report["verdict"],
        "strategy_effective": "NOT_EVALUATED",
        "production_authorization": "none",
    }


def run_once(*, ledger_path: Path = INGEST) -> dict[str, Any]:
    protocol = load_protocol()
    source = protocol["official_sources"]
    history = source["daily_history"]
    if any(path.exists() for path in (FACTSHEET_PATH, FIRST_HISTORY_PATH, SECOND_HISTORY_PATH)):
        raise BenchmarkLineageError("H00906 network scope was already consumed")
    headers = {"User-Agent": "shaiwei-h00906-lineage/1.0", "Accept": "application/json,application/pdf"}
    with httpx.Client(timeout=30.0, follow_redirects=True, trust_env=False, headers=headers) as client:
        factsheet = _get(client, source["identity_factsheet"]["url"])
        first_raw = _get(client, history["url"], history["query"])
        second_raw = _get(client, history["url"], history["query"])
    if canonical_history_data(first_raw) != canonical_history_data(second_raw):
        raise BenchmarkLineageError("two official H00906 responses drifted before persistence")
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
        identity_text=_factsheet_text(factsheet),
        calendar=calendar,
        start_date=protocol["benchmark"]["required_start_date"],
        end_date=protocol["benchmark"]["required_end_date"],
    )
    report["implementation_git_head"] = git_head()
    report["implementation_snapshot_sha256"] = code_snapshot_sha256()
    _write_once_bytes(FACTSHEET_PATH, factsheet)
    _write_once_bytes(FIRST_HISTORY_PATH, first_raw)
    _write_once_bytes(SECOND_HISTORY_PATH, second_raw)
    DAILY_PATH.parent.mkdir(parents=True, exist_ok=True)
    first.to_parquet(DAILY_PATH, index=False)
    report["artifacts"] = {
        "factsheet": _artifact(FACTSHEET_PATH),
        "history_first": _artifact(FIRST_HISTORY_PATH),
        "history_second": _artifact(SECOND_HISTORY_PATH),
        "derived_daily": _artifact(DAILY_PATH),
    }
    write_once(REPORT_PATH, json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    manifest = _manifest(report)
    write_once(
        MANIFEST_DRAFT_PATH,
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    return {**report, "manifest_sha256": canonical_sha256(manifest)}


def main() -> int:
    report = run_once()
    print(
        json.dumps(
            {
                "verdict": report["verdict"],
                "row_count": report["row_count"],
                "first_date": report["first_date"],
                "last_date": report["last_date"],
                "strategy_effective": report["strategy_effective"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
