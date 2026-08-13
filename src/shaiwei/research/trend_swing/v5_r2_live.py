"""One-shot four-response TS-v5-R2 DeepSeek contract canary."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable

from shaiwei.config import PROJECT_ROOT
from shaiwei.provenance import code_snapshot_sha256, git_head
from shaiwei.research.provider_contract import D1ControlError, ProviderResponse
from shaiwei.research.trend_swing.v5_canary import preflight as request_preflight
from shaiwei.research.trend_swing.v5_contract import canonical_json, sha256_text
from shaiwei.research.trend_swing.v5_evidence import (
    attempt_rows,
    classify_response,
    persist_completed_attempt,
    response_envelope,
    write_once,
)
from shaiwei.research.trend_swing.v5_live import tls_hostname_probe
from shaiwei.research.trend_swing.v5_prompt import plan_attempt
from shaiwei.research.trend_swing.v5_r2_release import (
    DEFAULT_RELEASE,
    REQUEST_BUNDLE_SHA256,
    V5R2ExecutionRelease,
    create_r2_provider,
)
from shaiwei.research.trend_swing.v5_response_contract import V5ResponseContract, build_request_v2
from shaiwei.research.trend_swing.v5_transport import V5TransportProtocol

DEFAULT_OUTPUT = PROJECT_ROOT / "data/research/trend_swing/ts-v5-r2-canary-001"
DEFAULT_ATTEMPT_LEDGER = PROJECT_ROOT / "ledger/ts_v5_r2_llm_attempts.csv"
DEFAULT_TRANSPORT_LEDGER = PROJECT_ROOT / "ledger/ts_v5_r2_llm_transports.csv"
WORST_CASE_ATTEMPT_USD = (16_000 * 0.435 + 1_800 * 0.87) / 1_000_000


def _gate(rows: list[dict[str, str]]) -> tuple[str, int]:
    valid = sum(
        row["schema_status"] == "PASS"
        and row["duplicate_status"] == "UNIQUE"
        and not row["failure_class"]
        for row in rows
    )
    if len(rows) != 4:
        return "STOP_INCOMPLETE_BATCH", valid
    return ("GO_CONTRACT_CANARY_ONLY" if valid else "STOP_NO_VALID_CANDIDATES"), valid


def _load_release(
    release_path: Path,
) -> tuple[V5TransportProtocol, V5ResponseContract, V5R2ExecutionRelease]:
    protocol = V5TransportProtocol.load()
    contract = V5ResponseContract.load()
    release = V5R2ExecutionRelease.load(release_path, protocol)
    return protocol, contract, release


def run_preflight(
    *, release_path: Path, attempt_path: Path, transport_path: Path,
    runtime_git_head: Callable[[], str] = git_head,
    runtime_code_sha: Callable[[], str] = code_snapshot_sha256,
) -> dict[str, Any]:
    _, contract, release = _load_release(release_path)
    if runtime_git_head() != release.implementation_git_head:
        raise D1ControlError("TS-v5-R2 runtime Git identity differs")
    if runtime_code_sha() != release.code_snapshot_sha256:
        raise D1ControlError("TS-v5-R2 runtime code snapshot differs")
    rows = attempt_rows(attempt_path, release)  # type: ignore[arg-type]
    if rows or transport_path.read_text(encoding="utf-8").splitlines()[1:]:
        raise D1ControlError("TS-v5-R2 preflight requires pristine dedicated ledgers")
    prepared = request_preflight()
    if (
        prepared["request_bundle_sha256"] != REQUEST_BUNDLE_SHA256
        or prepared["response_contract_sha256"] != contract.sha256
    ):
        raise D1ControlError("TS-v5-R2 prepared request bundle differs")
    return {
        "schema_version": "ts-v5-r2-live-preflight-v1",
        "execution_release_sha256": release.sha256,
        "request_bundle_sha256": REQUEST_BUNDLE_SHA256,
        "completed_responses_authorized_exact": 4,
        "batch_hard_ceiling_usd": release.batch_hard_ceiling_usd,
        "attempt_rows": 0, "transport_events": 0, "secret_read": False,
        "provider_calls": 0, "market_or_effect_read": False,
        "production_authorization": "none", "gate": "PASS",
    }


def _terminal_report(
    protocol: V5TransportProtocol, contract: V5ResponseContract,
    release: V5R2ExecutionRelease, rows: list[dict[str, str]], *, code_sha: str, tls_sha: str,
) -> dict[str, Any]:
    gate, valid = _gate(rows)
    return {
        "schema_version": "ts-v5-r2-canary-report-v1",
        "execution_release_id": release.release_id,
        "execution_release_sha256": release.sha256,
        "protocol_sha256": protocol.sha256,
        "response_contract_sha256": contract.sha256,
        "implementation_git_head": release.implementation_git_head,
        "code_snapshot_sha256": code_sha,
        "completed_response_count": len(rows),
        "completed_response_exact_gate": len(rows) == 4,
        "independent_response_count": sum(row["mode"] == "INDEPENDENT" for row in rows),
        "adversarial_response_count": 0,
        "schema_valid_count": sum(row["schema_status"] == "PASS" for row in rows),
        "valid_unique_candidate_count": valid,
        "failure_class_counts": {
            value or "NONE": sum(row["failure_class"] == value for row in rows)
            for value in sorted({row["failure_class"] for row in rows})
        },
        "actual_cost_usd": sum(float(row["estimated_cost_usd"]) for row in rows),
        "batch_hard_ceiling_usd": release.batch_hard_ceiling_usd,
        "cost_gate_pass": sum(float(row["estimated_cost_usd"]) for row in rows)
        <= release.batch_hard_ceiling_usd,
        "attempt_evidence_bundle_sha256": sha256_text(canonical_json([
            {"attempt_id": row["attempt_id"], "response_sha256": row["response_sha256"],
             "manifest_sha256": row["manifest_sha256"]} for row in rows
        ])),
        "tls_certificate_sha256": tls_sha,
        "market_or_effect_read": False, "parameter_search_or_backtest": False,
        "paper_web_or_production": False, "candidate_effectiveness": "NOT_EVALUATED",
        "production_authorization": "none", "gate": gate,
    }


def run_batch(
    *, release_path: Path, output_root: Path, attempt_path: Path, transport_path: Path,
    project_root: Path = PROJECT_ROOT, provider_factory: Callable[..., Any] = create_r2_provider,
    tls_probe: Callable[[V5R2ExecutionRelease], str] = tls_hostname_probe,
    runtime_git_head: Callable[[], str] = git_head,
    runtime_code_sha: Callable[[], str] = code_snapshot_sha256,
) -> dict[str, Any]:
    protocol, contract, release = _load_release(release_path)
    resolved_project, resolved_output = project_root.resolve(), output_root.resolve()
    try:
        relative_output = resolved_output.relative_to(resolved_project).as_posix()
        relative_attempt = attempt_path.resolve().relative_to(resolved_project).as_posix()
        relative_transport = transport_path.resolve().relative_to(resolved_project).as_posix()
    except ValueError as exc:
        raise D1ControlError("TS-v5-R2 runtime path escapes the project") from exc
    if (relative_output, relative_attempt, relative_transport) != (
        release.output_root, release.attempt_ledger, release.transport_ledger
    ) or runtime_git_head() != release.implementation_git_head:
        raise D1ControlError("TS-v5-R2 runtime path or Git identity differs")
    code_sha = runtime_code_sha()
    if code_sha != release.code_snapshot_sha256:
        raise D1ControlError("TS-v5-R2 runtime code snapshot differs")
    report_path = resolved_output / "ts_v5_r2_report.json"
    rows = attempt_rows(attempt_path, release)  # type: ignore[arg-type]
    if len(rows) > 4:
        raise D1ControlError("TS-v5-R2 attempt ledger exceeds the four-response authority")
    if report_path.is_file():
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if report.get("execution_release_sha256") != release.sha256 or len(rows) != 4:
            raise D1ControlError("TS-v5-R2 terminal report identity differs")
        return {**report, "idempotent_reuse": True, "external_api_calls_this_run": 0}
    tls_sha, calls = tls_probe(release), 0
    for ordinal in range(len(rows) + 1, 5):
        rows = attempt_rows(attempt_path, release)  # type: ignore[arg-type]
        if sum(float(row["estimated_cost_usd"]) for row in rows) + WORST_CASE_ATTEMPT_USD > 0.1:
            raise D1ControlError("TS-v5-R2 cost reserve reaches the hard ceiling")
        plan = plan_attempt(protocol.bundle, ordinal)
        request = build_request_v2(protocol.bundle, plan, contract=contract)
        request_payload, request_sha = canonical_json(request), sha256_text(canonical_json(request))
        write_once(resolved_output / "artifacts/requests" / f"{plan.attempt_id}-{request_sha[:12]}.json", request_payload)
        with provider_factory(
            protocol, release=release, attempt_id=plan.attempt_id,
            transport_ledger_path=transport_path,
            artifact_root=resolved_output / "artifacts/provider",
        ) as provider:
            response: ProviderResponse = provider.complete(request)
            calls += provider.external_api_calls
        raw_path = resolved_output / "artifacts/raw" / f"{plan.attempt_id}-{response.source_response_sha256[:12]}.json"
        write_once(raw_path, canonical_json(response_envelope(response)) + "\n")
        classified = classify_response(
            protocol, release, plan, response, parent_fingerprint=None,
            prior_semantic_signatures={row["semantic_signature"] for row in rows if row["semantic_signature"]},
            response_contract=contract,
        )
        persist_completed_attempt(
            protocol=protocol, release=release, plan=plan, response=response,
            classified=classified, request_sha=request_sha, parent_fingerprint=None,
            raw_path=raw_path, attempt_path=attempt_path, output_root=resolved_output,
            code_sha=code_sha, project_root=resolved_project,
            operator="docker-ts-v5-r2",
        )
        print(canonical_json({
            "ordinal": ordinal, "mechanism": plan.mechanism,
            "schema_status": classified["schema_status"],
            "duplicate_status": classified["duplicate_status"],
            "failure_class": classified["failure_class"],
        }), flush=True)
    rows = attempt_rows(attempt_path, release)  # type: ignore[arg-type]
    report = _terminal_report(protocol, contract, release, rows, code_sha=code_sha, tls_sha=tls_sha)
    write_once(report_path, json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return {**report, "idempotent_reuse": False, "external_api_calls_this_run": calls}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, default=DEFAULT_RELEASE)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--attempt-ledger", type=Path, default=DEFAULT_ATTEMPT_LEDGER)
    parser.add_argument("--transport-ledger", type=Path, default=DEFAULT_TRANSPORT_LEDGER)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = run_preflight(
            release_path=args.release, attempt_path=args.attempt_ledger,
            transport_path=args.transport_ledger,
        ) if args.preflight_only else run_batch(
            release_path=args.release, output_root=args.output_root,
            attempt_path=args.attempt_ledger, transport_path=args.transport_ledger,
        )
    except (D1ControlError, OSError, RuntimeError, TypeError, ValueError, json.JSONDecodeError):
        print(canonical_json({"status": "FAIL", "error_class": "TSV5R2ExecutionError"}))
        return 2
    print(canonical_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
