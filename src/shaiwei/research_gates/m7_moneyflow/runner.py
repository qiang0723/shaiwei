"""Thin approved M7 runner with an internal deterministic replay."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .compute import compute_quality_core
from .contract import InputManifest, M7GateError, M7Protocol, canonical_json, sha256_json
from .reader import load_key_inputs
from .release import ApprovalEnvelope, DataReleaseScope
from .sealing import seal_run


def build_report(
    protocol: M7Protocol,
    manifest: InputManifest,
    release: DataReleaseScope,
    approval: ApprovalEnvelope,
    *,
    input_root: Path,
) -> dict[str, object]:
    inputs = load_key_inputs(protocol, manifest, input_root=input_root)
    first = compute_quality_core(protocol, inputs)
    replay = compute_quality_core(protocol, inputs)
    first_sha = sha256_json(first)
    replay_sha = sha256_json(replay)
    if first != replay or first_sha != replay_sha:
        raise M7GateError("M7 runner internal replay differs")
    run_identity = {
        "protocol_sha256": protocol.sha256,
        "input_manifest_sha256": manifest.sha256,
        "release_scope_sha256": release.sha256,
        "approval_sha256": approval.sha256,
        "code_bundle_sha256": release.scope["implementation"]["code_bundle_sha256"],
    }
    return {
        "schema_version": "m7-moneyflow-data-compatibility-report-v1",
        "run_id": sha256_json(run_identity),
        "protocol_id": protocol.document["protocol_id"],
        "protocol_scope_sha256": protocol.build_document["protocol_scope_sha256"],
        "protocol_sha256": protocol.sha256,
        "build_contract_sha256": protocol.build_sha256,
        "input_manifest_sha256": manifest.sha256,
        "input_manifest_physical_sha256": manifest.physical_sha256,
        "release_scope_sha256": release.sha256,
        "approval_sha256": approval.sha256,
        "code_bundle_sha256": release.scope["implementation"]["code_bundle_sha256"],
        "execution_kind": "REAL_APPROVED_KEY_ONLY_DATA_GATE",
        "semantic_rows_read": True,
        "source_evidence": inputs.evidence,
        "core_sha256": first_sha,
        "internal_replay": {
            "status": "PASS",
            "first_pass_core_sha256": first_sha,
            "replay_core_sha256": replay_sha,
        },
        **first,
        "label_or_return_read": False,
        "effect_read": False,
        "model_training_run": False,
        "backtest_run": False,
        "provider_call_count": 0,
        "provider_cost_usd": "0.00",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--build-contract", type=Path, required=True)
    parser.add_argument("--input-manifest", type=Path, required=True)
    parser.add_argument("--release-scope", type=Path, required=True)
    parser.add_argument("--approval-envelope", type=Path, required=True)
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        protocol = M7Protocol.load(
            args.protocol,
            build_path=args.build_contract,
            project_root=args.input_root,
        )
        manifest = InputManifest.load(args.input_manifest, protocol)
        release = DataReleaseScope.load(args.release_scope, protocol, manifest)
        approval = ApprovalEnvelope.load(args.approval_envelope, release)
        report = build_report(
            protocol,
            manifest,
            release,
            approval,
            input_root=args.input_root,
        )
        result = seal_run(args.output_root, report)
    except (M7GateError, OSError, TypeError, ValueError, json.JSONDecodeError) as error:
        print(canonical_json({"status": "FAIL", "error_class": type(error).__name__, "message": str(error)}))
        return 2
    print(canonical_json({"status": "PASS", **result}))
    return 0 if str(result["verdict"]).startswith("GO_") else 3


if __name__ == "__main__":
    raise SystemExit(main())
