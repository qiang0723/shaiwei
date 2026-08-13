"""Independent offline audit for the four-response TS-v5-R2 canary."""

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
from shaiwei.research.provider_contract import D1ControlError, ProviderResponse
from shaiwei.research.trend_swing.v5_canary import MECHANISMS
from shaiwei.research.trend_swing.v5_contract import canonical_json, sha256_text
from shaiwei.research.trend_swing.v5_evidence import (
    attempt_rows,
    classify_response,
    write_once,
)
from shaiwei.research.trend_swing.v5_prompt import plan_attempt
from shaiwei.research.trend_swing.v5_r2_live import (
    DEFAULT_ATTEMPT_LEDGER,
    DEFAULT_OUTPUT,
    DEFAULT_RELEASE,
    DEFAULT_TRANSPORT_LEDGER,
    _gate,
)
from shaiwei.research.trend_swing.v5_r2_release import V5R2ExecutionRelease
from shaiwei.research.trend_swing.v5_response_contract import (
    V5ResponseContract,
    build_request_v2,
)
from shaiwei.research.trend_swing.v5_transport import V5TransportProtocol


def _json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise D1ControlError(f"TS-v5-R2 audit JSON is invalid: {path.name}") from exc
    if not isinstance(value, dict):
        raise D1ControlError("TS-v5-R2 audit JSON must be an object")
    return value


def _transport_rows(path: Path, release: V5R2ExecutionRelease) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    if tuple(reader.fieldnames or ()) != TRANSPORT_LEDGER_HEADER_V2:
        raise D1ControlError("TS-v5-R2 transport ledger schema differs")
    if len({row["event_id"] for row in rows}) != len(rows):
        raise D1ControlError("TS-v5-R2 transport event ids are duplicated")
    if any(
        row["execution_release_id"] != release.release_id
        or row["execution_release_sha256"] != release.sha256
        for row in rows
    ):
        raise D1ControlError("TS-v5-R2 transport release differs")
    if any(row["event_type"] == "BILLING_UNCERTAIN" for row in rows):
        raise D1ControlError("TS-v5-R2 audit found billing uncertainty")
    return rows


