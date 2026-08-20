"""Approved one-shot production Head30 treatment runner with internal replay."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable

from shaiwei.research.model_attribution.contract import canonical_sha256
from shaiwei.research.production_conversion.contract import ProtocolError
from shaiwei.research.production_conversion.execution import backtest_treatment
from shaiwei.research.production_conversion.metrics import WINDOWS, evaluate
from shaiwei.research.production_conversion.real_contract import (
    Approval,
    ReleaseProtocol,
    ReleaseScope,
    write_once_document,
)
from shaiwei.research.production_conversion.real_inputs import (
    initialize_qlib,
    load_sealed_passes,
    verify_input_identities,
)
from shaiwei.research.model_attribution.contract import ProtocolBundle


IdentityVerifier = Callable[..., dict[str, Any]]
InputLoader = Callable[..., dict[str, dict[str, Any]]]
Initializer = Callable[[Path], None]
TreatmentRunner = Callable[..., dict[str, Any]]


def _require_empty(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    if any(root.iterdir()):
        raise ProtocolError("production-converter effect output exists before one-shot run")


def _window_dates() -> dict[str, tuple[str, str]]:
    rows = ProtocolBundle.load().result["windows"]
    values = {str(row["name"]): (str(row["test"][0]), str(row["test"][1])) for row in rows}
    if tuple(values) != WINDOWS:
        raise ProtocolError("production-converter predecessor window set differs")
    return values


def _control_active(controls: dict[str, list[dict[str, Any]]]) -> dict[str, list[float]]:
    output: dict[str, list[float]] = {}
    for window in WINDOWS:
        output[window] = [
            (1.0 + float(row["gross_return"]) - float(row["recorded_cost"]))
            / (1.0 + float(row["benchmark_return"]))
            - 1.0
            for row in controls[window]
        ]
    return output


def _build_pass(
    sealed: dict[str, Any],
    protocol: ReleaseProtocol,
    treatment_runner: TreatmentRunner,
) -> dict[str, Any]:
    dates = _window_dates()
    treatments = {
        window: treatment_runner(
            sealed["predictions"][window],
            start=dates[window][0],
            end=dates[window][1],
            protocol=protocol.base,
        )
        for window in WINDOWS
    }
    result = evaluate(treatments, sealed["controls"])
    return {
        "schema_version": "m6-production-head30-pass-bundle-v1",
        "converter_protocol_sha256": protocol.base.sha256,
        "release_engineering_sha256": protocol.sha256,
        "treatments": treatments,
        "control_base_daily_active_return": _control_active(sealed["controls"]),
        "result": result,
    }


def run(
    *,
    protocol_path: Path | None = None,
    release_path: Path,
    approval_path: Path,
    provider_root: Path,
    m6_effect_root: Path,
    m6_audit_path: Path,
    output_root: Path,
    identity_verifier: IdentityVerifier = verify_input_identities,
    input_loader: InputLoader = load_sealed_passes,
    initializer: Initializer = initialize_qlib,
    treatment_runner: TreatmentRunner = backtest_treatment,
) -> dict[str, Any]:
    protocol = ReleaseProtocol.load(protocol_path)
    release = ReleaseScope.load(release_path, protocol)
    approval = Approval.load(approval_path, release)
    runtime = release.verify_runtime_identity()
    inputs = identity_verifier(provider_root, m6_effect_root, m6_audit_path, protocol, release)
    _require_empty(output_root)
    write_once_document(
        output_root / "authorization.json",
        {
            "schema_version": "m6-production-head30-run-authorization-v1",
            "release_scope_sha256": release.sha256,
            "approval_sha256": approval.sha256,
            "action": approval.document["action"],
            "production_authorization": "none",
        },
    )
    started = False
    try:
        write_once_document(
            output_root / "treatment_effect_started.json",
            {
                "release_scope_sha256": release.sha256,
                "portfolio_attempts_consumed": 1,
                "same_release_retry_authorized": False,
            },
        )
        started = True
        sealed = input_loader(m6_effect_root, release)
        if set(sealed) != {"first_pass", "replay"}:
            raise ProtocolError("production-converter sealed pass set differs")
        initializer(provider_root)
        bundles: dict[str, dict[str, Any]] = {}
        hashes: dict[str, str] = {}
        for name in ("first_pass", "replay"):
            bundle = _build_pass(sealed[name], protocol, treatment_runner)
            digest, _ = write_once_document(output_root / name / "bundle.json", bundle)
            bundles[name], hashes[name] = bundle, digest
        if hashes["first_pass"] != hashes["replay"] or bundles["first_pass"] != bundles["replay"]:
            raise ProtocolError("production-converter first-pass and replay differ")
        result = bundles["first_pass"]["result"]
        report = {
            "schema_version": "m6-production-head30-real-effect-report-v1",
            "release_scope_sha256": release.sha256,
            "approval_sha256": approval.sha256,
            "runtime_identity": runtime,
            "inputs": inputs,
            "first_pass_bundle_sha256": hashes["first_pass"],
            "replay_bundle_sha256": hashes["replay"],
            "first_pass_replay_equal": True,
            "result_sha256": canonical_sha256(result),
            "decision": result["decision"],
            "portfolio_attempts_consumed": 1,
            "model_attempt_increment": 0,
            "strategy_effective": "PENDING_INDEPENDENT_AUDIT",
            "production_authorization": "none",
        }
        report_sha, reused = write_once_document(output_root / "report.json", report)
        return {"report_sha256": report_sha, "reused": reused, "decision": result["decision"], "production_authorization": "none"}
    except Exception as error:
        write_once_document(
            output_root / "failure.json",
            {
                "schema_version": "m6-production-head30-real-effect-failure-v1",
                "release_scope_sha256": release.sha256,
                "approval_sha256": approval.sha256,
                "treatment_effect_started": started,
                "portfolio_attempts_consumed": 1 if started else 0,
                "same_release_retry_authorized": False,
                "error_type": type(error).__name__,
                "error_message": str(error)[:500],
                "production_authorization": "none",
            },
        )
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--approval", type=Path, required=True)
    parser.add_argument("--provider-root", type=Path, required=True)
    parser.add_argument("--m6-effect-root", type=Path, required=True)
    parser.add_argument("--m6-audit", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(protocol_path=args.protocol, release_path=args.release, approval_path=args.approval, provider_root=args.provider_root, m6_effect_root=args.m6_effect_root, m6_audit_path=args.m6_audit, output_root=args.output_root), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
