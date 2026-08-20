"""Synthetic daemon fixture for both repaired M6-5B-R1 CLI entrypoints."""

from __future__ import annotations

import argparse
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
from typing import Any

from shaiwei.research.production_conversion.real_contract import write_once_document

from .entrypoint_recovery_audit import main as audit_main
from .entrypoint_recovery_contract import EntrypointRecoveryProtocol
from .entrypoint_recovery_run import main as runner_main
from .release_fixture import build_fixture as build_domain_fixture


def _runner_mapping() -> dict[str, Path]:
    captured: dict[str, Path] = {}

    def executor(**kwargs: Path) -> dict[str, str]:
        captured.update(kwargs)
        return {"status": "PASS"}

    argv = [
        "--release", "/synthetic/release.json", "--approval", "/synthetic/approval.json",
        "--r2-root", "/synthetic/r2", "--r7-audit", "/synthetic/r7.json",
        "--raw-manifest", "/synthetic/raw.json", "--project-root", "/synthetic/project",
        "--output-root", "/synthetic/output",
    ]
    with redirect_stdout(io.StringIO()):
        runner_main(argv, executor=executor)
    return captured


def _auditor_mapping() -> dict[str, Path]:
    captured: dict[str, Path] = {}

    def auditor(**kwargs: Path) -> dict[str, str]:
        captured.update(kwargs)
        return {"status": "PASS"}

    argv = [
        "--release", "/synthetic/release.json", "--approval", "/synthetic/approval.json",
        "--effect-root", "/synthetic/effect", "--audit-root", "/synthetic/audit",
    ]
    with redirect_stdout(io.StringIO()):
        audit_main(argv, auditor=auditor)
    return captured


def build_fixture() -> dict[str, Any]:
    protocol = EntrypointRecoveryProtocol.load()
    runner = _runner_mapping()
    auditor = _auditor_mapping()
    if set(runner) != {
        "release_path", "approval_path", "r2_root", "r7_audit", "raw_manifest",
        "project_root", "output_root",
    }:
        raise RuntimeError("M6-5B-R1 runner CLI mapping differs")
    if set(auditor) != {"release_path", "approval_path", "effect_root", "audit_root"}:
        raise RuntimeError("M6-5B-R1 auditor CLI mapping differs")
    domain = build_domain_fixture()
    if domain["status"] != "PASS":
        raise RuntimeError("M6-5B-R1 synthetic domain fixture failed")
    return {
        "schema_version": "m6-head30-500k-entrypoint-recovery-fixture-v1",
        "status": "PASS", "entrypoint_recovery_protocol_sha256": protocol.sha256,
        "runner_cli_mapping_pass": True, "auditor_cli_mapping_pass": True,
        "internal_replay_pass": domain["deterministic_replay"],
        "independent_reconstruction_pass": domain["independent_reconstruction"],
        "execute_day_reused": domain["execute_day_reused"],
        "real_target_read": False, "real_price_or_effect_read": False,
        "network_used": False, "model_fit_count": 0, "production_authorization": "none",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    document = build_fixture()
    digest, reused = write_once_document(parser.parse_args().output, document)
    print(json.dumps({**document, "sha256": digest, "reused": reused}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
