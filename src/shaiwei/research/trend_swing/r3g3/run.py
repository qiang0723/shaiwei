"""One-shot offline R3G-3 diagnostic runner."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from shaiwei.provenance import verify_release_manifest
from shaiwei.research.trend_swing.r3g3.compute import compute_diagnostic
from shaiwei.research.trend_swing.r3g3.contract import (
    DiagnosticProtocol,
    RECOVERY_ACTION,
    verify_entrypoint_recovery,
)
from shaiwei.research.trend_swing.r3g3.evidence import (
    R3G3Error,
    canonical_json,
    file_manifest,
    write_once_json,
)
from shaiwei.research.trend_swing.r3g3.reader import load_inputs


def _runtime_identity() -> dict[str, str]:
    revision = os.environ.get("SHAIWEI_RELEASE_GIT_HEAD", "").strip().lower()
    manifest = os.environ.get("SHAIWEI_RELEASE_MANIFEST", "").strip()
    if len(revision) != 40 or not manifest:
        raise R3G3Error("R3G-3 release runtime identity is absent")
    snapshot = verify_release_manifest(Path(manifest))
    return {"git_commit": revision, "code_snapshot_sha256": snapshot}


def run(
    *,
    protocol_path: Path,
    recovery_scope_path: Path,
    input_root: Path,
    output_root: Path,
) -> dict[str, object]:
    if not output_root.is_dir() or any(output_root.iterdir()):
        raise R3G3Error("R3G-3 output root is absent or non-empty")
    protocol = DiagnosticProtocol.load(protocol_path)
    recovery_scope_sha = verify_entrypoint_recovery(recovery_scope_path, protocol)
    runtime = _runtime_identity()
    write_once_json(
        output_root / "authorization.json",
        {
            "schema_version": "ts-v5-r3g3-diagnostic-authorization-v1",
            "action": RECOVERY_ACTION,
            "protocol_sha256": protocol.sha256,
            "entrypoint_recovery_scope_sha256": recovery_scope_sha,
            "prior_runner_invocation_count": 1,
            "recovery_runner_invocation_count": 1,
            "strategy_effect_attempt_increment": 0,
            "external_network": False,
            "holdout_read": False,
            "partial_2026_read": False,
            "production_authorization": "none",
            "runtime": runtime,
        },
    )
    first = compute_diagnostic(protocol, load_inputs(protocol, input_root))
    write_once_json(output_root / "first_pass/diagnostic.json", first)
    replay = compute_diagnostic(protocol, load_inputs(protocol, input_root))
    write_once_json(output_root / "replay/diagnostic.json", replay)
    if canonical_json(first) != canonical_json(replay):
        raise R3G3Error("R3G-3 deterministic replay differs")
    report_sha = write_once_json(output_root / "report.json", first)
    manifest_sha = write_once_json(output_root / "manifest.json", file_manifest(output_root))
    return {
        "verdict": first["verdict"],
        "parent_verdict": first["parent_verdict"],
        "strategy_effect_attempt_increment": 0,
        "diagnostic_report_sha256": report_sha,
        "diagnostic_manifest_sha256": manifest_sha,
        "production_authorization": "none",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--recovery-scope", type=Path, required=True)
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    print(
        json.dumps(
            run(
                protocol_path=args.protocol,
                recovery_scope_path=args.recovery_scope,
                input_root=args.input_root,
                output_root=args.output_root,
            ),
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
