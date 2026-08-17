"""One-shot W7 lineage runner; it never reads strategy outcomes."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Callable

from shaiwei.research.model_attribution.effect_data import initialize_effect_qlib
from shaiwei.research.trend_swing.r3g2.contract import EffectProtocol, R3G2Error
from shaiwei.research.trend_swing.r3g2.evidence import write_once_json
from shaiwei.research.trend_swing.r3g2.w7_control import Approval, ReleaseScope
from shaiwei.research.trend_swing.r3g2.w7_lineage import fit_w7, save_pass


PassRunner = Callable[[Path, EffectProtocol, Path], dict[str, Any]]
Initializer = Callable[[Path], None]
InputVerifier = Callable[[ReleaseScope, Path], dict[str, Any]]
RuntimeVerifier = Callable[[ReleaseScope], dict[str, str]]


def execute_pass(root: Path, protocol: EffectProtocol, provider_root: Path) -> dict[str, Any]:
    return save_pass(root, fit_w7(protocol, provider_root, initialize=False), protocol)


def _empty(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    if any(root.iterdir()):
        raise R3G2Error("R3G-2 W7 output exists before the one-shot run")


def run(
    *,
    release_path: Path,
    approval_path: Path,
    provider_root: Path,
    output_root: Path,
    pass_runner: PassRunner = execute_pass,
    initializer: Initializer = initialize_effect_qlib,
    input_verifier: InputVerifier = lambda release, root: release.verify_provider(root),
    runtime_verifier: RuntimeVerifier = lambda release: release.verify_runtime_identity(),
) -> dict[str, Any]:
    protocol = EffectProtocol.load()
    release = ReleaseScope.load(release_path, protocol)
    approval = Approval.load(approval_path, release)
    runtime = runtime_verifier(release)
    inputs = input_verifier(release, provider_root)
    _empty(output_root)
    write_once_json(
        output_root / "authorization.json",
        {
            "schema_version": "ts-v5-r3g2-w7-run-authorization-v1",
            "release_scope_sha256": release.sha256,
            "approval_sha256": approval.sha256,
            "action": approval.document["action"],
            "strategy_effect_attempt_count": 0,
            "production_authorization": "none",
        },
    )
    started = False
    try:
        write_once_json(
            output_root / "lineage_read_started.json",
            {
                "release_scope_sha256": release.sha256,
                "complete_passes": ["first_pass", "replay"],
                "same_release_retry_authorized": False,
                "strategy_effect_attempt_count": 0,
            },
        )
        started = True
        initializer(provider_root)
        first = pass_runner(output_root / "first_pass", protocol, provider_root)
        replay = pass_runner(output_root / "replay", protocol, provider_root)
        if first["bundle_sha256"] != replay["bundle_sha256"]:
            raise R3G2Error("R3G-2 W7 internal replay bundle differs")
        report = {
            "schema_version": "ts-v5-r3g2-w7-lineage-report-v1",
            "release_scope_sha256": release.sha256,
            "approval_sha256": approval.sha256,
            "runtime_identity": runtime,
            "inputs": inputs,
            "first_pass": first,
            "replay": replay,
            "deterministic_replay": True,
            "label_rankic_return_or_effect_read": False,
            "strategy_effect_attempt_count": 0,
            "strategy_effective": "NOT_EVALUATED",
            "production_authorization": "none",
            "verdict": "PENDING_INDEPENDENT_W7_LINEAGE_AUDIT",
        }
        digest, reused = write_once_json(output_root / "report.json", report)
        return {"report_sha256": digest, "reused": reused, "verdict": report["verdict"]}
    except Exception as error:
        write_once_json(
            output_root / "failure.json",
            {
                "schema_version": "ts-v5-r3g2-w7-lineage-failure-v1",
                "release_scope_sha256": release.sha256,
                "lineage_read_started": started,
                "same_release_retry_authorized": False,
                "strategy_effect_attempt_count": 0,
                "error_type": type(error).__name__,
                "error_message": str(error)[:500],
                "strategy_effective": "NOT_EVALUATED",
                "production_authorization": "none",
            },
        )
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
