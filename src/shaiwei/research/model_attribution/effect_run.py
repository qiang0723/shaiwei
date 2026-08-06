"""Approved one-shot M6-2 runner with one real pass and one complete replay."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Callable

from shaiwei.research.model_attribution.contract import (
    AttributionError,
    ProtocolBundle,
    canonical_sha256,
    sha256_file,
)
from shaiwei.research.model_attribution.effect_artifacts import save_pass
from shaiwei.research.model_attribution.effect_contract import (
    EffectApproval,
    EffectProtocol,
    EffectReleaseScope,
    write_once_document,
)
from shaiwei.research.model_attribution.effect_data import (
    WindowModelOutput,
    fit_window,
    initialize_effect_qlib,
)
from shaiwei.research.model_attribution.effect_execution import (
    execute_window,
    scheduled_top30,
    score_overlap_diagnostics,
)
from shaiwei.research.model_attribution.effect_metrics import evaluate_effect
from shaiwei.research.model_attribution.effect_schema import ARMS, WINDOWS


PassRunner = Callable[[Path, EffectProtocol], dict[str, Any]]
Initializer = Callable[[Path], None]
InputVerifier = Callable[[Path, EffectProtocol, EffectReleaseScope], dict[str, Any]]


def execute_pass(root: Path, protocol: EffectProtocol) -> dict[str, Any]:
    windows = {str(row["name"]): row for row in protocol.result["windows"]}
    if tuple(windows) != WINDOWS:
        raise AttributionError("M6 real window set differs")
    outputs: dict[str, WindowModelOutput] = {}
    reports: dict[str, dict[str, Any]] = {}
    stress_reports: dict[str, Any] = {}
    top30: dict[str, dict[str, dict[str, list[str]]]] = {}
    score_diagnostics: dict[str, Any] = {}
    for name in WINDOWS:
        output = fit_window(protocol.result, windows[name])
        window_reports, stress = execute_window(output, windows[name], protocol.result)
        outputs[name] = output
        reports[name] = window_reports
        if stress:
            stress_reports = stress
        top30[name] = {
            arm: scheduled_top30(
                output.test_predictions[arm],
                rebalance_days=int(protocol.result["portfolio"]["rebalance_trade_days"]),
            )
            for arm in ARMS
        }
        score_diagnostics[name] = score_overlap_diagnostics(output.test_predictions)
    if tuple(stress_reports) != ARMS:
        raise AttributionError("M6 W6 stress reports are incomplete")
    effect = evaluate_effect(
        {window: outputs[window].mature_predictions for window in WINDOWS},
        {window: outputs[window].mature_labels for window in WINDOWS},
        reports,
        stress_reports,
        protocol.result,
    )
    summary = {
        "schema_version": "m6-model-attribution-pass-summary-v1",
        "protocol_sha256": protocol.sha256,
        "result_protocol_sha256": protocol.result_sha256,
        "model_fit_count": len(WINDOWS) * 2,
        "blend_model_fit_count": 0,
        "window_count": len(WINDOWS),
        "arm_count": len(ARMS),
        "score_diagnostics": score_diagnostics,
        "effect": effect,
        "strategy_effective": "NOT_YET_AUDITED",
        "production_authorization": "none",
    }
    saved = save_pass(root, outputs, reports, stress_reports, top30, summary)
    return {**saved, "summary_sha256": canonical_sha256(summary), "decision": effect["inference"]["decision"]}


def _require_empty_output(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    if any(root.iterdir()):
        raise AttributionError("M6 effect output exists before the approved one-shot run")


def _verify_inputs(
    provider_root: Path, protocol: EffectProtocol, release: EffectReleaseScope
) -> dict[str, Any]:
    bundle = ProtocolBundle.load()
    metadata = bundle.verify_metadata_inputs(
        provider_root / "_shaiwei_manifest.json",
        provider_root / "calendars/day.txt",
    )
    expected = release.scope["inputs"]
    observed = {
        "qlib_manifest_sha256": metadata["qlib_manifest_sha256"],
        "qlib_tree_sha256": metadata["qlib_tree_sha256"],
        "qlib_file_count": metadata["qlib_file_count"],
        "calendar_sha256": sha256_file(provider_root / "calendars/day.txt"),
        "calendar_row_count": metadata["calendar_row_count"],
    }
    if observed != expected:
        raise AttributionError("M6 release input identity differs")
    if protocol.result_sha256 != bundle.result_sha256:
        raise AttributionError("M6 runtime result protocol differs")
    return observed


def run(
    *,
    release_path: Path,
    approval_path: Path,
    provider_root: Path,
    output_root: Path,
    pass_runner: PassRunner = execute_pass,
    initializer: Initializer = initialize_effect_qlib,
    input_verifier: InputVerifier = _verify_inputs,
) -> dict[str, Any]:
    protocol = EffectProtocol.load()
    release = EffectReleaseScope.load(release_path, protocol)
    approval = EffectApproval.load(approval_path, release)
    runtime = release.verify_runtime_identity()
    inputs = input_verifier(provider_root, protocol, release)
    _require_empty_output(output_root)
    write_once_document(
        output_root / "authorization.json",
        {
            "schema_version": "m6-model-attribution-run-authorization-v1",
            "release_scope_sha256": release.sha256,
            "approval_sha256": approval.sha256,
            "action": approval.document["action"],
            "production_authorization": "none",
        },
    )
    effect_read_started = False
    try:
        write_once_document(
            output_root / "effect_read_started.json",
            {
                "release_scope_sha256": release.sha256,
                "alternative_attempts_consumed": 2,
                "same_release_retry_authorized": False,
            },
        )
        effect_read_started = True
        initializer(provider_root)
        first = pass_runner(output_root / "first_pass", protocol)
        replay = pass_runner(output_root / "replay", protocol)
        if first["bundle_sha256"] != replay["bundle_sha256"]:
            raise AttributionError("M6 first pass and replay artifact bundles differ")
        if first["summary_sha256"] != replay["summary_sha256"]:
            raise AttributionError("M6 first pass and replay summaries differ")
        if first["decision"] != replay["decision"]:
            raise AttributionError("M6 first pass and replay decisions differ")
        report = {
            "schema_version": "m6-model-attribution-effect-report-v1",
            "release_scope_sha256": release.sha256,
            "approval_sha256": approval.sha256,
            "runtime_identity": runtime,
            "inputs": inputs,
            "first_pass": first,
            "replay": replay,
            "deterministic_replay": True,
            "alternative_attempts_consumed": 2,
            "decision": first["decision"],
            "strategy_effective": "PENDING_INDEPENDENT_AUDIT",
            "production_authorization": "none",
        }
        report_sha, reused = write_once_document(output_root / "report.json", report)
        return {
            "report_sha256": report_sha,
            "reused": reused,
            "decision": report["decision"],
            "strategy_effective": report["strategy_effective"],
            "production_authorization": "none",
        }
    except Exception as error:
        failure = {
            "schema_version": "m6-model-attribution-effect-failure-v1",
            "release_scope_sha256": release.sha256,
            "approval_sha256": approval.sha256,
            "effect_read_started": effect_read_started,
            "alternative_attempts_consumed": 2 if effect_read_started else 0,
            "same_release_retry_authorized": False,
            "error_type": type(error).__name__,
            "error_message": str(error)[:500],
            "strategy_effective": "NOT_EVALUATED",
            "production_authorization": "none",
        }
        write_once_document(output_root / "failure.json", failure)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--approval", type=Path, required=True)
    parser.add_argument("--provider-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    import json

    print(
        json.dumps(
            run(
                release_path=args.release,
                approval_path=args.approval,
                provider_root=args.provider_root,
                output_root=args.output_root,
            ),
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
