"""Pure synthetic daemon fixture for the ordinal-two entitlement release."""

from __future__ import annotations

import argparse
from contextlib import redirect_stdout
from dataclasses import replace
import io
import json
from pathlib import Path
from typing import Any

import pandas as pd

from shaiwei.build_identity.registry import load_build_registry
from shaiwei.build_identity.release import component_build_snapshot_sha256
from shaiwei.paper.stock_dividend_entitlement import execute_entitlement_recovery_day
from shaiwei.research.effect_attempt_claim import EffectAttemptSpec, read_effect_after_claim
from shaiwei.research.model_attribution.contract import canonical_sha256
from shaiwei.research.production_conversion.real_contract import write_once_document

from ..delisting_independent_audit import independently_evaluate
from ..delisting_release_fixture import HEADER, _synthetic
from ..delisting_release_metrics import evaluate
from ..delisting_release_simulation import run_all
from .audit import main as audit_main
from .contract import (
    ACTION,
    COMPONENT_ID,
    IMAGE,
    SCOPE_KIND,
    SCOPE_SCHEMA,
    ReleaseProtocol,
    ReleaseScope,
    expected_authority,
)
from .run import main as runner_main


def _entitlement_synthetic() -> tuple[dict[str, Any], Any, str]:
    bundle, sources = _synthetic()
    calendar = sorted(sources.trade_cal["cal_date"].astype(str).unique())
    code = "600000.SH"
    dividends = pd.DataFrame(
        [
            {
                "ts_code": code,
                "end_date": "20191231",
                "ann_date": calendar[26],
                "div_proc": "实施",
                "stk_div": 0.1,
                "cash_div_tax": 0.0,
                "record_date": calendar[27],
                "pay_date": calendar[32],
                "div_listdate": calendar[32],
                "imp_ann_date": calendar[26],
            }
        ]
    )
    return bundle, replace(sources, dividends=dividends), code


def _detached_round_trip(result: dict[str, Any], code: str) -> bool:
    for window in result["windows"].values():
        held = [code in row["held_after"] for row in window["risk_trace"]]
        transitions = list(zip(held, held[1:], strict=False))
        if sum(before is False and after is True for before, after in transitions) != 1:
            return False
        if sum(before is True and after is False for before, after in transitions) != 2:
            return False
    return True


def _cli_mapping() -> dict[str, bool]:
    runner: dict[str, Path] = {}
    auditor: dict[str, Path] = {}

    def capture_runner(**kwargs: Path) -> dict[str, str]:
        runner.update(kwargs)
        return {"status": "PASS"}

    def capture_auditor(**kwargs: Path) -> dict[str, str]:
        auditor.update(kwargs)
        return {"status": "PASS"}

    runner_argv = [
        "--release", "/fixture/release", "--approval", "/fixture/approval",
        "--r2-root", "/fixture/r2", "--r7-audit", "/fixture/r7",
        "--raw-manifest", "/fixture/raw", "--project-root", "/fixture/project",
        "--ledger", "/fixture/experiments.csv", "--claim-receipt", "/fixture/claim",
        "--output-root", "/fixture/effect",
    ]
    audit_argv = [
        "--release", "/fixture/release", "--approval", "/fixture/approval",
        "--effect-root", "/fixture/effect", "--ledger", "/fixture/experiments.csv",
        "--claim-receipt", "/fixture/claim", "--audit-root", "/fixture/audit",
    ]
    with redirect_stdout(io.StringIO()):
        runner_main(runner_argv, executor=capture_runner)
        audit_main(audit_argv, auditor=capture_auditor)
    return {
        "runner": set(runner) == {
            "release_path", "approval_path", "r2_root", "r7_audit", "raw_manifest",
            "project_root", "ledger_path", "receipt_path", "output_root",
        },
        "auditor": set(auditor) == {
            "release_path", "approval_path", "effect_root", "ledger_path",
            "receipt_path", "audit_root",
        },
    }


def _claim_fixture(root: Path) -> dict[str, object]:
    ledger = root / "experiments.csv"
    ledger.write_text(HEADER, encoding="utf-8")
    receipt = root / "claim.json"
    observations: list[tuple[bool, int]] = []

    def reader(document: dict[str, object]) -> str:
        observations.append((receipt.is_file(), len(ledger.read_text().splitlines()) - 1))
        return str(document["experiment_id"])

    spec = EffectAttemptSpec(
        attempt_family="m6_head30_500k_delisting_risk_overlay_fixture",
        release_scope_sha256="a" * 64,
        attempt_ordinal=2,
        parent_experiment_id="6797875cf3c0",
        candidate_source="synthetic-head30",
        model_or_engine="paper-v2-delisting-risk-exit",
        engine_version="fixture-entitlement-v2",
        code_sha256="b" * 64,
        data_snapshot_sha256="c" * 64,
        feature_or_formula="preserve detached stock rights",
        train_period="none; synthetic",
        valid_period="synthetic",
    )
    experiment_id = read_effect_after_claim(
        spec,
        ledger_path=ledger,
        receipt_path=receipt,
        effect_reader=reader,
        claimed_at="2026-08-23T20:00:00+08:00",
    )
    retry_blocked = False
    try:
        read_effect_after_claim(
            spec, ledger_path=ledger, receipt_path=receipt, effect_reader=reader
        )
    except RuntimeError:
        retry_blocked = True
    row = ledger.read_text(encoding="utf-8").splitlines()[1]
    return {
        "claim_before_reader": observations == [(True, 1)],
        "same_scope_retry_blocked": retry_blocked,
        "experiment_id": experiment_id,
        "parent_present": "6797875cf3c0" in row,
        "ordinal": json.loads(receipt.read_text(encoding="utf-8"))["attempt_ordinal"],
    }


