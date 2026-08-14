"""Independent offline recomputation for the H00906 lineage data gate."""

from __future__ import annotations

from io import BytesIO
import json

import pandas as pd
from pypdf import PdfReader

from shaiwei.ledger import INGEST
from shaiwei.provenance import code_snapshot_sha256, git_head
from shaiwei.research.trend_swing.benchmark_lineage import (
    DAILY_PATH,
    FACTSHEET_PATH,
    FIRST_HISTORY_PATH,
    MANIFEST_DRAFT_PATH,
    PROTOCOL_SHA256,
    RECOVERY_SHA256,
    REPORT_PATH,
    SECOND_HISTORY_PATH,
    evaluate_quality,
    load_calendar_evidence,
    load_protocol,
    parse_history,
)
from shaiwei.research.trend_swing.contract import sha256_file
from shaiwei.research.trend_swing.v5_evidence import write_once


AUDIT_PATH = REPORT_PATH.with_name("independent_audit.json")


def _factsheet_text() -> str:
    reader = PdfReader(BytesIO(FACTSHEET_PATH.read_bytes()))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def audit_once() -> dict:
    protocol = load_protocol()
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST_DRAFT_PATH.read_text(encoding="utf-8"))
    first = parse_history(FIRST_HISTORY_PATH.read_bytes())
    second = parse_history(SECOND_HISTORY_PATH.read_bytes())
    persisted = pd.read_parquet(DAILY_PATH).loc[:, first.columns]
    calendar = load_calendar_evidence(
        INGEST,
        start_date=protocol["benchmark"]["required_start_date"],
        end_date=protocol["benchmark"]["required_end_date"],
    )
    recomputed = evaluate_quality(
        first,
        second,
        identity_text=_factsheet_text(),
        calendar=calendar,
        start_date=protocol["benchmark"]["required_start_date"],
        end_date=protocol["benchmark"]["required_end_date"],
    )
    checks = {
        "protocol_identity": report["protocol_sha256"] == PROTOCOL_SHA256,
        "implementation_git_identity": report["implementation_git_head"] == git_head(),
        "implementation_snapshot_identity": (
            report["implementation_snapshot_sha256"] == code_snapshot_sha256()
        ),
        "report_verdict": report["verdict"] == "GO_H00906_LINEAGE_DATA_GATE_ONLY",
        "recomputed_report_counts": all(
            report[key] == recomputed[key]
            for key in (
                "row_count",
                "first_date",
                "last_date",
                "official_open_day_count",
                "duplicate_key_count",
                "missing_official_open_date_count",
                "unexpected_date_count",
                "invalid_close_count",
                "invalid_ohlc_count",
            )
        ),
        "derived_daily_equals_official_response": persisted.equals(first),
        "derived_daily_hash": (
            manifest["sources"]["official.csi_total_return"]["artifacts"][0]["content_sha256"]
            == sha256_file(DAILY_PATH)
        ),
        "explicit_H00906_identity": (
            manifest["sources"]["official.csi_total_return"]["artifacts"][0]["params"]["index_id"]
            == "H00906"
        ),
        "raw_hashes": all(
            report["artifacts"][key]["sha256"] == sha256_file(path)
            for key, path in (
                ("factsheet", FACTSHEET_PATH),
                ("history_first", FIRST_HISTORY_PATH),
                ("history_second", SECOND_HISTORY_PATH),
            )
        ),
        "zero_effect_attempt": report["strategy_effect_attempt_count"] == 0,
        "zero_secret_read": report["tushare_or_secret_read_count"] == 0,
        "transport_recovery_identity": report.get("transport_recovery_sha256")
        == RECOVERY_SHA256,
        "transport_attempt_accounting": report.get("transport_recovery")
        == {
            "prior_failed_transport_attempt_count": 1,
            "recovery_completed_response_count": 3,
            "secret_read_count": 0,
        },
        "no_production_authorization": report["production_authorization"] == "none",
    }
    if not all(checks.values()):
        raise RuntimeError("independent H00906 lineage audit failed")
    audit = {
        "schema_version": "ts-v5-r3g2-h00906-independent-audit-v1",
        "protocol_sha256": PROTOCOL_SHA256,
        "report_sha256": sha256_file(REPORT_PATH),
        "manifest_sha256": sha256_file(MANIFEST_DRAFT_PATH),
        "verdict": "PASS",
        "checks": checks,
        "strategy_effect_attempt_count": 0,
        "production_authorization": "none",
    }
    write_once(AUDIT_PATH, json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return audit


def main() -> int:
    audit = audit_once()
    print(json.dumps({"verdict": audit["verdict"], "checks": len(audit["checks"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
