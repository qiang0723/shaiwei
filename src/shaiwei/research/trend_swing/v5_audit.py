"""Independent, offline audit for one completed TS-v5 LLM research batch."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import re
from typing import Any

from shaiwei.config import PROJECT_ROOT
from shaiwei.ledger import sha256_file
from shaiwei.research.deepseek_client import TRANSPORT_LEDGER_HEADER_V2
from shaiwei.research.provider_contract import D1ControlError
from shaiwei.research.trend_swing.v5_contract import canonical_json, sha256_text
from shaiwei.research.trend_swing.v5_evidence import attempt_rows, candidate_gate, write_once
from shaiwei.research.trend_swing.v5_live import (
    DEFAULT_ATTEMPT_LEDGER,
    DEFAULT_OUTPUT,
    DEFAULT_RELEASE,
    DEFAULT_TRANSPORT_LEDGER,
)
from shaiwei.research.trend_swing.v5_transport import (
    INDEPENDENT_REQUEST_BUNDLE_SHA256,
    V5ExecutionRelease,
    V5TransportProtocol,
)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise D1ControlError(f"TS-v5 audit JSON is invalid: {path.name}") from exc
    if not isinstance(value, dict):
        raise D1ControlError("TS-v5 audit JSON must be an object")
    return value


def _transport_rows(
    path: Path, release: V5ExecutionRelease
) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    if tuple(reader.fieldnames or ()) != TRANSPORT_LEDGER_HEADER_V2:
        raise D1ControlError("TS-v5 audit transport schema differs")
    if len({row["event_id"] for row in rows}) != len(rows):
        raise D1ControlError("TS-v5 audit transport event ids are duplicated")
    if any(
        row["execution_release_id"] != release.release_id
        or row["execution_release_sha256"] != release.sha256
        for row in rows
    ):
        raise D1ControlError("TS-v5 audit transport release differs")
    if any(row["event_type"] == "BILLING_UNCERTAIN" for row in rows):
        raise D1ControlError("TS-v5 audit found billing uncertainty")
    return rows


def _verify_artifacts(
    rows: list[dict[str, str]],
    transport: list[dict[str, str]],
    output_root: Path,
    project_root: Path,
) -> dict[str, int]:
    completed = [row for row in transport if row["event_type"] == "COMPLETED"]
    by_attempt = {row["attempt_id"]: row for row in completed}
    if len(completed) != 12 or len(by_attempt) != 12:
        raise D1ControlError("TS-v5 audit requires exactly 12 completed transports")
    for row in rows:
        request_path = output_root / "artifacts/requests" / (
            f"{row['attempt_id']}-{row['request_sha256'][:12]}.json"
        )
        raw_path = project_root / row["raw_artifact_path"]
        manifest_path = project_root / row["manifest_path"]
        if (
            sha256_file(request_path) != row["request_sha256"]
            or sha256_file(raw_path) != row["raw_artifact_sha256"]
            or sha256_file(manifest_path) != row["manifest_sha256"]
        ):
            raise D1ControlError("TS-v5 immutable attempt artifact differs")
        request_text = request_path.read_text(encoding="utf-8")
        if re.search(r"\b\d{6}\.(?:SH|SZ|BJ)\b|/(?:Users|private|workspace)/|sk-[A-Za-z0-9]", request_text):
            raise D1ControlError("TS-v5 outbound request contains a forbidden identity")
        manifest = _load_json(manifest_path)
        raw = _load_json(raw_path)
        event = by_attempt.get(row["attempt_id"])
        if (
            manifest.get("request_sha256") != row["request_sha256"]
            or manifest.get("response_sha256") != row["response_sha256"]
            or raw.get("source_response_sha256") != row["response_sha256"]
            or event is None
            or event["request_sha256"] != row["request_sha256"]
            or event["source_response_sha256"] != row["response_sha256"]
        ):
            raise D1ControlError("TS-v5 attempt linkage differs")
        provider_path = output_root / "artifacts/provider" / event["response_artifact_path"]
        if sha256_file(provider_path) != event["response_artifact_sha256"]:
            raise D1ControlError("TS-v5 provider response artifact differs")
    return {
        "attempt_rows": len(rows),
        "transport_events": len(transport),
        "transport_completions": len(completed),
        "request_artifacts": len(rows),
        "raw_artifacts": len(rows),
        "manifest_artifacts": len(rows),
        "provider_artifacts": len(completed),
    }


def audit_batch(
    *,
    release_path: Path,
    output_root: Path,
    attempt_path: Path,
    transport_path: Path,
    project_root: Path = PROJECT_ROOT,
) -> dict[str, Any]:
    protocol = V5TransportProtocol.load()
    release = V5ExecutionRelease.load(
        release_path,
        protocol,
        independent_request_bundle_sha256=INDEPENDENT_REQUEST_BUNDLE_SHA256,
    )
    rows = attempt_rows(attempt_path, release)
    if len(rows) != 12:
        raise D1ControlError("TS-v5 audit requires exactly 12 attempt rows")
    transport = _transport_rows(transport_path, release)
    static = _verify_artifacts(rows, transport, output_root, project_root)
    report = _load_json(output_root / "ts_v5_llm_report.json")
    bundle = sha256_text(
        canonical_json(
            [
                {
                    "attempt_id": row["attempt_id"],
                    "response_sha256": row["response_sha256"],
                    "manifest_sha256": row["manifest_sha256"],
                }
                for row in rows
            ]
        )
    )
    total_cost = sum(float(row["estimated_cost_usd"]) for row in rows)
    authoritative_gate, valid_candidates = candidate_gate(rows)
    checks = {
        "release_identity": report.get("execution_release_sha256") == release.sha256,
        "completed_responses_exact": report.get("completed_response_count") == 12,
        "independent_and_revision_counts": report.get("independent_response_count") == 6
        and report.get("adversarial_response_count") == 6,
        "cost_recomputed": abs(float(report.get("actual_cost_usd", -1)) - total_cost) < 1e-12,
        "cost_below_batch_ceiling": total_cost <= 0.5,
        "evidence_bundle": report.get("attempt_evidence_bundle_sha256") == bundle,
        "no_market_or_effect_read": report.get("market_or_effect_read") is False,
        "no_parameter_search_or_backtest": report.get("parameter_search_or_backtest") is False,
        "no_paper_web_or_production": report.get("paper_web_or_production") is False,
        "strategy_not_evaluated": report.get("candidate_effectiveness") == "NOT_EVALUATED",
        "production_authorization_none": report.get("production_authorization") == "none",
    }
    verdict = "PASS" if all(checks.values()) else "FAIL"
    result = {
        "schema_version": "ts-v5-llm-independent-audit-v1",
        "execution_release_sha256": release.sha256,
        "checks": checks,
        "static_evidence": static,
        "actual_cost_usd": total_cost,
        "valid_candidate_count": valid_candidates,
        "authoritative_candidate_gate": authoritative_gate,
        "original_report_gate": report.get("gate"),
        "original_report_gate_consistent": report.get("gate") == authoritative_gate,
        "original_report_gate_finding": (
            "NONE"
            if report.get("gate") == authoritative_gate
            else "ORIGINAL_GATE_IGNORED_CANDIDATE_VALIDITY"
        ),
        "candidate_content_used_for_effect_decision": False,
        "network_used": False,
        "secret_read": False,
        "verdict": verdict,
    }
    if verdict != "PASS":
        raise D1ControlError("TS-v5 independent audit failed")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, default=DEFAULT_RELEASE)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--attempt-ledger", type=Path, default=DEFAULT_ATTEMPT_LEDGER)
    parser.add_argument("--transport-ledger", type=Path, default=DEFAULT_TRANSPORT_LEDGER)
    parser.add_argument("--write-report", type=Path)
    args = parser.parse_args(argv)
    try:
        result = audit_batch(
            release_path=args.release,
            output_root=args.output_root,
            attempt_path=args.attempt_ledger,
            transport_path=args.transport_ledger,
        )
        if args.write_report:
            write_once(
                args.write_report,
                json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            )
    except (D1ControlError, OSError, RuntimeError, TypeError, ValueError):
        print(canonical_json({"status": "FAIL", "error_class": "TSV5LLMAuditError"}))
        return 2
    print(canonical_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