def _scope_loader_fixture(root: Path, protocol: ReleaseProtocol) -> bool:
    registry = load_build_registry(validate_filesystem=False)
    component = registry.component(COMPONENT_ID)
    records = [
        {"path": path, "sha256": canonical_sha256({"fixture_asset": path})}
        for path in component.assets
    ]
    revision = "a" * 40
    source_bundle = "b" * 64
    inputs = protocol.failed_scope["inputs"]
    scope = {
        "scope_kind": SCOPE_KIND,
        "created_at": "2026-08-23T20:00:00+08:00",
        "protocol_sha256": protocol.sha256,
        "implementation": {
            "git_commit": revision,
            "origin_main_commit": revision,
            "source_bundle_sha256": source_bundle,
            "source_manifest_sha256": "c" * 64,
            "registry_sha256": registry.registry_sha256,
            "build_assets": records,
            "component_build_snapshot_sha256": component_build_snapshot_sha256(records),
        },
        "image": {
            "reference": IMAGE,
            "image_id": f"sha256:{'d' * 64}",
            "git_commit": revision,
            "source_bundle_sha256": source_bundle,
            "component_build_snapshot_sha256": component_build_snapshot_sha256(records),
            "labels": {},
        },
        "inputs": inputs,
        "attempt_claim": {
            "spec": protocol.document["attempt_claim"],
            "input_identity_sha256": canonical_sha256(inputs),
            "claim_before_effect_reader": True,
        },
        "execution": {
            "approval_action": ACTION,
            "runner_invocation_count": 1,
            "complete_internal_passes": ["first_pass", "replay"],
            "independent_auditor_invocation_count": 1,
            "attempt_family": "m6_head30_500k_delisting_risk_overlay_v1",
            "family_attempts_before_run": 1,
            "new_attempts_consumed_at_claim": 1,
            "total_family_attempts_after_claim": 2,
            "same_scope_retry_authorized": False,
        },
        "container": {
            "network_mode": "none", "read_only_root": True, "run_as_non_root": True,
            "cap_drop_all": True, "no_new_privileges": True, "env_file_mounted": False,
            "docker_socket_mounted": False, "full_project_root_mounted": False,
            "production_write_mount_present": False,
            "canonical_ledger_mount": "runner-rw-auditor-ro",
            "claim_receipt_mount": "runner-rw-auditor-ro", "auditor_raw_or_r2_mount": False,
        },
        "authority": expected_authority(),
    }
    document = {
        "schema_version": SCOPE_SCHEMA,
        "release_scope_sha256": canonical_sha256(scope),
        "scope": scope,
    }
    path = root / "release-scope.json"
    path.write_text(json.dumps(document, sort_keys=True) + "\n", encoding="utf-8")
    return ReleaseScope.load(path, protocol).sha256 == document["release_scope_sha256"]


def build_fixture(root: Path) -> dict[str, Any]:
    protocol = ReleaseProtocol.load()
    root.mkdir(parents=True, exist_ok=True)
    scope_loader = _scope_loader_fixture(root, protocol)
    cli = _cli_mapping()
    claim = _claim_fixture(root)
    bundle, sources, code = _entitlement_synthetic()
    first = run_all(bundle, sources, day_executor=execute_entitlement_recovery_day)
    first["result"] = evaluate(first)
    replay = run_all(bundle, sources, day_executor=execute_entitlement_recovery_day)
    replay["result"] = evaluate(replay)
    rebuilt = independently_evaluate(first)
    detached = _detached_round_trip(first, code)
    if not all(
        (
            first == replay,
            canonical_sha256(first["result"]) == canonical_sha256(rebuilt),
            detached,
            all(cli.values()),
            claim["claim_before_reader"],
            claim["same_scope_retry_blocked"],
            claim["parent_present"],
            claim["ordinal"] == 2,
            scope_loader,
        )
    ):
        raise RuntimeError("M6-5C-C-R4 synthetic fixture failed")
    return {
        "schema_version": "m6-head30-500k-delisting-entitlement-release-fixture-v1",
        "status": "PASS",
        "protocol_sha256": protocol.sha256,
        "release_scope_loader_pass": True,
        "runner_cli_mapping_pass": True,
        "auditor_cli_mapping_pass": True,
        "claim_before_effect_reader": True,
        "same_scope_retry_blocked": True,
        "attempt_ordinal": 2,
        "parent_experiment_id": "6797875cf3c0",
        "internal_replay_pass": True,
        "independent_reconstruction_pass": True,
        "detached_entitlement_round_trip_pass": True,
        "real_target_or_price_or_effect_read": False,
        "canonical_ledger_write": False,
        "network_used": False,
        "production_authorization": "none",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    document = build_fixture(args.root)
    digest, reused = write_once_document(args.output, document)
    print(json.dumps({**document, "sha256": digest, "reused": reused}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
