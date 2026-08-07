"""Approved one-shot M6-3C runner with sealed-input replay and independent-audit handoff."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable

from shaiwei.research.topk_conversion.artifacts import canonical_sha256, write_once_json
from shaiwei.research.topk_conversion.contract import ConversionError
from shaiwei.research.topk_conversion.metrics import evaluate_case
from shaiwei.research.topk_conversion.real_contract import (
    Approval,
    RealProtocol,
    ReleaseScope,
    write_once_document,
)
from shaiwei.research.topk_conversion.real_execution import build_real_case
from shaiwei.research.topk_conversion.real_inputs import (
    initialize_qlib,
    load_sealed_passes,
    verify_input_identities,
)


IdentityVerifier = Callable[[Path, Path, Path, RealProtocol, ReleaseScope], dict[str, Any]]
InputLoader = Callable[[Path, RealProtocol], dict[str, dict[str, Any]]]
Initializer = Callable[[Path], None]
CaseBuilder = Callable[..., dict[str, Any]]


def _require_empty(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    if any(root.iterdir()):
        raise ConversionError("M6-3C effect output exists before the approved one-shot run")


def _pass_bundle(case: dict[str, Any], protocol: RealProtocol) -> dict[str, Any]:
    return {
        "schema_version": "m6-topk20-conversion-real-pass-bundle-v1",
        "result_protocol_sha256": protocol.result_sha256,
        "real_release_protocol_sha256": protocol.sha256,
        "schedule_addendum_sha256": protocol.addendum_sha256,
        "case": case,
    }


def run(
    *,
    release_path: Path,
    approval_path: Path,
    provider_root: Path,
    m6_effect_root: Path,
    m6_audit_path: Path,
    output_root: Path,
    identity_verifier: IdentityVerifier = verify_input_identities,
    input_loader: InputLoader = load_sealed_passes,
    initializer: Initializer = initialize_qlib,
    case_builder: CaseBuilder = build_real_case,
) -> dict[str, Any]:
    protocol = RealProtocol.load()
    release = ReleaseScope.load(release_path, protocol)
    approval = Approval.load(approval_path, release)
    runtime = release.verify_runtime_identity()
    inputs = identity_verifier(
        provider_root, m6_effect_root, m6_audit_path, protocol, release
    )
    _require_empty(output_root)
    write_once_document(
        output_root / "authorization.json",
        {
            "schema_version": "m6-topk20-conversion-run-authorization-v1",
            "release_scope_sha256": release.sha256,
            "approval_sha256": approval.sha256,
            "action": approval.document["action"],
            "production_authorization": "none",
        },
    )
    attempts_consumed = False

    def mark_top20_start() -> None:
        nonlocal attempts_consumed
        write_once_document(
            output_root / "top20_effect_started.json",
            {
                "release_scope_sha256": release.sha256,
                "portfolio_attempts_consumed": 2,
                "same_release_retry_authorized": False,
            },
        )
        attempts_consumed = True

    try:
        sealed = input_loader(m6_effect_root, protocol)
        if set(sealed) != {"first_pass", "replay"}:
            raise ConversionError("M6-3C sealed pass set differs")
        initializer(provider_root)
        results: dict[str, dict[str, Any]] = {}
        bundle_hashes: dict[str, str] = {}
        for pass_name in ("first_pass", "replay"):
            case = case_builder(
                sealed[pass_name], protocol, on_top20_start=mark_top20_start
            )
            result = evaluate_case(case, protocol.result)
            bundle = _pass_bundle(case, protocol)
            path = output_root / pass_name / "bundle.json"
            digest, _ = write_once_json(path, bundle)
            results[pass_name], bundle_hashes[pass_name] = result, digest
        if bundle_hashes["first_pass"] != bundle_hashes["replay"]:
            raise ConversionError("M6-3C first-pass and replay physical bundles differ")
        if canonical_sha256(results["first_pass"]) != canonical_sha256(results["replay"]):
            raise ConversionError("M6-3C first-pass and replay decisions differ")
        decision = results["first_pass"]["decision"]
        report = {
            "schema_version": "m6-topk20-conversion-real-effect-report-v1",
            "release_scope_sha256": release.sha256,
            "approval_sha256": approval.sha256,
            "runtime_identity": runtime,
            "inputs": inputs,
            "first_pass_bundle_sha256": bundle_hashes["first_pass"],
            "replay_bundle_sha256": bundle_hashes["replay"],
            "first_pass_replay_equal": True,
            "result": results["first_pass"],
            "portfolio_attempts_consumed": 2,
            "model_attempt_increment": 0,
            "decision": decision,
            "strategy_effective": "PENDING_INDEPENDENT_AUDIT",
            "production_authorization": "none",
        }
        report_sha, reused = write_once_document(output_root / "report.json", report)
        return {
            "report_sha256": report_sha,
            "reused": reused,
            "decision": decision,
            "strategy_effective": "PENDING_INDEPENDENT_AUDIT",
            "production_authorization": "none",
        }
    except Exception as error:
        write_once_document(
            output_root / "failure.json",
            {
                "schema_version": "m6-topk20-conversion-real-effect-failure-v1",
                "release_scope_sha256": release.sha256,
                "approval_sha256": approval.sha256,
                "top20_effect_started": attempts_consumed,
                "portfolio_attempts_consumed": 2 if attempts_consumed else 0,
                "same_release_retry_authorized": False,
                "error_type": type(error).__name__,
                "error_message": str(error)[:500],
                "strategy_effective": "NOT_EVALUATED_FOR_PRODUCTION",
                "production_authorization": "none",
            },
        )
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--approval", type=Path, required=True)
    parser.add_argument("--provider-root", type=Path, required=True)
    parser.add_argument("--m6-effect-root", type=Path, required=True)
    parser.add_argument("--m6-audit", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    print(
        json.dumps(
            run(
                release_path=args.release,
                approval_path=args.approval,
                provider_root=args.provider_root,
                m6_effect_root=args.m6_effect_root,
                m6_audit_path=args.m6_audit,
                output_root=args.output_root,
            ),
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
