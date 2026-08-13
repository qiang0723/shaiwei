"""Independent offline audit for the completed no-retry TS-v5-R3F canary."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from typing import Any

from shaiwei.config import PROJECT_ROOT
from shaiwei.ledger import sha256_file
from shaiwei.research.provider_contract import D1ControlError
from shaiwei.research.trend_swing.v5_contract import canonical_json, sha256_text
from shaiwei.research.trend_swing.v5_evidence import attempt_rows, write_once
from shaiwei.research.trend_swing.v5_r3f_canary import (
    MECHANISMS,
    R3FTransportProtocol,
    batch_gate,
    classify_proposal_response,
    request_bundle,
)
from shaiwei.research.trend_swing.v5_r3f_live import (
    DEFAULT_ATTEMPT_LEDGER,
    DEFAULT_OUTPUT,
    DEFAULT_RELEASE,
    DEFAULT_TRANSPORT_LEDGER,
)
from shaiwei.research.trend_swing.v5_r3f_release import (
    REQUEST_BUNDLE_SHA256,
    R3FExecutionRelease,
)
from shaiwei.research.trend_swing.v5_runtime_audit import (
    json_object,
    provider_response,
    transport_rows,
)


def _linked_response(
    *,
    ordinal: int,
    row: dict[str, str],
    request: dict[str, Any],
    by_attempt: dict[str, dict[str, str]],
    output_root: Path,
    project_root: Path,
) -> dict[str, Any]:
    task = json.loads(request["messages"][1]["content"])
    if (
        row["attempt_id"] != task["attempt_id"]
        or row["mechanism"] != MECHANISMS[ordinal - 1].value
        or row["mode"] != "INDEPENDENT"
        or task["assigned_attempt_authority"]["mode"] != "INDEPENDENT"
        or task["assigned_attempt_authority"]["ordinal"] != ordinal
    ):
        raise D1ControlError("TS-v5-R3F attempt schedule or authority differs")
    request_path = output_root / "artifacts/requests" / (
        f"{row['attempt_id']}-{row['request_sha256'][:12]}.json"
    )
    request_text = request_path.read_text(encoding="utf-8")
    if request_text != canonical_json(request) or re.search(
        r"\b\d{6}\.(?:SH|SZ|BJ)\b|/(?:Users|private|workspace)/|sk-[A-Za-z0-9]",
        request_text,
    ):
        raise D1ControlError("TS-v5-R3F outbound request differs or contains identity")
    raw_path = project_root / row["raw_artifact_path"]
    manifest_path = project_root / row["manifest_path"]
    if (
        sha256_file(request_path) != row["request_sha256"]
        or sha256_file(raw_path) != row["raw_artifact_sha256"]
        or sha256_file(manifest_path) != row["manifest_sha256"]
    ):
        raise D1ControlError("TS-v5-R3F immutable attempt artifact differs")
    raw = json_object(raw_path, label="TS-v5-R3F")
    manifest = json_object(manifest_path, label="TS-v5-R3F")
    event = by_attempt.get(row["attempt_id"])
    if (
        event is None
        or event["request_sha256"] != row["request_sha256"]
        or event["source_response_sha256"] != row["response_sha256"]
        or raw.get("source_response_sha256") != row["response_sha256"]
        or manifest.get("request_sha256") != row["request_sha256"]
        or manifest.get("response_sha256") != row["response_sha256"]
        or manifest.get("candidate_fingerprint") != row["candidate_fingerprint"]
        or manifest.get("parse_status") != row["parse_status"]
        or manifest.get("schema_status") != row["schema_status"]
        or manifest.get("duplicate_status") != row["duplicate_status"]
        or manifest.get("failure_class") != row["failure_class"]
    ):
        raise D1ControlError("TS-v5-R3F transport linkage differs")
    provider_path = output_root / "artifacts/provider" / event["response_artifact_path"]
    if sha256_file(provider_path) != event["response_artifact_sha256"]:
        raise D1ControlError("TS-v5-R3F provider artifact differs")
    return raw


def _verify_classification(
    *,
    ordinal: int,
    row: dict[str, str],
    raw: dict[str, Any],
    prior_signatures: set[str],
) -> None:
    classified = classify_proposal_response(
        MECHANISMS[ordinal - 1],
        ordinal,
        provider_response(raw, label="TS-v5-R3F"),
        prior_semantic_signatures=prior_signatures,
    )
    candidate = classified["candidate"]
    observed = (
        classified["parse_status"], classified["schema_status"],
        classified["duplicate_status"], classified["failure_class"],
        candidate.fingerprint() if candidate else "",
        candidate.semantic_signature() if candidate else "",
    )
    recorded = tuple(row[key] for key in (
        "parse_status", "schema_status", "duplicate_status", "failure_class",
        "candidate_fingerprint", "semantic_signature",
    ))
    if observed != recorded or abs(
        classified["cost"] - float(row["estimated_cost_usd"])
    ) > 5e-13:
        raise D1ControlError("TS-v5-R3F independent classification differs")
    if candidate is not None and not classified["failure_class"]:
        prior_signatures.add(candidate.semantic_signature())


def _verify_attempts(
    *,
    rows: list[dict[str, str]],
    transport: list[dict[str, str]],
    output_root: Path,
    project_root: Path,
) -> dict[str, Any]:
    completed = [row for row in transport if row["event_type"] == "COMPLETED"]
    started = [row for row in transport if row["event_type"] == "STARTED"]
    if (
        len(transport) != 12
        or len(completed) != 6
        or len(started) != 6
        or any(row["sequence"] != "1" for row in transport)
        or any(row["event_type"] not in {"STARTED", "COMPLETED"} for row in transport)
    ):
        raise D1ControlError("TS-v5-R3F transport is not exactly six no-retry completions")
    by_attempt = {row["attempt_id"]: row for row in completed}
    if len(by_attempt) != 6 or {row["attempt_id"] for row in started} != set(by_attempt):
        raise D1ControlError("TS-v5-R3F transport attempt identities differ")
    requests, prior_signatures = request_bundle(), set()
    for ordinal, (row, request) in enumerate(zip(rows, requests, strict=True), start=1):
        raw = _linked_response(
            ordinal=ordinal,
            row=row,
            request=request,
            by_attempt=by_attempt,
            output_root=output_root,
            project_root=project_root,
        )
        _verify_classification(
            ordinal=ordinal,
            row=row,
            raw=raw,
            prior_signatures=prior_signatures,
        )
    return {
        "request_bundle_sha256": sha256_text(canonical_json(requests)),
        "external_request_count": len(started),
        "completed_transport_count": len(completed),
        "transport_retry_count": 0,
        "attempt_count": len(rows),
    }


def audit_batch(
    *,
    release_path: Path,
    output_root: Path,
    attempt_path: Path,
    transport_path: Path,
    project_root: Path = PROJECT_ROOT,
) -> dict[str, Any]:
    protocol = R3FTransportProtocol.load()
    release = R3FExecutionRelease.load(release_path, protocol)
    rows = attempt_rows(attempt_path, release)
    if len(rows) != 6:
        raise D1ControlError("TS-v5-R3F audit requires exactly six attempt rows")
    static = _verify_attempts(
        rows=rows,
        transport=transport_rows(transport_path, release, label="TS-v5-R3F"),
        output_root=output_root,
        project_root=project_root,
    )
    report = json_object(output_root / "ts_v5_r3f_report.json", label="TS-v5-R3F")
    valid = sum(
        not row["failure_class"]
        and row["schema_status"] == "PASS"
        and row["duplicate_status"] == "UNIQUE"
        for row in rows
    )
    cost = sum(float(row["estimated_cost_usd"]) for row in rows)
    gate = batch_gate(len(rows), valid)
    bundle = sha256_text(canonical_json([
        {key: row[key] for key in (
            "attempt_id", "request_sha256", "response_sha256",
            "raw_artifact_sha256", "manifest_sha256", "candidate_fingerprint",
        )}
        for row in rows
    ]))
    checks = {
        "release_identity": report.get("release_sha256") == release.sha256,
        "request_bundle_identity": static["request_bundle_sha256"] == REQUEST_BUNDLE_SHA256,
        "completed_responses_exact": report.get("completed_response_count") == 6,
        "external_requests_exact": report.get("external_request_count") == 6
        and static["external_request_count"] == 6,
        "transport_retries_zero": report.get("transport_retries") == 0
        and static["transport_retry_count"] == 0,
        "cost_recomputed": abs(float(report.get("actual_cost_usd", -1)) - cost) < 5e-13,
        "cost_below_ceiling": cost <= release.batch_hard_ceiling_usd,
        "evidence_bundle": report.get("attempt_evidence_bundle_sha256") == bundle,
        "valid_count_recomputed": report.get("valid_unique_candidate_count") == valid,
        "authoritative_gate": report.get("gate") == gate,
        "no_strategy_execution": all(report.get(key) is False for key in (
            "market_or_effect_read", "parameter_search_or_backtest", "paper_web_or_production",
        )),
        "strategy_not_evaluated": report.get("candidate_effectiveness") == "NOT_EVALUATED",
        "production_authorization_none": report.get("production_authorization") == "none",
    }
    if not all(checks.values()):
        raise D1ControlError("TS-v5-R3F independent audit failed")
    return {
        "schema_version": "ts-v5-r3f-independent-audit-v1",
        "release_sha256": release.sha256,
        "checks": checks,
        "static_evidence": static,
        "actual_cost_usd": cost,
        "valid_unique_candidate_count": valid,
        "authoritative_gate": gate,
        "network_used": False,
        "secret_read": False,
        "candidate_effectiveness": "NOT_EVALUATED",
        "production_authorization": "none",
        "verdict": "PASS",
    }


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
    except (D1ControlError, OSError, RuntimeError, TypeError, ValueError, json.JSONDecodeError):
        print(canonical_json({"status": "FAIL", "error_class": "TSV5R3FResultAuditError"}))
        return 2
    print(canonical_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