def _provider_response(document: dict[str, Any]) -> ProviderResponse:
    try:
        return ProviderResponse(
            model=str(document["model"]),
            content=str(document["content"]),
            reasoning_content=str(document["reasoning_content"]),
            finish_reason=str(document["finish_reason"]),
            usage=document["usage"],
            completed_at=str(document["completed_at"]),
            sensitive_output_detected=bool(document["sensitive_output_detected"]),
            source_response_sha256=str(document["source_response_sha256"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise D1ControlError("TS-v5-R2 raw envelope schema differs") from exc


def _verify_attempts(
    *, rows: list[dict[str, str]], transport: list[dict[str, str]],
    protocol: V5TransportProtocol, contract: V5ResponseContract,
    release: V5R2ExecutionRelease, output_root: Path, project_root: Path,
) -> dict[str, Any]:
    completed = [row for row in transport if row["event_type"] == "COMPLETED"]
    by_attempt = {row["attempt_id"]: row for row in completed}
    if len(completed) != 4 or len(by_attempt) != 4:
        raise D1ControlError("TS-v5-R2 audit requires exactly four completed transports")
    request_documents: list[dict[str, Any]] = []
    prior_signatures: set[str] = set()
    for ordinal, row in enumerate(rows, start=1):
        plan = plan_attempt(protocol.bundle, ordinal)
        if row["mechanism"] != MECHANISMS[ordinal - 1] or row["mode"] != "INDEPENDENT":
            raise D1ControlError("TS-v5-R2 attempt schedule differs")
        expected_request = build_request_v2(protocol.bundle, plan, contract=contract)
        request_path = output_root / "artifacts/requests" / (
            f"{row['attempt_id']}-{row['request_sha256'][:12]}.json"
        )
        request_text = request_path.read_text(encoding="utf-8")
        if request_text != canonical_json(expected_request):
            raise D1ControlError("TS-v5-R2 outbound request differs")
        if re.search(
            r"\b\d{6}\.(?:SH|SZ|BJ)\b|/(?:Users|private|workspace)/|sk-[A-Za-z0-9]",
            request_text,
        ):
            raise D1ControlError("TS-v5-R2 request contains a forbidden identity")
        request_documents.append(expected_request)
        raw_path = project_root / row["raw_artifact_path"]
        manifest_path = project_root / row["manifest_path"]
        if (
            sha256_file(request_path) != row["request_sha256"]
            or sha256_file(raw_path) != row["raw_artifact_sha256"]
            or sha256_file(manifest_path) != row["manifest_sha256"]
        ):
            raise D1ControlError("TS-v5-R2 immutable attempt artifact differs")
        raw, manifest = _json_object(raw_path), _json_object(manifest_path)
        event = by_attempt.get(row["attempt_id"])
        if (
            event is None
            or event["request_sha256"] != row["request_sha256"]
            or event["source_response_sha256"] != row["response_sha256"]
            or raw.get("source_response_sha256") != row["response_sha256"]
            or manifest.get("response_sha256") != row["response_sha256"]
        ):
            raise D1ControlError("TS-v5-R2 attempt linkage differs")
        provider_path = output_root / "artifacts/provider" / event["response_artifact_path"]
        if sha256_file(provider_path) != event["response_artifact_sha256"]:
            raise D1ControlError("TS-v5-R2 provider artifact differs")
        classified = classify_response(
            protocol, release, plan, _provider_response(raw),
            parent_fingerprint=None, prior_semantic_signatures=prior_signatures,
            response_contract=contract,
        )
        candidate = classified["candidate"]
        observed = (
            classified["parse_status"], classified["schema_status"],
            classified["duplicate_status"], classified["failure_class"],
            candidate.fingerprint() if candidate else "",
            candidate.semantic_signature() if candidate else "",
        )
        recorded = tuple(
            row[key] for key in (
                "parse_status", "schema_status", "duplicate_status", "failure_class",
                "candidate_fingerprint", "semantic_signature",
            )
        )
        if observed != recorded or abs(classified["cost"] - float(row["estimated_cost_usd"])) > 5e-13:
            raise D1ControlError("TS-v5-R2 independent classification differs")
        if candidate and not classified["failure_class"]:
            prior_signatures.add(candidate.semantic_signature())
    return {
        "request_bundle_sha256": sha256_text(canonical_json(request_documents)),
        "completed_transport_count": len(completed),
        "attempt_count": len(rows),
    }


def audit_batch(
    *, release_path: Path, output_root: Path, attempt_path: Path, transport_path: Path,
    project_root: Path = PROJECT_ROOT,
) -> dict[str, Any]:
    protocol, contract = V5TransportProtocol.load(), V5ResponseContract.load()
    release = V5R2ExecutionRelease.load(release_path, protocol)
    rows = attempt_rows(attempt_path, release)  # type: ignore[arg-type]
    if len(rows) != 4:
        raise D1ControlError("TS-v5-R2 audit requires exactly four attempt rows")
    transport = _transport_rows(transport_path, release)
    static = _verify_attempts(
        rows=rows, transport=transport, protocol=protocol, contract=contract,
        release=release, output_root=output_root, project_root=project_root,
    )
    report = _json_object(output_root / "ts_v5_r2_report.json")
    bundle = sha256_text(canonical_json([
        {"attempt_id": row["attempt_id"], "response_sha256": row["response_sha256"],
         "manifest_sha256": row["manifest_sha256"]} for row in rows
    ]))
    total_cost = sum(float(row["estimated_cost_usd"]) for row in rows)
    gate, valid = _gate(rows)
    checks = {
        "release_identity": report.get("execution_release_sha256") == release.sha256,
        "request_bundle_identity": static["request_bundle_sha256"]
        == release.document["frozen_contract"]["request_bundle_sha256"],
        "completed_responses_exact": report.get("completed_response_count") == 4,
        "independent_only": report.get("independent_response_count") == 4
        and report.get("adversarial_response_count") == 0,
        "cost_recomputed": abs(float(report.get("actual_cost_usd", -1)) - total_cost) < 5e-13,
        "cost_below_ceiling": total_cost <= release.batch_hard_ceiling_usd,
        "evidence_bundle": report.get("attempt_evidence_bundle_sha256") == bundle,
        "authoritative_gate": report.get("gate") == gate,
        "no_market_effect_or_strategy_execution": all(
            report.get(key) is False for key in (
                "market_or_effect_read", "parameter_search_or_backtest", "paper_web_or_production",
            )
        ),
        "strategy_not_evaluated": report.get("candidate_effectiveness") == "NOT_EVALUATED",
        "production_authorization_none": report.get("production_authorization") == "none",
    }
    if not all(checks.values()):
        raise D1ControlError("TS-v5-R2 independent audit failed")
    return {
        "schema_version": "ts-v5-r2-independent-audit-v1",
        "execution_release_sha256": release.sha256,
        "checks": checks, "static_evidence": static,
        "actual_cost_usd": total_cost, "valid_candidate_count": valid,
        "authoritative_gate": gate, "network_used": False, "secret_read": False,
        "candidate_effectiveness": "NOT_EVALUATED",
        "production_authorization": "none", "verdict": "PASS",
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
            release_path=args.release, output_root=args.output_root,
            attempt_path=args.attempt_ledger, transport_path=args.transport_ledger,
        )
        if args.write_report:
            write_once(args.write_report, json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    except (D1ControlError, OSError, RuntimeError, TypeError, ValueError, json.JSONDecodeError):
        print(canonical_json({"status": "FAIL", "error_class": "TSV5R2AuditError"}))
        return 2
    print(canonical_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
