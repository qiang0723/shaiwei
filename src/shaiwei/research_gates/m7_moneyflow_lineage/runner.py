"""One-shot M7 lineage runner with pre-read claim and internal replay."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from shaiwei.research_gates.m7_moneyflow.consumption import execute_after_pre_read_claim
from shaiwei.research_gates.m7_moneyflow.contract import M7GateError, canonical_json, sha256_json

from .compute import compute_lineage_core
from .contract import LineageError, LineageInputManifest, LineageProtocol
from .reader import load_lineage_inputs
from .release import LineageApproval, LineageRelease
from .sealing import seal_run


def run_identity(
    protocol: LineageProtocol,
    manifest: LineageInputManifest,
    release: LineageRelease,
    approval: LineageApproval,
) -> dict[str, str]:
    return {
        "protocol_sha256": protocol.sha256,
        "input_manifest_sha256": manifest.sha256,
        "release_scope_sha256": release.sha256,
        "approval_sha256": approval.sha256,
        "code_bundle_sha256": release.scope["implementation"]["code_bundle_sha256"],
    }


def build_report(
    protocol: LineageProtocol,
    manifest: LineageInputManifest,
    release: LineageRelease,
    approval: LineageApproval,
    *,
    input_root: Path,
    claim_root: Path,
) -> dict[str, object]:
    identity = run_identity(protocol, manifest, release, approval)
    run_id = sha256_json(identity)
    claim, inputs = execute_after_pre_read_claim(
        claim_root,
        {
            "protocol_sha256": protocol.sha256,
            "release_scope_sha256": release.sha256,
            "approval_sha256": approval.sha256,
            "role": "runner",
            "run_id": run_id,
        },
        lambda: load_lineage_inputs(protocol, manifest, input_root=input_root),
    )
    first = compute_lineage_core(protocol, inputs)
    replay = compute_lineage_core(protocol, inputs)
    first_sha = sha256_json(first)
    if first != replay or first_sha != sha256_json(replay):
        raise LineageError("lineage runner internal replay differs")
    return {
        "schema_version": "m7-moneyflow-gap-lineage-report-v1",
        "run_id": run_id,
        "protocol_id": protocol.document["protocol_id"],
        **identity,
        "input_manifest_physical_sha256": manifest.physical_sha256,
        "execution_kind": "REAL_APPROVED_KEY_STATUS_LINEAGE_ONLY",
        "semantic_rows_read": True,
        "source_evidence": inputs.evidence,
        "core_sha256": first_sha,
        "internal_replay": {
            "status": "PASS",
            "first_pass_core_sha256": first_sha,
            "replay_core_sha256": first_sha,
        },
        "pre_read_consumption": claim,
        **first,
        "security_codes_persisted": False,
        "adjusted_coverage_computed": False,
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
    parser.add_argument("--input-manifest", type=Path, required=True)
    parser.add_argument("--release-scope", type=Path, required=True)
    parser.add_argument("--approval-envelope", type=Path, required=True)
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--claim-root", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        protocol = LineageProtocol.load(args.protocol, project_root=args.input_root)
        manifest = LineageInputManifest.load(args.input_manifest, protocol)
        release = LineageRelease.load(args.release_scope, protocol, manifest)
        approval = LineageApproval.load(args.approval_envelope, release)
        result = seal_run(
            args.output_root,
            build_report(
                protocol,
                manifest,
                release,
                approval,
                input_root=args.input_root,
                claim_root=args.claim_root,
            ),
        )
    except (LineageError, M7GateError, OSError, TypeError, ValueError, json.JSONDecodeError) as error:
        print(canonical_json({"status": "FAIL", "error_class": type(error).__name__, "message": str(error)}))
        return 2
    print(canonical_json({"status": "PASS", **result}))
    return 0 if str(result["verdict"]).startswith("GO_") else 3


if __name__ == "__main__":
    raise SystemExit(main())
