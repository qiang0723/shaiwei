"""One-shot DeepSeek execution for the frozen M1-2 STAR50 Top2 review."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

from shaiwei.config import PROJECT_ROOT
from shaiwei.ledger import append_llm_factor_review, sha256_file
from shaiwei.provenance import code_snapshot_sha256, git_head
from shaiwei.research.deepseek_client import create_live_deepseek_provider
from shaiwei.research.llm_factor import (
    D1ControlError,
    _has_sensitive_output,
    _response_envelope,
    _validate_usage,
)
from shaiwei.research.llm_factor_live import tls_hostname_probe
from shaiwei.research.llm_review_semantics import PASS as SEMANTIC_PASS
from shaiwei.research.m1_star50_review_contract import (
    DEFAULT_PROTOCOL_PATH,
    M1ReviewProtocol,
    build_review_request,
    canonical_json,
    plan_review,
    validate_review_document,
    worst_case_cost,
)
from shaiwei.research.m1_star50_review_evidence import (
    build_terminal_report,
    verify_static_evidence,
)
from shaiwei.research.m1_star50_review_release import (
    DEFAULT_RELEASE_PATH,
    M1ReviewRelease,
)


REVIEW_LEDGER_HEADER = (
    "review_id",
    "protocol_id",
    "execution_release_id",
    "execution_release_sha256",
    "candidate_id",
    "review_ordinal",
    "role",
    "completed_at",
    "provider",
    "requested_model",
    "returned_model",
    "protocol_sha256",
    "prompt_sha256",
    "request_sha256",
    "response_sha256",
    "code_snapshot_sha256",
    "prompt_tokens",
    "prompt_cache_hit_tokens",
    "prompt_cache_miss_tokens",
    "completion_tokens",
    "estimated_cost_usd",
    "parse_status",
    "schema_status",
    "semantic_status",
    "semantic_reason_codes_json",
    "inspected_text_sha256",
    "role_verdict",
    "critical_findings",
    "major_findings",
    "minor_findings",
    "failure_class",
    "raw_artifact_path",
    "raw_artifact_sha256",
    "manifest_path",
    "manifest_sha256",
    "operator",
)


def _write_once(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        if path.read_text(encoding="utf-8") != payload:
            raise D1ControlError(f"immutable M1-2 artifact differs: {path.name}")
        return
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        temporary.write_text(payload, encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _rows(path: Path) -> list[dict[str, str]]:
    header = ",".join(REVIEW_LEDGER_HEADER) + "\n"
    if not path.is_file():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(header, encoding="utf-8")
    if path.read_text(encoding="utf-8").splitlines()[:1] != [header.rstrip()]:
        raise D1ControlError("M1-2 review ledger header differs")
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    ids = [row["review_id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise D1ControlError("M1-2 review ledger contains duplicate ids")
    return rows


def _finding_counts(review: Any | None) -> dict[str, int]:
    return {
        severity: sum(item.severity == severity for item in review.findings) if review else 0
        for severity in ("critical", "major", "minor")
    }


def run_reviews(
    *, protocol_path: Path, release_path: Path, output_root: Path
) -> dict[str, Any]:
    output_root = output_root.resolve()
    if not output_root.is_relative_to(PROJECT_ROOT.resolve()):
        raise D1ControlError("M1-2 output root escapes the project")
    protocol = M1ReviewProtocol.load(protocol_path)
    release = M1ReviewRelease.load(release_path, protocol)
    if git_head() != release.implementation_git_head:
        raise D1ControlError("M1-2 runtime Git identity differs from the frozen image")
    review_path = PROJECT_ROOT / release.document["ledgers"]["review"]
    transport_path = PROJECT_ROOT / release.document["ledgers"]["transport"]
    rows = [row for row in _rows(review_path) if row["execution_release_id"] == release.release_id]
    if [int(row["review_ordinal"]) for row in rows] != list(range(1, len(rows) + 1)):
        raise D1ControlError("M1-2 partial review is not a contiguous prefix")
    report_path = output_root / "m1_2_review_report.json"
    if report_path.is_file():
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if report.get("static_evidence") != verify_static_evidence(
            rows, transport_path, output_root, release
        ):
            raise D1ControlError("M1-2 terminal report evidence differs")
        return {**report, "idempotent_reuse": True, "external_api_calls_this_run": 0}

    tls_sha = tls_hostname_probe(release)  # type: ignore[arg-type]
    code_sha = code_snapshot_sha256()
    external_calls = 0
    fatal_existing = any(row["failure_class"] for row in rows)
    if not fatal_existing:
        for ordinal in range(len(rows) + 1, 9):
            current = [
                row for row in _rows(review_path) if row["execution_release_id"] == release.release_id
            ]
            if sum(float(row["estimated_cost_usd"]) for row in current) + worst_case_cost(
                protocol
            ) > release.batch_hard_ceiling_usd + 1e-12:
                raise D1ControlError("M1-2 cost reserve reaches the hard ceiling")
            plan = plan_review(protocol, ordinal)
            request = build_review_request(protocol, plan)
            request_payload = canonical_json(request) + "\n"
            request_sha = hashlib.sha256(request_payload.encode("utf-8")).hexdigest()
            request_path = output_root / "artifacts/requests" / (
                f"{plan.review_id}-{request_sha[:12]}.json"
            )
            _write_once(request_path, request_payload)
            with create_live_deepseek_provider(
                protocol,  # type: ignore[arg-type]
                execution_release=release,  # type: ignore[arg-type]
                attempt_id=plan.review_id,
                transport_ledger_path=transport_path,
                artifact_root=output_root / "artifacts/provider",
                operator="docker-m1-star50-review",
            ) as provider:
                response = provider.complete(request)
                external_calls += provider.external_api_calls
            usage, cost = _validate_usage(protocol, response.usage)  # type: ignore[arg-type]
            raw_payload = canonical_json(_response_envelope(response)) + "\n"
            raw_path = output_root / "artifacts/raw" / (
                f"{plan.review_id}-{response.source_response_sha256[:12]}.json"
            )
            _write_once(raw_path, raw_payload)
            review = None
            semantic = None
            parse_status = schema_status = "PASS"
            failure_class = ""
            try:
                if response.model != release.response_model_identity:
                    raise D1ControlError("M1-2 provider returned a different model")
                if _has_sensitive_output(response):
                    raise D1ControlError("M1-2 provider response contains sensitive output")
                document = json.loads(response.content)
                review, semantic = validate_review_document(protocol, plan, document)
                if semantic.status != SEMANTIC_PASS:
                    failure_class = "semantic_contract_violation"
            except json.JSONDecodeError:
                parse_status, schema_status, failure_class = "FAIL", "NOT_EVALUATED", "json_invalid"
            except (TypeError, ValueError):
                schema_status, failure_class = "FAIL", "schema_invalid"
            counts = _finding_counts(review)
            semantic_status = semantic.status if semantic else "NOT_EVALUATED"
            reasons = list(semantic.reason_codes) if semantic else []
            manifest = {
                "schema_version": "m1-star50-review-artifact-manifest-v1",
                "review_id": plan.review_id,
                "candidate_id": plan.candidate.candidate_id,
                "review_ordinal": ordinal,
                "role": plan.role,
                "request_sha256": request_sha,
                "response_sha256": response.source_response_sha256,
                "raw_artifact_sha256": sha256_file(raw_path),
                "parse_status": parse_status,
                "schema_status": schema_status,
                "semantic_status": semantic_status,
                "semantic_reason_codes": reasons,
                "inspected_text_sha256": semantic.inspected_text_sha256 if semantic else "",
                "role_verdict": review.role_verdict if review else "",
                "finding_counts": counts,
                "failure_class": failure_class,
                "protocol_sha256": protocol.sha256,
                "execution_release_sha256": release.sha256,
            }
            manifest_path = output_root / "artifacts/manifests" / f"{plan.review_id}.json"
            _write_once(
                manifest_path,
                json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            )
            row = {
                "review_id": plan.review_id,
                "protocol_id": protocol.document["protocol_id"],
                "execution_release_id": release.release_id,
                "execution_release_sha256": release.sha256,
                "candidate_id": plan.candidate.candidate_id,
                "review_ordinal": str(ordinal),
                "role": plan.role,
                "completed_at": response.completed_at,
                "provider": protocol.provider_name,
                "requested_model": protocol.requested_model,
                "returned_model": response.model,
                "protocol_sha256": protocol.sha256,
                "prompt_sha256": protocol.prompt_sha256,
                "request_sha256": request_sha,
                "response_sha256": response.source_response_sha256,
                "code_snapshot_sha256": code_sha,
                "prompt_tokens": str(usage["prompt_tokens"]),
                "prompt_cache_hit_tokens": str(usage["prompt_cache_hit_tokens"]),
                "prompt_cache_miss_tokens": str(usage["prompt_cache_miss_tokens"]),
                "completion_tokens": str(usage["completion_tokens"]),
                "estimated_cost_usd": f"{cost:.12f}",
                "parse_status": parse_status,
                "schema_status": schema_status,
                "semantic_status": semantic_status,
                "semantic_reason_codes_json": canonical_json(reasons),
                "inspected_text_sha256": semantic.inspected_text_sha256 if semantic else "",
                "role_verdict": review.role_verdict if review else "",
                "critical_findings": str(counts["critical"]),
                "major_findings": str(counts["major"]),
                "minor_findings": str(counts["minor"]),
                "failure_class": failure_class,
                "raw_artifact_path": raw_path.relative_to(PROJECT_ROOT).as_posix(),
                "raw_artifact_sha256": sha256_file(raw_path),
                "manifest_path": manifest_path.relative_to(PROJECT_ROOT).as_posix(),
                "manifest_sha256": sha256_file(manifest_path),
                "operator": "docker-m1-star50-review",
            }
            if not append_llm_factor_review(path=review_path, **row):
                raise D1ControlError("M1-2 review row unexpectedly exists")
            print(
                canonical_json(
                    {
                        "review_ordinal": ordinal,
                        "candidate_id": plan.candidate.candidate_id,
                        "role": plan.role,
                        "schema_status": schema_status,
                        "semantic_status": semantic_status,
                        "role_verdict": row["role_verdict"] or "INVALID",
                    }
                ),
                flush=True,
            )
            if failure_class:
                break

    final_rows = [
        row for row in _rows(review_path) if row["execution_release_id"] == release.release_id
    ]
    report = build_terminal_report(
        protocol=protocol,
        release=release,
        rows=final_rows,
        transport_path=transport_path,
        output_root=output_root,
        code_sha=code_sha,
        tls_sha=tls_sha,
    )
    _write_once(report_path, json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return {**report, "idempotent_reuse": False, "external_api_calls_this_run": external_calls}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL_PATH)
    parser.add_argument("--execution-release", type=Path, default=DEFAULT_RELEASE_PATH)
    parser.add_argument(
        "--output-root",
        type=Path,
        default=PROJECT_ROOT / "data/research/m1/m1-star50-price-volume-v1/m1_2_reviews",
    )
    args = parser.parse_args(argv)
    try:
        report = run_reviews(
            protocol_path=args.protocol,
            release_path=args.execution_release,
            output_root=args.output_root,
        )
    except (D1ControlError, OSError, RuntimeError, TypeError, ValueError):
        print(canonical_json({"status": "FAIL", "error_class": "M1ReviewExecutionError"}))
        return 2
    print(canonical_json(report))
    return 0 if report["review_gate"] == "GO_FREEZE_M1_3_VALIDATION_PROTOCOL_ONLY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
