"""Bounded DeepSeek generation and discovery-only evaluation for M1-1 STAR50."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from shaiwei.config import PROJECT_ROOT
from shaiwei.provenance import code_snapshot_sha256, git_head
from shaiwei.research.candidate_semantics import validate_candidate_semantics
from shaiwei.research.deepseek_client import create_live_deepseek_provider
from shaiwei.research.llm_factor import (
    D1ControlError,
    D1Protocol,
    execute_completed_attempt,
    plan_attempt,
    verify_attempt_experiment_bijection,
)
from shaiwei.research.llm_factor_live import (
    feedback_for_attempt,
    read_attempt_rows,
    select_discovery_candidates,
    tls_hostname_probe,
    verify_static_evidence,
)
from shaiwei.research.m1_star50_contract import (
    M1Star50ExecutionRelease,
    verify_star50_inputs,
)
from shaiwei.research.m1_star50_discovery import Star50DiscoveryEvaluator
from shaiwei.research.m1_star50_recovery import M1Star50TerminalRecovery


FATAL_FAILURES = {
    "cost_budget_exceeded",
    "model_identity_mismatch",
    "sensitive_output",
    "usage_missing_or_invalid",
    "discovery_evaluation_error",
}


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _write_once(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        if path.read_text(encoding="utf-8") != payload:
            raise D1ControlError("immutable M1-1 terminal report differs")
        return
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        temporary.write_text(payload, encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _batch_rows(
    rows: list[dict[str, str]], release: M1Star50ExecutionRelease
) -> list[dict[str, str]]:
    if any(row["execution_release_id"] != release.release_id for row in rows):
        raise D1ControlError("M1-1 dedicated attempt ledger contains another release")
    ordinals = [int(row["global_ordinal"]) for row in rows]
    if ordinals != list(range(1, len(rows) + 1)):
        raise D1ControlError("M1-1 attempt ledger is not a contiguous prefix")
    if any(row["execution_release_sha256"] != release.sha256 for row in rows):
        raise D1ControlError("M1-1 attempt rows differ from the active release")
    return rows


def _report(
    *,
    protocol: D1Protocol,
    release: M1Star50ExecutionRelease,
    rows: list[dict[str, str]],
    evaluator: Star50DiscoveryEvaluator,
    code_sha256: str,
    release_git_head: str,
    tls_certificate_sha256: str,
) -> dict[str, Any]:
    selected = select_discovery_candidates(rows, 2)
    actual_cost = sum(float(row["estimated_cost_usd"]) for row in rows)
    verdict = (
        "GO_DISCOVERY_TOP2_LOCKED"
        if len(selected) == 2
        else "PAUSE_INSUFFICIENT_DISCOVERY_CANDIDATES"
    )
    return {
        "schema_version": "m1-star50-factor-discovery-report-v1",
        "release_id": release.release_id,
        "execution_release_sha256": release.sha256,
        "protocol_sha256": protocol.sha256,
        "prompt_sha256": protocol.prompt_bundle.sha256,
        "knowledge_manifest_sha256": protocol.knowledge_manifest.sha256,
        "code_snapshot_sha256": code_sha256,
        "release_git_head": release_git_head,
        "data_snapshot_sha256": evaluator.data_snapshot_sha256,
        "qlib_artifact_sha256": evaluator.input_identity.qlib_artifact_sha256,
        "member_day_sha256": evaluator.input_identity.member_day_sha256,
        "tls_certificate_sha256": tls_certificate_sha256,
        "completed_response_count": len(rows),
        "completed_response_exact_gate": len(rows) == 40,
        "global_ordinals_complete": [int(row["global_ordinal"]) for row in rows]
        == list(range(1, 41)),
        "attempt_experiment_bijection": verify_attempt_experiment_bijection(
            PROJECT_ROOT / release.document["ledgers"]["attempt"],
            PROJECT_ROOT / release.document["ledgers"]["experiment"],
            protocol_id=protocol.protocol_id,
        ),
        "actual_cost_usd": actual_cost,
        "batch_hard_ceiling_usd": release.batch_hard_ceiling_usd,
        "d1_total_authorization_usd": release.total_authorization_usd,
        "cost_gate_pass": actual_cost <= release.batch_hard_ceiling_usd,
        "candidate_status_counts": {
            status: sum(row["candidate_status"] == status for row in rows)
            for status in sorted({row["candidate_status"] for row in rows})
        },
        "failure_class_counts": {
            status or "NONE": sum(row["failure_class"] == status for row in rows)
            for status in sorted({row["failure_class"] for row in rows})
        },
        "semantic_contract_violation_count": sum(
            row["failure_class"] == "semantic_contract_violation" for row in rows
        ),
        "selected_count": len(selected),
        "mechanical_top2": selected,
        "verdict": verdict,
        "discovery_results_evaluated": True,
        "sealed_validation_read": False,
        "stress_periods_read": False,
        "g1_run": False,
        "model_or_portfolio_run": False,
        "strategy_effective": "NOT_EVALUATED",
        "production_authorization": "none",
    }


def run_live(
    *,
    protocol_path: Path,
    release_path: Path,
    output_root: Path,
    recovery_path: Path | None = None,
) -> dict[str, Any]:
    protocol = D1Protocol.load(protocol_path)
    release = M1Star50ExecutionRelease.load(release_path, protocol)
    input_identity = verify_star50_inputs(protocol, PROJECT_ROOT)
    if release.document.get("input_contract", {}).get(
        "data_snapshot_sha256"
    ) != input_identity.snapshot_sha256:
        raise D1ControlError("M1-1 execution release input snapshot differs")

    ledger_path = PROJECT_ROOT / release.document["ledgers"]["attempt"]
    experiment_path = PROJECT_ROOT / release.document["ledgers"]["experiment"]
    transport_path = PROJECT_ROOT / release.document["ledgers"]["transport"]
    artifact_root = output_root / "artifacts"
    report_path = output_root / "m1_1_discovery_report.json"
    rows = _batch_rows(read_attempt_rows(ledger_path), release)
    if rows:
        verify_static_evidence(
            release=release,
            attempt_rows=rows,
            transport_ledger_path=transport_path,
            artifact_root=artifact_root,
            expected_count=len(rows),
        )
    if len(rows) == 40:
        static = verify_static_evidence(
            release=release,
            attempt_rows=rows,
            transport_ledger_path=transport_path,
            artifact_root=artifact_root,
        )
        if report_path.is_file():
            report = json.loads(report_path.read_text(encoding="utf-8"))
            if report.get("static_evidence") != static:
                raise D1ControlError("M1-1 report differs from static evidence")
            return {**report, "idempotent_reuse": True, "external_api_calls_this_run": 0}
        if recovery_path is None:
            raise D1ControlError("M1-1 completed batch is missing its terminal report")
        recovery = M1Star50TerminalRecovery.load(recovery_path)
        recovery.verify_frozen_evidence(
            project_root=PROJECT_ROOT,
            static_evidence=static,
            report_path=report_path,
        )
        evaluator = Star50DiscoveryEvaluator(protocol, artifact_root)
        report = _report(
            protocol=protocol,
            release=release,
            rows=rows,
            evaluator=evaluator,
            code_sha256=recovery.original_code_snapshot_sha256,
            release_git_head=recovery.original_release_git_head,
            tls_certificate_sha256=tls_hostname_probe(release),
        )
        report["static_evidence"] = static
        report["terminal_recovery"] = {
            "recovery_id": recovery.document["recovery_id"],
            "recovery_sha256": recovery.sha256,
            "assembled_from_existing_40_response_evidence": True,
            "additional_provider_calls": 0,
            "tls_probe_repeated_without_api_request": True,
        }
        _write_once(report_path, json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
        return {**report, "idempotent_reuse": False, "external_api_calls_this_run": 0}

    evaluator = Star50DiscoveryEvaluator(protocol, artifact_root)
    if evaluator.data_snapshot_sha256 != input_identity.snapshot_sha256:
        raise D1ControlError("M1-1 evaluator input identity differs from preflight")
    tls_certificate_sha256 = tls_hostname_probe(release)
    code_sha = code_snapshot_sha256()
    release_head = git_head()
    external_calls = 0
    for ordinal in range(len(rows) + 1, 41):
        plan = plan_attempt(protocol, ordinal)
        current_rows = _batch_rows(read_attempt_rows(ledger_path), release)
        feedback = feedback_for_attempt(current_rows, plan)
        with create_live_deepseek_provider(
            protocol,
            execution_release=release,
            attempt_id=plan.attempt_id,
            transport_ledger_path=transport_path,
            artifact_root=artifact_root / "provider",
            operator="docker-m1-star50-live",
        ) as provider:
            result = execute_completed_attempt(
                protocol,
                plan,
                provider,
                ledger_path=ledger_path,
                experiment_ledger_path=experiment_path,
                artifact_root=artifact_root,
                operator="docker-m1-star50-live",
                code_sha256=code_sha,
                feedback_records=feedback,
                execution_release_id=release.release_id,
                execution_release_sha256=release.sha256,
                cost_hard_ceiling_usd=release.batch_hard_ceiling_usd,
                data_sha256=evaluator.data_snapshot_sha256,
                discovery_evaluator=evaluator,
                returned_model_identity=release.response_model_identity,
                candidate_semantic_validator=validate_candidate_semantics,
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
            raise D1ControlError("M1-1 live batch stopped at a fatal completed-response gate")

    final_rows = _batch_rows(read_attempt_rows(ledger_path), release)
    report = _report(
        protocol=protocol,
        release=release,
        rows=final_rows,
        evaluator=evaluator,
        code_sha256=code_sha,
        release_git_head=release_head,
        tls_certificate_sha256=tls_certificate_sha256,
    )
    report["static_evidence"] = verify_static_evidence(
        release=release,
        attempt_rows=final_rows,
        transport_ledger_path=transport_path,
        artifact_root=artifact_root,
    )
    if not (
        report["completed_response_exact_gate"]
        and report["global_ordinals_complete"]
        and report["cost_gate_pass"]
    ):
        raise D1ControlError("M1-1 live batch failed its terminal machine gates")
    _write_once(report_path, json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return {**report, "idempotent_reuse": False, "external_api_calls_this_run": external_calls}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--protocol",
        type=Path,
        default=PROJECT_ROOT / "config/m1_star50_factor_research_v1.yaml",
    )
    parser.add_argument(
        "--execution-release",
        type=Path,
        default=PROJECT_ROOT / "config/m1_star50_factor_execution_v1.yaml",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=PROJECT_ROOT / "data/research/m1/m1-star50-price-volume-v1",
    )
    parser.add_argument("--terminal-recovery", type=Path, default=None)
    args = parser.parse_args(argv)
    try:
        report = run_live(
            protocol_path=args.protocol,
            release_path=args.execution_release,
            output_root=args.output_root,
            recovery_path=args.terminal_recovery,
        )
    except (D1ControlError, OSError, RuntimeError, TypeError, ValueError) as error:
        print(_canonical_json({"status": "FAIL", "error_class": type(error).__name__}))
        return 2
    print(_canonical_json(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
