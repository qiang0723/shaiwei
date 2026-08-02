"""Bounded DeepSeek generation and discovery-only scoring for M3-2."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from shaiwei.config import PROJECT_ROOT
from shaiwei.provenance import code_snapshot_sha256, git_head
from shaiwei.research.deepseek_client import create_live_deepseek_provider
from shaiwei.research.llm_factor import (
    D1ControlError,
    execute_completed_attempt,
    verify_attempt_experiment_bijection,
)
from shaiwei.research.llm_factor_live import (
    read_attempt_rows,
    tls_hostname_probe,
    verify_static_evidence,
)
from shaiwei.research.m3_multi_pool_contract import M3Protocol
from shaiwei.research.m3_multi_pool_data import build_m3_discovery_input
from shaiwei.research.m3_multi_pool_discovery import (
    M3DiscoveryEvaluator,
    feedback_for_m3_attempt,
    feedback_row,
    plan_m3_attempt,
    prior_expression_index,
    select_m3_candidates,
)
from shaiwei.research.m3_multi_pool_evaluation import validate_m3_candidate_semantics
from shaiwei.research.m3_multi_pool_release import M3ExecutionRelease


TOTAL_RESPONSES = 24
FATAL_FAILURES = {
    "cost_budget_exceeded",
    "model_identity_mismatch",
    "sensitive_output",
    "usage_missing_or_invalid",
    "discovery_evaluation_error",
}


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _write_once(path: Path, document: dict[str, Any]) -> None:
    payload = json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        if path.read_text(encoding="utf-8") != payload:
            raise D1ControlError(f"immutable M3-2 artifact differs: {path.name}")
        return
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        temporary.write_text(payload, encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _batch_rows(
    rows: list[dict[str, str]], release: M3ExecutionRelease
) -> list[dict[str, str]]:
    if len(rows) > TOTAL_RESPONSES:
        raise D1ControlError("M3-2 dedicated attempt ledger exceeds its frozen budget")
    if any(row["execution_release_id"] != release.release_id for row in rows):
        raise D1ControlError("M3-2 dedicated attempt ledger contains another release")
    if any(row["execution_release_sha256"] != release.sha256 for row in rows):
        raise D1ControlError("M3-2 attempt rows differ from the frozen release")
    ordinals = [int(row["global_ordinal"]) for row in rows]
    if ordinals != list(range(1, len(rows) + 1)):
        raise D1ControlError("M3-2 attempt ledger is not a contiguous prefix")
    return rows


def _batch_context(
    *,
    release: M3ExecutionRelease,
    data_snapshot_sha256: str,
    code_sha256: str,
    release_git_head: str,
    tls_certificate_sha256: str,
) -> dict[str, Any]:
    return {
        "schema_version": "m3-multi-pool-live-context-v1",
        "release_id": release.release_id,
        "execution_release_sha256": release.sha256,
        "data_snapshot_sha256": data_snapshot_sha256,
        "code_snapshot_sha256": code_sha256,
        "release_git_head": release_git_head,
        "tls_certificate_sha256": tls_certificate_sha256,
        "same_release_resume_allowed": True,
        "changed_code_or_release_requires_result_before_addendum": True,
    }


def _load_context(
    path: Path,
    *,
    release: M3ExecutionRelease,
    data_snapshot_sha256: str,
    code_sha256: str,
    release_git_head: str,
) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise D1ControlError("M3-2 immutable live context is missing or invalid") from error
    if (
        not isinstance(document, dict)
        or document.get("schema_version") != "m3-multi-pool-live-context-v1"
        or document.get("release_id") != release.release_id
        or document.get("execution_release_sha256") != release.sha256
        or document.get("data_snapshot_sha256") != data_snapshot_sha256
        or document.get("code_snapshot_sha256") != code_sha256
        or document.get("release_git_head") != release_git_head
        or not isinstance(document.get("tls_certificate_sha256"), str)
        or len(document["tls_certificate_sha256"]) != 64
    ):
        raise D1ControlError("M3-2 immutable live context schema differs")
    return document


def _report(
    *,
    protocol: M3Protocol,
    release: M3ExecutionRelease,
    rows: list[dict[str, str]],
    artifact_root: Path,
    context: dict[str, Any],
) -> dict[str, Any]:
    selected = select_m3_candidates(rows, artifact_root, count=2)
    actual_cost = sum(float(row["estimated_cost_usd"]) for row in rows)
    eligible_count = sum(
        1
        for row in rows
        if row["candidate_status"] == "DISCOVERY_EVALUATED"
        and row["discovery_artifact_path"]
        and json.loads(
            (artifact_root / row["discovery_artifact_path"]).read_text(encoding="utf-8")
        ).get("eligible")
        is True
    )
    return {
        "schema_version": "m3-multi-pool-factor-discovery-report-v1",
        "release_id": release.release_id,
        "execution_release_sha256": release.sha256,
        "protocol_sha256": protocol.sha256,
        "prompt_sha256": protocol.prompt_bundle.sha256,
        "knowledge_manifest_sha256": protocol.knowledge_manifest.sha256,
        "code_snapshot_sha256": context["code_snapshot_sha256"],
        "release_git_head": context["release_git_head"],
        "data_snapshot_sha256": context["data_snapshot_sha256"],
        "tls_certificate_sha256": context["tls_certificate_sha256"],
        "completed_response_count": len(rows),
        "completed_response_exact_gate": len(rows) == TOTAL_RESPONSES,
        "global_ordinals_complete": [int(row["global_ordinal"]) for row in rows]
        == list(range(1, TOTAL_RESPONSES + 1)),
        "attempt_experiment_bijection": verify_attempt_experiment_bijection(
            PROJECT_ROOT / release.document["ledgers"]["attempt"],
            PROJECT_ROOT / release.document["ledgers"]["experiment"],
            protocol_id=protocol.protocol_id,
        ),
        "actual_cost_usd": actual_cost,
        "batch_hard_ceiling_usd": release.batch_hard_ceiling_usd,
        "d1_total_authorization_usd": release.total_authorization_usd,
        "cost_gate_pass": actual_cost <= release.batch_hard_ceiling_usd,
        "prior_related_trial_count": 246,
        "new_batch_trial_count": TOTAL_RESPONSES,
        "effective_trial_count": 270,
        "cross_pool_evaluation_cells": TOTAL_RESPONSES * 3,
        "candidate_status_counts": {
            status: sum(row["candidate_status"] == status for row in rows)
            for status in sorted({row["candidate_status"] for row in rows})
        },
        "failure_class_counts": {
            failure or "NONE": sum(row["failure_class"] == failure for row in rows)
            for failure in sorted({row["failure_class"] for row in rows})
        },
        "eligible_cross_pool_candidate_count": eligible_count,
        "selected_count": len(selected),
        "mechanical_top2": selected,
        "verdict": (
            "GO_M3_2_DISCOVERY_TOP2_LOCKED"
            if len(selected) == 2
            else "PAUSE_INSUFFICIENT_CROSS_POOL_CANDIDATES"
        ),
        "discovery_results_evaluated": True,
        "sealed_validation_read": False,
        "stress_periods_read": False,
        "g1_run": False,
        "model_or_portfolio_run": False,
        "strategy_effective": "NOT_EVALUATED",
        "production_authorization": "none",
    }


def run_live(*, protocol_path: Path, release_path: Path, output_root: Path) -> dict[str, Any]:
    protocol = M3Protocol.load(protocol_path)
    release = M3ExecutionRelease.load(release_path, protocol)
    prepared = build_m3_discovery_input(protocol)
    release.verify_input(prepared.identity)
    ledger_path = PROJECT_ROOT / release.document["ledgers"]["attempt"]
    experiment_path = PROJECT_ROOT / release.document["ledgers"]["experiment"]
    transport_path = PROJECT_ROOT / release.document["ledgers"]["transport"]
    artifact_root = output_root / "artifacts"
    context_path = output_root / "m3_2_live_context.json"
    report_path = output_root / "m3_2_discovery_report.json"
    rows = _batch_rows(read_attempt_rows(ledger_path), release)
    current_code_sha = code_snapshot_sha256()
    current_git_head = git_head()
    if rows:
        verify_static_evidence(
            release=release,
            attempt_rows=rows,
            transport_ledger_path=transport_path,
            artifact_root=artifact_root,
            expected_count=len(rows),
        )
    if len(rows) == TOTAL_RESPONSES:
        static = verify_static_evidence(
            release=release,
            attempt_rows=rows,
            transport_ledger_path=transport_path,
            artifact_root=artifact_root,
            expected_count=TOTAL_RESPONSES,
        )
        context = _load_context(
            context_path,
            release=release,
            data_snapshot_sha256=prepared.identity.snapshot_sha256,
            code_sha256=current_code_sha,
            release_git_head=current_git_head,
        )
        if report_path.is_file():
            report = json.loads(report_path.read_text(encoding="utf-8"))
            if (
                report.get("static_evidence") != static
                or report.get("execution_release_sha256") != release.sha256
                or report.get("data_snapshot_sha256") != prepared.identity.snapshot_sha256
                or report.get("code_snapshot_sha256") != current_code_sha
                or report.get("release_git_head") != current_git_head
            ):
                raise D1ControlError("M3-2 report differs from static evidence")
            return {**report, "idempotent_reuse": True, "external_api_calls_this_run": 0}
        report = _report(
            protocol=protocol,
            release=release,
            rows=rows,
            artifact_root=artifact_root,
            context=context,
        )
        report["static_evidence"] = static
        report["terminal_assembly_from_existing_responses"] = True
        _write_once(report_path, report)
        return {**report, "idempotent_reuse": False, "external_api_calls_this_run": 0}

    evaluator = M3DiscoveryEvaluator(
        protocol=protocol,
        release=release,
        artifact_root=artifact_root,
        prepared=prepared,
    )
    if context_path.is_file():
        current_context = _load_context(
            context_path,
            release=release,
            data_snapshot_sha256=prepared.identity.snapshot_sha256,
            code_sha256=current_code_sha,
            release_git_head=current_git_head,
        )
    else:
        current_context = _batch_context(
            release=release,
            data_snapshot_sha256=prepared.identity.snapshot_sha256,
            code_sha256=current_code_sha,
            release_git_head=current_git_head,
            tls_certificate_sha256=tls_hostname_probe(release),
        )
        _write_once(context_path, current_context)
    prior_index = prior_expression_index()
    external_calls = 0
    for ordinal in range(len(rows) + 1, TOTAL_RESPONSES + 1):
        plan = plan_m3_attempt(protocol, ordinal)
        current_rows = _batch_rows(read_attempt_rows(ledger_path), release)
        feedback = feedback_for_m3_attempt(current_rows, plan, artifact_root)
        with create_live_deepseek_provider(
            protocol,
            execution_release=release,
            attempt_id=plan.attempt_id,
            transport_ledger_path=transport_path,
            artifact_root=artifact_root / "provider",
            operator="docker-m3-multi-pool-live",
        ) as provider:
            result = execute_completed_attempt(
                protocol,
                plan,
                provider,
                ledger_path=ledger_path,
                experiment_ledger_path=experiment_path,
                artifact_root=artifact_root,
                operator="docker-m3-multi-pool-live",
                code_sha256=current_context["code_snapshot_sha256"],
                feedback_records=feedback,
                execution_release_id=release.release_id,
                execution_release_sha256=release.sha256,
                cost_hard_ceiling_usd=release.batch_hard_ceiling_usd,
                data_sha256=prepared.identity.snapshot_sha256,
                discovery_evaluator=evaluator,
                returned_model_identity=release.response_model_identity,
                candidate_semantic_validator=validate_m3_candidate_semantics,
                feedback_row_projector=lambda row: feedback_row(row, artifact_root),
                duplicate_expression_lookup=prior_index.get,
            )
            external_calls += provider.external_api_calls
        print(
            _canonical_json(
                {
                    "global_ordinal": ordinal,
                    "completed": True,
                    "candidate_status": result.row["candidate_status"],
                    "failure_class": result.row["failure_class"] or "NONE",
                    "cumulative_cost_usd": round(
                        sum(
                            float(row["estimated_cost_usd"])
                            for row in read_attempt_rows(ledger_path)
                        ),
                        8,
                    ),
                }
            ),
            flush=True,
        )
        if result.row["failure_class"] in FATAL_FAILURES:
            raise D1ControlError("M3-2 batch stopped at a fatal completed-response gate")

    final_rows = _batch_rows(read_attempt_rows(ledger_path), release)
    report = _report(
        protocol=protocol,
        release=release,
        rows=final_rows,
        artifact_root=artifact_root,
        context=current_context,
    )
    report["static_evidence"] = verify_static_evidence(
        release=release,
        attempt_rows=final_rows,
        transport_ledger_path=transport_path,
        artifact_root=artifact_root,
        expected_count=TOTAL_RESPONSES,
    )
    if not (
        report["completed_response_exact_gate"]
        and report["global_ordinals_complete"]
        and report["cost_gate_pass"]
    ):
        raise D1ControlError("M3-2 live batch failed its terminal machine gates")
    _write_once(report_path, report)
    return {**report, "idempotent_reuse": False, "external_api_calls_this_run": external_calls}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--protocol",
        type=Path,
        default=PROJECT_ROOT / "config/m3_multi_pool_factor_research_v1.yaml",
    )
    parser.add_argument(
        "--execution-release",
        type=Path,
        default=PROJECT_ROOT / "config/m3_multi_pool_factor_execution_v1.yaml",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=PROJECT_ROOT / "data/research/m3/m3-star-three-pool-price-volume-v1",
    )
    args = parser.parse_args(argv)
    try:
        report = run_live(
            protocol_path=args.protocol,
            release_path=args.execution_release,
            output_root=args.output_root,
        )
    except (D1ControlError, OSError, RuntimeError, TypeError, ValueError) as error:
        print(_canonical_json({"status": "FAIL", "error_class": type(error).__name__}))
        return 2
    print(_canonical_json(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
