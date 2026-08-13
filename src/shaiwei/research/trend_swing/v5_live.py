"""One-shot TS-v5 DeepSeek batch coordinator over frozen contracts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import socket
import ssl
from typing import Any, Callable

from shaiwei.config import PROJECT_ROOT
from shaiwei.ledger import sha256_file
from shaiwei.provenance import code_snapshot_sha256, git_head
from shaiwei.research.llm_factor_contract import D1ControlError, ProviderResponse
from shaiwei.research.trend_swing.v5_contract import canonical_json, sha256_text
from shaiwei.research.trend_swing.v5_evidence import (
    attempt_rows,
    classify_response,
    persist_completed_attempt,
    response_envelope,
    write_once,
)
from shaiwei.research.trend_swing.v5_models import MechanismCandidate
from shaiwei.research.trend_swing.v5_prompt import build_request, plan_attempt, validate_response
from shaiwei.research.trend_swing.v5_transport import (
    V5ExecutionRelease,
    INDEPENDENT_REQUEST_BUNDLE_SHA256,
    V5TransportProtocol,
    create_live_provider,
)

DEFAULT_RELEASE = PROJECT_ROOT / "config/ts_v5_llm_execution_release_v1.yaml"
DEFAULT_OUTPUT = PROJECT_ROOT / "data/research/trend_swing/ts-v5-llm-batch-001"
DEFAULT_ATTEMPT_LEDGER = PROJECT_ROOT / "ledger/ts_v5_llm_attempts.csv"
DEFAULT_TRANSPORT_LEDGER = PROJECT_ROOT / "ledger/ts_v5_llm_transports.csv"


def tls_hostname_probe(release: V5ExecutionRelease) -> str:
    egress = release.document["egress"]
    host, port = str(egress["host"]), int(egress["port"])
    context = ssl.create_default_context()
    with socket.create_connection((host, port), timeout=10) as raw:
        with context.wrap_socket(raw, server_hostname=host) as connection:
            certificate = connection.getpeercert(binary_form=True)
            if not certificate:
                raise D1ControlError("TS-v5 TLS probe returned no peer certificate")
    return hashlib.sha256(certificate).hexdigest()


def _worst_case_attempt_cost() -> float:
    return (16_000 * 0.435 + 1_800 * 0.87) / 1_000_000


def _load_parent(
    protocol: V5TransportProtocol,
    rows: list[dict[str, str]],
    project_root: Path,
    ordinal: int,
) -> tuple[MechanismCandidate | None, str | None, str | None]:
    if ordinal <= 6:
        return None, None, None
    parent_row = rows[ordinal - 7]
    if int(parent_row["ordinal"]) != ordinal - 6:
        raise D1ControlError("TS-v5 revision parent ordinal differs")
    if not parent_row["failure_class"]:
        raw_path = project_root / parent_row["raw_artifact_path"]
        if not raw_path.is_file() or sha256_file(raw_path) != parent_row["raw_artifact_sha256"]:
            raise D1ControlError("TS-v5 parent response artifact differs")
        envelope = json.loads(raw_path.read_text(encoding="utf-8"))
        parent_plan = plan_attempt(protocol.bundle, ordinal - 6)
        candidate = validate_response(parent_plan, json.loads(envelope["content"]))
        if candidate.fingerprint() != parent_row["candidate_fingerprint"]:
            raise D1ControlError("TS-v5 parent candidate identity differs")
        return candidate, candidate.fingerprint(), None
    return None, parent_row["response_sha256"], parent_row["failure_class"]


def run_preflight(
    *,
    release_path: Path,
    attempt_path: Path,
    transport_path: Path,
    runtime_git_head: Callable[[], str] = git_head,
) -> dict[str, Any]:
    protocol = V5TransportProtocol.load()
    release = V5ExecutionRelease.load(
        release_path,
        protocol,
        independent_request_bundle_sha256=INDEPENDENT_REQUEST_BUNDLE_SHA256,
    )
    if runtime_git_head() != release.implementation_git_head:
        raise D1ControlError("TS-v5 runtime Git identity differs")
    rows = attempt_rows(attempt_path, release)
    if rows or transport_path.read_text(encoding="utf-8").splitlines()[1:]:
        raise D1ControlError("TS-v5 live preflight requires pristine dedicated ledgers")
    requests = [
        build_request(protocol.bundle, plan_attempt(protocol.bundle, ordinal))
        for ordinal in range(1, 7)
    ]
    return {
        "schema_version": "ts-v5-llm-live-preflight-v1",
        "execution_release_sha256": release.sha256,
        "request_bundle_sha256": sha256_text(canonical_json(requests)),
        "completed_responses_authorized_exact": 12,
        "batch_hard_ceiling_usd": release.batch_hard_ceiling_usd,
        "attempt_rows": 0,
        "transport_events": 0,
        "secret_read": False,
        "provider_calls": 0,
        "market_or_effect_read": False,
        "production_authorization": "none",
        "gate": "PASS",
    }


def _terminal_report(
    protocol: V5TransportProtocol,
    release: V5ExecutionRelease,
    rows: list[dict[str, str]],
    *,
    code_sha: str,
    tls_sha: str,
) -> dict[str, Any]:
    return {
        "schema_version": "ts-v5-llm-research-report-v1",
        "execution_release_id": release.release_id,
        "execution_release_sha256": release.sha256,
        "protocol_sha256": protocol.sha256,
        "implementation_git_head": release.implementation_git_head,
        "code_snapshot_sha256": code_sha,
        "completed_response_count": len(rows),
        "completed_response_exact_gate": len(rows) == 12,
        "independent_response_count": sum(row["mode"] == "INDEPENDENT" for row in rows),
        "adversarial_response_count": sum(
            row["mode"] == "ADVERSARIAL_REVISION" for row in rows
        ),
        "schema_valid_count": sum(row["schema_status"] == "PASS" for row in rows),
        "unique_candidate_count": sum(row["duplicate_status"] == "UNIQUE" for row in rows),
        "duplicate_candidate_count": sum(row["duplicate_status"] == "DUPLICATE" for row in rows),
        "failure_class_counts": {
            value or "NONE": sum(row["failure_class"] == value for row in rows)
            for value in sorted({row["failure_class"] for row in rows})
        },
        "actual_cost_usd": sum(float(row["estimated_cost_usd"]) for row in rows),
        "batch_hard_ceiling_usd": release.batch_hard_ceiling_usd,
        "cost_gate_pass": sum(float(row["estimated_cost_usd"]) for row in rows)
        <= release.batch_hard_ceiling_usd,
        "attempt_evidence_bundle_sha256": sha256_text(
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
        ),
        "tls_certificate_sha256": tls_sha,
        "market_or_effect_read": False,
        "parameter_search_or_backtest": False,
        "paper_web_or_production": False,
        "candidate_effectiveness": "NOT_EVALUATED",
        "production_authorization": "none",
        "gate": "GO_CANDIDATES_ONLY" if len(rows) == 12 else "STOP_INCOMPLETE_BATCH",
    }


def run_batch(
    *,
    release_path: Path,
    output_root: Path,
    attempt_path: Path,
    transport_path: Path,
    project_root: Path = PROJECT_ROOT,
    provider_factory: Callable[..., Any] = create_live_provider,
    tls_probe: Callable[[V5ExecutionRelease], str] = tls_hostname_probe,
    runtime_git_head: Callable[[], str] = git_head,
    runtime_code_sha: Callable[[], str] = code_snapshot_sha256,
) -> dict[str, Any]:
    output_root = output_root.resolve()
    if not output_root.is_relative_to(project_root.resolve()):
        raise D1ControlError("TS-v5 output root escapes the project")
    protocol = V5TransportProtocol.load()
    release = V5ExecutionRelease.load(
        release_path,
        protocol,
        independent_request_bundle_sha256=INDEPENDENT_REQUEST_BUNDLE_SHA256,
    )
    relative_output = output_root.relative_to(project_root.resolve()).as_posix()
    relative_attempt = attempt_path.resolve().relative_to(project_root.resolve()).as_posix()
    relative_transport = transport_path.resolve().relative_to(project_root.resolve()).as_posix()
    if (
        relative_output != release.output_root
        or relative_attempt != release.attempt_ledger
        or relative_transport != release.transport_ledger
    ):
        raise D1ControlError("TS-v5 live paths differ from the frozen release")
    if runtime_git_head() != release.implementation_git_head:
        raise D1ControlError("TS-v5 runtime Git identity differs")
    report_path = output_root / "ts_v5_llm_report.json"
    rows = attempt_rows(attempt_path, release)
    if report_path.is_file():
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if report.get("execution_release_sha256") != release.sha256 or len(rows) != 12:
            raise D1ControlError("TS-v5 terminal report identity differs")
        return {**report, "idempotent_reuse": True, "external_api_calls_this_run": 0}
    tls_sha, code_sha, external_calls = tls_probe(release), runtime_code_sha(), 0
    if code_sha != release.code_snapshot_sha256:
        raise D1ControlError("TS-v5 runtime code snapshot differs from the frozen release")
    for ordinal in range(len(rows) + 1, 13):
        rows = attempt_rows(attempt_path, release)
        spent = sum(float(row["estimated_cost_usd"]) for row in rows)
        if spent + _worst_case_attempt_cost() > release.batch_hard_ceiling_usd:
            raise D1ControlError("TS-v5 cost reserve reaches the hard ceiling")
        plan = plan_attempt(protocol.bundle, ordinal)
        parent, parent_fingerprint, parent_failure = _load_parent(
            protocol, rows, project_root, ordinal
        )
        request = build_request(
            protocol.bundle,
            plan,
            parent=parent,
            parent_attempt_fingerprint=parent_fingerprint,
            parent_failure_class=parent_failure,
        )
        request_payload = canonical_json(request)
        request_sha = sha256_text(request_payload)
        write_once(
            output_root / "artifacts/requests" / f"{plan.attempt_id}-{request_sha[:12]}.json",
            request_payload,
        )
        with provider_factory(
            protocol,
            release=release,
            attempt_id=plan.attempt_id,
            transport_ledger_path=transport_path,
            artifact_root=output_root / "artifacts/provider",
        ) as provider:
            response: ProviderResponse = provider.complete(request)
            external_calls += provider.external_api_calls
        raw_path = output_root / "artifacts/raw" / (
            f"{plan.attempt_id}-{response.source_response_sha256[:12]}.json"
        )
        write_once(raw_path, canonical_json(response_envelope(response)) + "\n")
        prior_signatures = {row["semantic_signature"] for row in rows if row["semantic_signature"]}
        classified = classify_response(
            protocol,
            release,
            plan,
            response,
            parent_fingerprint=parent_fingerprint,
            prior_semantic_signatures=prior_signatures,
        )
        persist_completed_attempt(
            protocol=protocol,
            release=release,
            plan=plan,
            response=response,
            classified=classified,
            request_sha=request_sha,
            parent_fingerprint=parent_fingerprint,
            raw_path=raw_path,
            attempt_path=attempt_path,
            output_root=output_root,
            code_sha=code_sha,
            project_root=project_root,
        )
        print(
            canonical_json(
                {
                    "ordinal": ordinal,
                    "mechanism": plan.mechanism,
                    "mode": plan.mode,
                    "schema_status": classified["schema_status"],
                    "duplicate_status": classified["duplicate_status"],
                    "failure_class": classified["failure_class"],
                }
            ),
            flush=True,
        )
    rows = attempt_rows(attempt_path, release)
    report = _terminal_report(protocol, release, rows, code_sha=code_sha, tls_sha=tls_sha)
    write_once(report_path, json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return {**report, "idempotent_reuse": False, "external_api_calls_this_run": external_calls}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, default=DEFAULT_RELEASE)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--attempt-ledger", type=Path, default=DEFAULT_ATTEMPT_LEDGER)
    parser.add_argument("--transport-ledger", type=Path, default=DEFAULT_TRANSPORT_LEDGER)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = (
            run_preflight(
                release_path=args.release,
                attempt_path=args.attempt_ledger,
                transport_path=args.transport_ledger,
            )
            if args.preflight_only
            else run_batch(
                release_path=args.release,
                output_root=args.output_root,
                attempt_path=args.attempt_ledger,
                transport_path=args.transport_ledger,
            )
        )
    except (D1ControlError, OSError, RuntimeError, TypeError, ValueError):
        print(canonical_json({"status": "FAIL", "error_class": "TSV5LLMExecutionError"}))
        return 2
    print(canonical_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
