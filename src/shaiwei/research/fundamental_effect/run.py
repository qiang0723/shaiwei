"""Run the frozen F1-1 residual build and six-candidate historical effect gate."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq

from shaiwei.config import PROJECT_ROOT, load
from shaiwei.ledger import portable_artifact_path, sha256_file
from shaiwei.provenance import code_snapshot_sha256, git_head
from shaiwei.research.fundamental_effect.contract import (
    RESEARCH_FAMILY,
    FundamentalEffectError,
    FundamentalEffectProtocol,
)
from shaiwei.research.fundamental_effect.evidence import (
    build_candidate_artifacts,
    candidate_experiment_id,
    direction_reject_result,
    ensure_experiment,
    experiment_result,
    family_trial_count,
    record_execution_failure,
    stable_decision_summary,
)
from shaiwei.research.fundamental_effect.io import (
    write_content_addressed_parquet,
    write_json_once,
)
from shaiwei.research.fundamental_effect.metrics import (
    CandidateResult,
    build_baselines,
    evaluate_candidate,
    evaluate_discovery,
    load_labels,
)
from shaiwei.research.g1 import AdmissionDecision, evaluate_g1


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise FundamentalEffectError(f"invalid F1-1 JSON evidence: {path}") from error
    if not isinstance(value, dict):
        raise FundamentalEffectError(f"F1-1 JSON evidence must be an object: {path}")
    return value


def _artifact(
    value: dict[str, Any],
    *,
    project_root: Path,
) -> Path:
    path = (project_root / str(value.get("path", ""))).resolve()
    if not path.is_relative_to(project_root.resolve()):
        raise FundamentalEffectError("F1-1 artifact path escapes the project")
    expected = str(value.get("sha256", ""))
    if not path.is_file() or sha256_file(path) != expected:
        raise FundamentalEffectError(f"F1-1 artifact is missing or hash-mismatched: {path.name}")
    expected_rows = value.get("row_count")
    if expected_rows is not None and pq.read_metadata(path).num_rows != int(expected_rows):
        raise FundamentalEffectError(f"F1-1 artifact row count differs: {path.name}")
    return path


def validate_residual_report(
    protocol: FundamentalEffectProtocol,
    input_identity: dict[str, object],
    *,
    project_root: Path = PROJECT_ROOT,
) -> tuple[dict[str, Any], Path]:
    report_path = protocol.output_root / "residual_build_report.json"
    report = _read_json(report_path)
    if report.get("schema_version") != "f1-csi800-fundamental-residual-build-v1":
        raise FundamentalEffectError("F1-1 residual report schema differs")
    expected = {
        "protocol_sha256": protocol.sha256,
        "policy_sha256": protocol.policy_sha256,
        "code_snapshot_sha256": code_snapshot_sha256(),
        "status": "PASS",
        "labels_read": False,
        "rank_ic_computed": False,
        "returns_computed": False,
    }
    if any(report.get(key) != value for key, value in expected.items()):
        raise FundamentalEffectError("F1-1 residual report binding or authority differs")
    report_input = report.get("input_identity")
    if not isinstance(report_input, dict) or report_input.get("input_snapshot_sha256") != input_identity.get(
        "input_snapshot_sha256"
    ):
        raise FundamentalEffectError("F1-1 residual report input snapshot differs")
    artifacts = report.get("artifacts")
    if not isinstance(artifacts, dict) or set(artifacts) != {"core", "formal"}:
        raise FundamentalEffectError("F1-1 residual report lacks core/formal artifacts")
    for value in artifacts.values():
        if not isinstance(value, dict):
            raise FundamentalEffectError("F1-1 residual artifact binding is invalid")
        _artifact(value, project_root=project_root)
    gates = report.get("gates")
    if not isinstance(gates, dict) or not gates or not all(gates.values()):
        raise FundamentalEffectError("F1-1 residual report gates are not all PASS")
    return report, report_path


def _result_artifacts(
    results: list[CandidateResult],
    output_root: Path,
) -> dict[str, object]:
    if not results:
        return {}
    returns = pd.concat([result.return_rows for result in results], ignore_index=True).sort_values(
        ["candidate", "window", "scenario", "trade_date"], kind="stable"
    )
    daily_ic = pd.concat([result.ic_rows for result in results], ignore_index=True).sort_values(
        ["candidate", "series_type", "window", "trade_date"], kind="stable"
    )
    returns_path, returns_sha, returns_reused = write_content_addressed_parquet(
        returns.reset_index(drop=True), output_root, stem="f1-fundamental-daily-returns-v1"
    )
    ic_path, ic_sha, ic_reused = write_content_addressed_parquet(
        daily_ic.reset_index(drop=True), output_root, stem="f1-fundamental-daily-ic-v1"
    )
    return {
        "daily_returns": {
            "path": portable_artifact_path(returns_path),
            "sha256": returns_sha,
            "row_count": int(len(returns)),
            "reused": returns_reused,
        },
        "daily_ic": {
            "path": portable_artifact_path(ic_path),
            "sha256": ic_sha,
            "row_count": int(len(daily_ic)),
            "reused": ic_reused,
        },
    }


def _stable_artifact_bindings(runtime: dict[str, object]) -> dict[str, object]:
    return {
        name: {key: value[key] for key in ("path", "sha256", "row_count")}
        for name, value in runtime.items()
        if isinstance(value, dict)
    }


def run_effect(
    protocol: FundamentalEffectProtocol,
    input_identity: dict[str, object],
    *,
    project_root: Path = PROJECT_ROOT,
) -> dict[str, object]:
    residual, residual_path = validate_residual_report(
        protocol, input_identity, project_root=project_root
    )
    artifacts = residual["artifacts"]
    core = pd.read_parquet(_artifact(artifacts["core"], project_root=project_root))
    formal = pd.read_parquet(_artifact(artifacts["formal"], project_root=project_root))
    prediction_binding = protocol.document["input_bindings"]["alpha158_predictions"]
    prediction_path = protocol.project_path(
        str(prediction_binding["path"]), project_root=project_root
    )
    predictions = pd.read_parquet(prediction_path)
    settings = load()
    code_hash = code_snapshot_sha256()
    data_hash = str(residual["residual_data_snapshot_sha256"])
    effects_started = False
    completed = False
    try:
        effects_started = True
        labels = load_labels(settings)
        baselines = build_baselines(settings, labels, predictions)
        discovery_policy = protocol.document["evaluation"]["discovery"]
        discoveries = [
            evaluate_discovery(
                spec,
                core,
                labels,
                start=str(discovery_policy["start"]),
                end=str(discovery_policy["end"]),
                minimum=int(discovery_policy["minimum_daily_rank_ic_observations"]),
            )
            for spec in protocol.candidates
        ]
        experiment_ids = {
            discovery.spec.name: candidate_experiment_id(
                discovery.spec.name,
                code_hash,
                data_hash,
                protocol.policy_sha256,
            )
            for discovery in discoveries
        }
        results = [
            evaluate_candidate(
                settings,
                discovery,
                experiment_ids[discovery.spec.name],
                formal,
                labels,
                baselines,
                factor_library_root=project_root / "data" / "research" / "factor_library",
            )
            for discovery in discoveries
            if discovery.direction_pass
        ]
        runtime_artifacts = _result_artifacts(results, protocol.output_root)
        stable_artifacts = _stable_artifact_bindings(runtime_artifacts)
        result_by_name = {result.discovery.spec.name: result for result in results}
        built: dict[str, tuple[Path, Path, bool]] = {}
        if results:
            returns = stable_artifacts["daily_returns"]
            daily_ic = stable_artifacts["daily_ic"]
            for result in results:
                built[result.discovery.spec.name] = build_candidate_artifacts(
                    result,
                    code_hash=code_hash,
                    data_hash=data_hash,
                    policy_hash=protocol.policy_sha256,
                    panel_report_path=residual_path,
                    panel_report_sha256=sha256_file(residual_path),
                    daily_returns_path=project_root / str(returns["path"]),
                    daily_returns_sha256=str(returns["sha256"]),
                    daily_ic_path=project_root / str(daily_ic["path"]),
                    daily_ic_sha256=str(daily_ic["sha256"]),
                    output_root=protocol.output_root,
                )
        experiment_reuse: dict[str, bool] = {}
        for discovery in discoveries:
            if discovery.direction_pass:
                result = result_by_name[discovery.spec.name]
                test_path, evidence_path, _ = built[discovery.spec.name]
                ledger_result = experiment_result(
                    result, test_path=test_path, evidence_path=evidence_path
                )
                reject_reason = "G1 evidence candidate; pending frozen judge"
            else:
                ledger_result = direction_reject_result(discovery)
                reject_reason = "pre-registered economic direction disagrees with discovery RankIC"
            experiment_reuse[discovery.spec.name] = ensure_experiment(
                experiment_id=experiment_ids[discovery.spec.name],
                spec=discovery.spec,
                code_hash=code_hash,
                data_hash=data_hash,
                policy_hash=protocol.policy_sha256,
                result=ledger_result,
                reject_reason=reject_reason,
            )
        decisions: dict[str, AdmissionDecision] = {}
        for result in results:
            evidence_path = built[result.discovery.spec.name][1]
            decisions[result.discovery.spec.name] = evaluate_g1(
                evidence_path,
                settings=settings,
                output_dir=protocol.output_root / "g1_decisions",
            )
        candidates: list[dict[str, object]] = []
        for discovery in discoveries:
            if not discovery.direction_pass:
                candidates.append(
                    {
                        "candidate": discovery.spec.name,
                        "experiment_id": experiment_ids[discovery.spec.name],
                        "pre_registered_direction": discovery.spec.direction,
                        "discovery_mean_rank_ic": discovery.mean_rank_ic,
                        "discovery_observations": discovery.observation_count,
                        "direction_gate": "REJECT",
                        "oos_effect_read": False,
                        "g1_decision": "NOT_RUN_DIRECTION_REJECT",
                    }
                )
                continue
            result = result_by_name[discovery.spec.name]
            decision = decisions[discovery.spec.name]
            test_path, evidence_path, _ = built[discovery.spec.name]
            candidates.append(
                {
                    **stable_decision_summary(result),
                    "direction_gate": "PASS",
                    "test_report_path": portable_artifact_path(test_path),
                    "test_report_sha256": sha256_file(test_path),
                    "evidence_path": portable_artifact_path(evidence_path),
                    "evidence_sha256": sha256_file(evidence_path),
                    "g1_decision": "PASS" if decision.admitted else "REJECT",
                    "failed_gates": list(decision.failed_gates),
                    "decision_report_path": portable_artifact_path(decision.report_path),
                    "decision_report_sha256": decision.report_sha256,
                }
            )
        admitted = [decision for decision in decisions.values() if decision.admitted]
        verdict = "GO_REVIEW_ONLY" if admitted else "REJECT"
        stable_summary: dict[str, object] = {
            "schema_version": "f1-csi800-fundamental-effect-summary-v1",
            "protocol_id": protocol.document["protocol_id"],
            "protocol_sha256": protocol.sha256,
            "policy_sha256": protocol.policy_sha256,
            "research_family": RESEARCH_FAMILY,
            "code_snapshot_sha256": code_hash,
            "code_git_head": git_head(),
            "residual_data_snapshot_sha256": data_hash,
            "residual_report_path": portable_artifact_path(residual_path),
            "residual_report_sha256": sha256_file(residual_path),
            "candidate_budget": 6,
            "experiment_trial_count": family_trial_count(),
            "direction_pass_count": int(sum(item.direction_pass for item in discoveries)),
            "g1_pass_count": len(admitted),
            "artifacts": stable_artifacts,
            "candidates": candidates,
            "formal_library_insertions": 0,
            "strategy_effective": verdict,
            "production_authorization": "none",
            "verdict": verdict,
        }
        summary_name = (
            f"summary-{protocol.policy_sha256[:12]}-{code_hash[:12]}-{data_hash[:12]}.json"
        )
        summary_path, summary_sha, summary_reused = write_json_once(
            protocol.output_root / summary_name,
            stable_summary,
        )
        manifest: dict[str, object] = {
            "schema_version": "f1-csi800-fundamental-effect-manifest-v1",
            "protocol_id": protocol.document["protocol_id"],
            "protocol_sha256": protocol.sha256,
            "policy_sha256": protocol.policy_sha256,
            "code_snapshot_sha256": code_hash,
            "code_git_head": git_head(),
            "input_snapshot_sha256": input_identity["input_snapshot_sha256"],
            "residual_data_snapshot_sha256": data_hash,
            "residual_report": {
                "path": portable_artifact_path(residual_path),
                "sha256": sha256_file(residual_path),
            },
            "summary": {"path": portable_artifact_path(summary_path), "sha256": summary_sha},
            "artifacts": stable_artifacts,
            "candidate_attempt_count": 6,
            "experiment_trial_count": stable_summary["experiment_trial_count"],
            "direction_pass_count": stable_summary["direction_pass_count"],
            "g1_pass_count": stable_summary["g1_pass_count"],
            "formal_library_insertions": 0,
            "network_requests": 0,
            "model_training_run": False,
            "production_authorization": "none",
            "verdict": verdict,
        }
        manifest_path, manifest_sha, manifest_reused = write_json_once(
            protocol.output_root / "manifest.json", manifest
        )
        completed = True
        return {
            **manifest,
            "manifest_path": portable_artifact_path(manifest_path),
            "manifest_sha256": manifest_sha,
            "reuse": {
                "runtime_artifacts": {
                    name: bool(value["reused"])
                    for name, value in runtime_artifacts.items()
                    if isinstance(value, dict)
                },
                "experiments": all(experiment_reuse.values()),
                "g1_decisions": all(decision.reused for decision in decisions.values()),
                "summary": summary_reused,
                "manifest": manifest_reused,
            },
        }
    except Exception as error:
        if effects_started and not completed:
            record_execution_failure(
                protocol,
                code_hash=code_hash,
                data_hash=data_hash,
                error_type=type(error).__name__,
            )
        raise
