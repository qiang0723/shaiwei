"""Bounded DeepSeek execution for the frozen M3-3 Top2 review batch."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from shaiwei.config import PROJECT_ROOT
from shaiwei.provenance import code_snapshot_sha256, git_head
from shaiwei.research.deepseek_client import (
    TRANSPORT_LEDGER_HEADER_V2,
    create_live_deepseek_provider,
)
from shaiwei.research.llm_factor import (
    D1ControlError,
    ProviderResponse,
    _has_sensitive_output,
    _response_envelope,
    _validate_usage,
)
from shaiwei.research.llm_factor_live import tls_hostname_probe
from shaiwei.research.llm_review_semantics import PASS as SEMANTIC_PASS
from shaiwei.research.m3_multi_pool_review_contract import (
    DEFAULT_PROTOCOL_PATH,
    M3ReviewProtocol,
    ReviewPlan,
    canonical_json,
)
from shaiwei.research.m3_multi_pool_review_live_evidence import (
    build_terminal_report,
    load_terminal_report,
    persist_completed_review,
    review_rows,
    write_once,
)
from shaiwei.research.m3_multi_pool_review_live_release import (
    DEFAULT_LIVE_RELEASE_PATH,
    M3ReviewLiveRelease,
)
from shaiwei.research.m3_multi_pool_review_request import (
    build_review_request,
    plan_review,
    preflight,
    validate_review_document,
)


OUTPUT_ROOT = (
    PROJECT_ROOT / "data/research/m3/m3-star-three-pool-price-volume-v1/m3_3_reviews"
)


@dataclass(frozen=True)
class ProviderProtocolAdapter:
    review: M3ReviewProtocol

    @property
    def document(self) -> dict[str, Any]:
        return self.review.document

    @property
    def sha256(self) -> str:
        return self.review.sha256

    @property
    def provider_name(self) -> str:
        return str(self.review.document["provider"]["provider"])

    @property
    def requested_model(self) -> str:
        return self.review.requested_model

    @property
    def maximum_output_tokens(self) -> int:
        return self.review.maximum_output_tokens


def _transport_rows(path: Path, release: M3ReviewLiveRelease) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    if tuple(reader.fieldnames or ()) != TRANSPORT_LEDGER_HEADER_V2:
        raise D1ControlError("M3-3 transport ledger schema differs")
    if any(
        row["execution_release_id"] != release.release_id
        or row["execution_release_sha256"] != release.sha256
        for row in rows
    ):
        raise D1ControlError("M3-3 transport ledger release differs")
    return rows


def run_live_preflight(
    *, protocol_path: Path, release_path: Path
) -> dict[str, Any]:
    protocol = M3ReviewProtocol.load(protocol_path)
    release = M3ReviewLiveRelease.load(release_path, protocol)
    if git_head() != release.implementation_git_head:
        raise D1ControlError("M3-3 live image Git identity differs")
    review_path = PROJECT_ROOT / release.document["ledgers"]["review"]
    transport_path = PROJECT_ROOT / release.document["ledgers"]["transport"]
    reviews = review_rows(review_path, release)
    transports = _transport_rows(transport_path, release)
    if reviews or transports:
        raise D1ControlError("M3-3 live preflight requires pristine dedicated ledgers")
    contract = preflight(protocol_path)
    return {
        **contract,
        "schema_version": "m3-multi-pool-review-live-preflight-v1",
        "execution_release_id": release.release_id,
        "execution_release_sha256": release.sha256,
        "implementation_git_head": release.implementation_git_head,
        "runtime_git_head": git_head(),
        "runtime_code_snapshot_sha256": code_snapshot_sha256(),
        "execution_authorized": True,
        "authorized_completed_responses_exact": 8,
        "review_hard_ceiling_usd": release.batch_hard_ceiling_usd,
        "review_ledger_rows": 0,
        "transport_ledger_rows": 0,
        "api_key_read": False,
        "provider_calls": 0,
        "sealed_validation_read": False,
        "strategy_effective": "NOT_EVALUATED",
        "production_authorization": "none",
        "live_preflight_gate": "PASS",
    }


def _worst_case_attempt_cost(protocol: M3ReviewProtocol) -> float:
    provider = protocol.document["provider"]
    prices = protocol.document["cost_budget"]
    return (
        int(provider["maximum_prompt_tokens_per_attempt"])
        * float(prices["pro_input_cache_miss_per_million"])
        + int(provider["maximum_output_tokens"])
        * float(prices["pro_output_per_million"])
    ) / 1_000_000


def classify_response(
    protocol: M3ReviewProtocol,
    release: M3ReviewLiveRelease,
    plan: ReviewPlan,
    response: ProviderResponse,
) -> dict[str, Any]:
    adapter = ProviderProtocolAdapter(protocol)
    usage = {
        "prompt_tokens": 0,
        "prompt_cache_hit_tokens": 0,
        "prompt_cache_miss_tokens": 0,
        "completion_tokens": 0,
    }
    cost = 0.0
    review = semantic = None
    parse_status = schema_status = "NOT_EVALUATED"
    failure_class = ""
    try:
        usage, cost = _validate_usage(adapter, response.usage)  # type: ignore[arg-type]
        if response.model != release.response_model_identity:
            raise D1ControlError("provider_model_identity_mismatch")
        if response.finish_reason != "stop":
            raise D1ControlError("provider_finish_reason_invalid")
        if _has_sensitive_output(response):
            raise D1ControlError("provider_sensitive_output")
    except D1ControlError as error:
        failure_class = str(error)
    if not failure_class:
        try:
            document = json.loads(response.content)
            parse_status = "PASS"
            review, semantic = validate_review_document(protocol, plan, document)
            schema_status = "PASS"
            if semantic.status != SEMANTIC_PASS:
                failure_class = "semantic_contract_violation"
        except json.JSONDecodeError:
            parse_status, schema_status, failure_class = (
                "FAIL",
                "NOT_EVALUATED",
                "json_invalid",
            )
        except (TypeError, ValueError):
            parse_status, schema_status, failure_class = "PASS", "FAIL", "schema_invalid"
    return {
        "usage": usage,
        "cost": cost,
        "review": review,
        "semantic": semantic,
        "parse_status": parse_status,
        "schema_status": schema_status,
        "semantic_status": semantic.status if semantic else "NOT_EVALUATED",
        "semantic_reason_codes": list(semantic.reason_codes) if semantic else [],
        "inspected_text_sha256": semantic.inspected_text_sha256 if semantic else "",
        "failure_class": failure_class,
    }


def run_reviews(
    *, protocol_path: Path, release_path: Path, output_root: Path
) -> dict[str, Any]:
    output_root = output_root.resolve()
    if not output_root.is_relative_to(PROJECT_ROOT.resolve()):
        raise D1ControlError("M3-3 output root escapes the project")
    protocol = M3ReviewProtocol.load(protocol_path)
    release = M3ReviewLiveRelease.load(release_path, protocol)
    if git_head() != release.implementation_git_head:
        raise D1ControlError("M3-3 runtime Git identity differs from the frozen image")
    review_path = PROJECT_ROOT / release.document["ledgers"]["review"]
    transport_path = PROJECT_ROOT / release.document["ledgers"]["transport"]
    rows = review_rows(review_path, release)
    report_path = output_root / "m3_3_review_report.json"
    if report_path.is_file():
        report = load_terminal_report(
            report_path,
            rows=rows,
            transport_path=transport_path,
            output_root=output_root,
            release=release,
        )
        return {**report, "idempotent_reuse": True, "external_api_calls_this_run": 0}
    tls_sha = tls_hostname_probe(release)  # type: ignore[arg-type]
    code_sha = code_snapshot_sha256()
    if any(row["code_snapshot_sha256"] != code_sha for row in rows):
        raise D1ControlError("M3-3 partial rows use another code snapshot")
    external_calls = 0
    if not any(row["failure_class"] for row in rows):
        for ordinal in range(len(rows) + 1, 9):
            current = review_rows(review_path, release)
            spent = sum(float(row["estimated_cost_usd"]) for row in current)
            if spent + _worst_case_attempt_cost(protocol) > release.batch_hard_ceiling_usd:
                raise D1ControlError("M3-3 cost reserve reaches the hard ceiling")
            plan = plan_review(protocol, ordinal)
            request = build_review_request(protocol, plan)
            request_payload = canonical_json(request)
            request_sha = hashlib.sha256(request_payload.encode("utf-8")).hexdigest()
            request_path = output_root / "artifacts/requests" / (
                f"{plan.review_id}-{request_sha[:12]}.json"
            )
            write_once(request_path, request_payload)
            adapter = ProviderProtocolAdapter(protocol)
            with create_live_deepseek_provider(
                adapter,  # type: ignore[arg-type]
                execution_release=release,  # type: ignore[arg-type]
                attempt_id=plan.review_id,
                transport_ledger_path=transport_path,
                artifact_root=output_root / "artifacts/provider",
                operator="docker-m3-multi-pool-review",
            ) as provider:
                response = provider.complete(request)
                external_calls += provider.external_api_calls
            raw_payload = canonical_json(_response_envelope(response)) + "\n"
            raw_path = output_root / "artifacts/raw" / (
                f"{plan.review_id}-{response.source_response_sha256[:12]}.json"
            )
            write_once(raw_path, raw_payload)
            classified = classify_response(protocol, release, plan, response)
            persist_completed_review(
                protocol=protocol,
                release=release,
                plan=plan,
                response=response,
                classified=classified,
                request_sha=request_sha,
                raw_path=raw_path,
                code_sha=code_sha,
                review_path=review_path,
                output_root=output_root,
            )
            print(
                canonical_json(
                    {
                        "review_ordinal": ordinal,
                        "candidate_id": plan.candidate.candidate_id,
                        "role": plan.role,
                        "schema_status": classified["schema_status"],
                        "semantic_status": classified["semantic_status"],
                        "role_verdict": (
                            classified["review"].role_verdict
                            if classified["review"]
                            else "INVALID"
                        ),
                    }
                ),
                flush=True,
            )
            if classified["failure_class"]:
                break
    final_rows = review_rows(review_path, release)
    report = build_terminal_report(
        protocol=protocol,
        release=release,
        rows=final_rows,
        transport_path=transport_path,
        output_root=output_root,
        code_sha=code_sha,
        tls_sha=tls_sha,
    )
    write_once(report_path, json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return {**report, "idempotent_reuse": False, "external_api_calls_this_run": external_calls}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL_PATH)
    parser.add_argument("--execution-release", type=Path, default=DEFAULT_LIVE_RELEASE_PATH)
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = (
            run_live_preflight(protocol_path=args.protocol, release_path=args.execution_release)
            if args.preflight_only
            else run_reviews(
                protocol_path=args.protocol,
                release_path=args.execution_release,
                output_root=args.output_root,
            )
        )
    except (D1ControlError, OSError, RuntimeError, TypeError, ValueError):
        print(canonical_json({"status": "FAIL", "error_class": "M3ReviewExecutionError"}))
        return 2
    print(canonical_json(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
