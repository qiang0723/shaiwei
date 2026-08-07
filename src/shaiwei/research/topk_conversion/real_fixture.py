"""Pure synthetic M6-3C release runner and independent-auditor fixture."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
from typing import Any

from shaiwei.provenance import code_snapshot_sha256, git_head, write_release_manifest
from shaiwei.research.topk_conversion.contract import ProtocolBundle
from shaiwei.research.topk_conversion.real_audit import audit
from shaiwei.research.topk_conversion.real_contract import (
    APPROVAL_ACTION,
    RealProtocol,
    write_once_document,
)
from shaiwei.research.topk_conversion.real_release import build_release_document
from shaiwei.research.topk_conversion.real_run import run
from shaiwei.research.topk_conversion.synthetic import build_bundle


def _approval(release_sha256: str) -> dict[str, Any]:
    return {
        "schema_version": "m6-topk20-conversion-approval-v1",
        "release_scope_sha256": release_sha256,
        "action": APPROVAL_ACTION,
        "approved_at": "2026-08-07T00:00:01+00:00",
        "consumed": False,
        "qlib_read_authorized": True,
        "sealed_m6_effect_read_authorized": True,
        "reused_prediction_read_authorized": True,
        "top30_compatibility_backtest_authorized": True,
        "real_top20_backtest_authorized": True,
        "formal_effect_output_write_authorized": True,
        "independent_audit_authorized": True,
        "model_fit_authorized": False,
        "prediction_generation_authorized": False,
        "experiment_ledger_write_authorized": False,
        "external_network_authorized": False,
        "env_or_secret_read_authorized": False,
        "production_authorization": "none",
    }


def execute_fixture(output_root: Path) -> dict[str, Any]:
    protocol = RealProtocol.load()
    manifest_path = Path(os.environ.get("SHAIWEI_RELEASE_MANIFEST", ""))
    if not manifest_path.is_file():
        manifest_path = output_root / "control/release-manifest.json"
        write_release_manifest(manifest_path)
    machine = {"aarch64": "arm64", "x86_64": "amd64"}.get(
        platform.machine(), platform.machine()
    )
    head = git_head()
    release_document = build_release_document(
        protocol=protocol,
        created_at="2026-08-07T00:00:00+00:00",
        implementation_git_commit=head,
        origin_main_commit=head,
        code_snapshot=code_snapshot_sha256(),
        image_id="sha256:" + "1" * 64,
        image_platform=f"linux/{machine}",
        image_git_commit=head,
        image_release_manifest_path=manifest_path,
    )
    release_path = output_root / "control/release.json"
    approval_path = output_root / "control/approval.json"
    write_once_document(release_path, release_document)
    write_once_document(approval_path, _approval(release_document["release_scope_sha256"]))
    old_manifest = os.environ.get("SHAIWEI_RELEASE_MANIFEST")
    os.environ["SHAIWEI_RELEASE_MANIFEST"] = str(manifest_path)
    case = build_bundle(ProtocolBundle.load())["cases"]["TOPK20_CONVERSION_SUPPORTED"]

    def loader(_root: Path, _protocol: RealProtocol) -> dict[str, dict[str, Any]]:
        return {"first_pass": {"synthetic": True}, "replay": {"synthetic": True}}

    def builder(
        _sealed: dict[str, Any],
        _protocol: RealProtocol,
        *,
        on_top20_start,
    ) -> dict[str, Any]:
        on_top20_start()
        return case

    try:
        runner = run(
            release_path=release_path,
            approval_path=approval_path,
            provider_root=output_root / "no-real-qlib",
            m6_effect_root=output_root / "no-real-effect",
            m6_audit_path=output_root / "no-real-audit.json",
            output_root=output_root / "effect",
            identity_verifier=lambda *_: dict(release_document["scope"]["inputs"]),
            input_loader=loader,
            initializer=lambda _: None,
            case_builder=builder,
        )
        auditor = audit(
            release_path=release_path,
            approval_path=approval_path,
            effect_root=output_root / "effect",
            audit_root=output_root / "audit",
        )
    finally:
        if old_manifest is None:
            os.environ.pop("SHAIWEI_RELEASE_MANIFEST", None)
        else:
            os.environ["SHAIWEI_RELEASE_MANIFEST"] = old_manifest
    return {
        "runner": runner,
        "auditor": auditor,
        "real_data_read": False,
        "qlib_read": False,
        "real_backtest_count": 0,
        "production_authorization": "none",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(execute_fixture(args.output_root), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
