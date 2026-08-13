"""One-shot no-retry six-response runner for an approved TS-v5-R3F release."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable

from shaiwei.config import PROJECT_ROOT
from shaiwei.provenance import code_snapshot_sha256, git_head
from shaiwei.research.provider_contract import D1ControlError, ProviderResponse
from shaiwei.research.trend_swing.v5_contract import canonical_json, sha256_text
from shaiwei.research.trend_swing.v5_evidence import (
    attempt_rows,
    persist_completed_attempt,
    response_envelope,
    write_once,
)
from shaiwei.research.trend_swing.v5_live import tls_hostname_probe
from shaiwei.research.trend_swing.v5_prompt import AttemptPlan
from shaiwei.research.trend_swing.v5_r3f_canary import (
    MECHANISMS,
    R3FTransportProtocol,
    batch_gate,
    classify_proposal_response,
    request_bundle,
)
from shaiwei.research.trend_swing.v5_r3f_release import (
    DEFAULT_RELEASE,
    REQUEST_BUNDLE_SHA256,
    R3FExecutionRelease,
    create_r3f_provider,
)

DEFAULT_OUTPUT = PROJECT_ROOT / "data/research/trend_swing/ts-v5-r3f-canary-001"
DEFAULT_ATTEMPT_LEDGER = PROJECT_ROOT / "ledger/ts_v5_r3f_llm_attempts.csv"
DEFAULT_TRANSPORT_LEDGER = PROJECT_ROOT / "ledger/ts_v5_r3f_llm_transports.csv"
WORST_CASE_ATTEMPT_USD = (16_000 * 0.435 + 1_800 * 0.87) / 1_000_000


def _load_release(path: Path) -> tuple[R3FTransportProtocol, R3FExecutionRelease]:
    protocol = R3FTransportProtocol.load()
    return protocol, R3FExecutionRelease.load(path, protocol)


def _runtime_relative(path: Path, project_root: Path) -> str:
    try:
        return path.resolve(strict=True).relative_to(
            project_root.resolve(strict=True)
        ).as_posix()
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        raise D1ControlError("TS-v5-R3F runtime path escapes the project") from exc


def run_preflight(
    *,
    release_path: Path,
    attempt_path: Path,
    transport_path: Path,
    runtime_git_head: Callable[[], str] = git_head,
    runtime_code_sha: Callable[[], str] = code_snapshot_sha256,
) -> dict[str, Any]:
    protocol, release = _load_release(release_path)
    if (
        runtime_git_head() != release.implementation_git_head
        or runtime_code_sha() != release.code_snapshot_sha256
        or protocol.document["attempt_budget"]["maximum_transport_retries_per_attempt"] != 0
    ):
        raise D1ControlError("TS-v5-R3F runtime identity or no-retry contract differs")
    if attempt_rows(attempt_path, release) or transport_path.read_text(
        encoding="utf-8"
    ).splitlines()[1:]:
        raise D1ControlError("TS-v5-R3F preflight requires pristine dedicated ledgers")
    bundle = sha256_text(canonical_json(request_bundle()))
    if bundle != REQUEST_BUNDLE_SHA256:
        raise D1ControlError("TS-v5-R3F prepared request bundle differs")
    return {
        "schema_version": "ts-v5-r3f-live-preflight-v1",
        "release_sha256": release.sha256,
        "request_bundle_sha256": bundle,
        "completed_responses_authorized_exact": 6,
        "external_request_maximum": 6,
        "maximum_transport_attempts_per_slot": 1,
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
    release: R3FExecutionRelease,
    rows: list[dict[str, str]],
    *,
    tls_sha: str,
) -> dict[str, Any]:
    valid = sum(
        not row["failure_class"]
        and row["schema_status"] == "PASS"
        and row["duplicate_status"] == "UNIQUE"
        for row in rows
    )
    return {
        "schema_version": "ts-v5-r3f-canary-report-v1",
        "release_sha256": release.sha256,
        "request_bundle_sha256": REQUEST_BUNDLE_SHA256,
        "completed_response_count": len(rows),
        "external_request_count": len(rows),
        "valid_unique_candidate_count": valid,
        "actual_cost_usd": sum(float(row["estimated_cost_usd"]) for row in rows),
        "batch_hard_ceiling_usd": release.batch_hard_ceiling_usd,
        "attempt_evidence_bundle_sha256": sha256_text(canonical_json([
            {key: row[key] for key in (
                "attempt_id", "request_sha256", "response_sha256",
                "raw_artifact_sha256", "manifest_sha256", "candidate_fingerprint",
            )}
            for row in rows
        ])),
        "tls_certificate_sha256": tls_sha,
        "transport_retries": 0,
        "market_or_effect_read": False,
        "parameter_search_or_backtest": False,
        "paper_web_or_production": False,
        "candidate_effectiveness": "NOT_EVALUATED",
        "production_authorization": "none",
        "gate": batch_gate(len(rows), valid),
    }


def _run_attempt(
    *,
    ordinal: int,
    request: dict[str, Any],
    protocol: R3FTransportProtocol,
    release: R3FExecutionRelease,
    output_root: Path,
    attempt_path: Path,
    transport_path: Path,
    prior_signatures: set[str],
    provider_factory: Callable[..., Any],
    project_root: Path,
    code_sha: str,
) -> int:
    task = json.loads(request["messages"][1]["content"])
    request_sha = sha256_text(canonical_json(request))
    request_path = output_root / "artifacts/requests" / (
        f"{task['attempt_id']}-{request_sha[:12]}.json"
    )
    write_once(request_path, canonical_json(request))
    with provider_factory(
        protocol,
        release=release,
        attempt_id=task["attempt_id"],
        transport_ledger_path=transport_path,
        artifact_root=output_root / "artifacts/provider",
    ) as provider:
        response: ProviderResponse = provider.complete(request)
        calls = provider.external_api_calls
    if calls != 1:
        raise D1ControlError("TS-v5-R3F slot did not use exactly one transport attempt")
    raw_path = output_root / "artifacts/raw" / (
        f"{task['attempt_id']}-{response.source_response_sha256[:12]}.json"
    )
    write_once(raw_path, canonical_json(response_envelope(response)) + "\n")
    classified = classify_proposal_response(
        MECHANISMS[ordinal - 1],
        ordinal,
        response,
        prior_semantic_signatures=prior_signatures,
    )
    plan = AttemptPlan(task["attempt_id"], ordinal, MECHANISMS[ordinal - 1], "INDEPENDENT")
    persist_completed_attempt(
        protocol=protocol,  # type: ignore[arg-type]
        release=release,  # type: ignore[arg-type]
        plan=plan,
        response=response,
        classified=classified,
        request_sha=request_sha,
        parent_fingerprint=None,
        raw_path=raw_path,
        attempt_path=attempt_path,
        output_root=output_root,
        code_sha=code_sha,
        project_root=project_root,
        operator="docker-ts-v5-r3f",
    )
    candidate = classified["candidate"]
    if candidate is not None and not classified["failure_class"]:
        prior_signatures.add(candidate.semantic_signature())
    return calls


def run_batch(
    *,
    release_path: Path,
    output_root: Path,
    attempt_path: Path,
    transport_path: Path,
    project_root: Path = PROJECT_ROOT,
    provider_factory: Callable[..., Any] = create_r3f_provider,
    tls_probe: Callable[[R3FExecutionRelease], str] = tls_hostname_probe,
    runtime_git_head: Callable[[], str] = git_head,
    runtime_code_sha: Callable[[], str] = code_snapshot_sha256,
) -> dict[str, Any]:
    protocol, release = _load_release(release_path)
    code_sha = runtime_code_sha()
    if (
        runtime_git_head() != release.implementation_git_head
        or code_sha != release.code_snapshot_sha256
        or _runtime_relative(output_root, project_root) != release.output_root
        or _runtime_relative(attempt_path, project_root) != release.attempt_ledger
        or _runtime_relative(transport_path, project_root) != release.transport_ledger
    ):
        raise D1ControlError("TS-v5-R3F runtime path or identity differs")
    report_path = output_root / "ts_v5_r3f_report.json"
    rows = attempt_rows(attempt_path, release)
    if report_path.is_file():
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if report.get("release_sha256") != release.sha256 or len(rows) != 6:
            raise D1ControlError("TS-v5-R3F terminal report identity differs")
        return {**report, "idempotent_reuse": True, "external_api_calls_this_run": 0}
    if rows or transport_path.read_text(encoding="utf-8").splitlines()[1:]:
        raise D1ControlError("TS-v5-R3F incomplete prior batch cannot be resumed")
    tls_sha, calls, requests = tls_probe(release), 0, request_bundle()
    prior_signatures: set[str] = set()
    for ordinal, request in enumerate(requests, start=1):
        if calls >= release.completed_responses_exact:
            raise D1ControlError("TS-v5-R3F external request ceiling reached")
        spent = sum(
            float(row["estimated_cost_usd"])
            for row in attempt_rows(attempt_path, release)
        )
        if spent + WORST_CASE_ATTEMPT_USD > release.batch_hard_ceiling_usd:
            raise D1ControlError("TS-v5-R3F cost reserve reaches the hard ceiling")
        calls += _run_attempt(
            ordinal=ordinal,
            request=request,
            protocol=protocol,
            release=release,
            output_root=output_root,
            attempt_path=attempt_path,
            transport_path=transport_path,
            prior_signatures=prior_signatures,
            provider_factory=provider_factory,
            project_root=project_root,
            code_sha=code_sha,
        )
    rows = attempt_rows(attempt_path, release)
    report = _terminal_report(release, rows, tls_sha=tls_sha)
    write_once(
        report_path,
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
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
        shared = {
            "release_path": args.release,
            "attempt_path": args.attempt_ledger,
            "transport_path": args.transport_ledger,
        }
        result = run_preflight(**shared) if args.preflight_only else run_batch(
            **shared, output_root=args.output_root
        )
    except (D1ControlError, OSError, RuntimeError, TypeError, ValueError, json.JSONDecodeError):
        print(canonical_json({"status": "FAIL", "error_class": "TSV5R3FExecutionError"}))
        return 2
    print(canonical_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
