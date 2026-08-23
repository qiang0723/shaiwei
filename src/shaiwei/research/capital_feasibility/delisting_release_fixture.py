"""Pure synthetic claim, replay, and audit fixture for the M6-5C release image."""

from __future__ import annotations

import argparse
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
from typing import Any

import pandas as pd

from shaiwei.build_identity.registry import load_build_registry
from shaiwei.build_identity.release import component_build_snapshot_sha256
from shaiwei.research.effect_attempt_claim import EffectAttemptSpec, read_effect_after_claim
from shaiwei.research.model_attribution.contract import canonical_sha256
from shaiwei.research.production_conversion.real_contract import write_once_document

from .delisting_independent_audit import independently_evaluate
from .delisting_release_audit import main as audit_main
from .delisting_release_contract import (
    ACTION,
    COMPOSE_PATH,
    DOCKERFILE_PATH,
    IMAGE,
    SCOPE_KIND,
    SCOPE_SCHEMA,
    ReleaseProtocol,
    ReleaseScope,
    expected_authority,
)
from .delisting_release_metrics import evaluate
from .delisting_release_run import main as runner_main
from .delisting_release_simulation import run_all
from .source_reader import RawSources


HEADER = (
    "experiment_id,parent_experiment_id,ts,candidate_source,model_or_engine,engine_version,"
    "seed,prompt_hash,code_sha256,data_snapshot_sha256,feature_or_formula,params_json,"
    "train_period,valid_period,result_json,admitted,reject_reason\n"
)


def _synthetic() -> tuple[dict[str, Any], RawSources]:
    calendar = pd.bdate_range("2020-01-02", periods=55)
    dates = [day.strftime("%Y%m%d") for day in calendar]
    codes = [f"{600000 + index:06d}.SH" for index in range(30)]
    qlib_codes = [f"SH{code[:6]}" for code in codes]
    rows: list[dict[str, Any]] = []
    for offset, day in enumerate(dates):
        for index, code in enumerate(codes):
            price = 0.90 if index == 0 and offset >= 20 else 10.0
            rows.append({
                "ts_code": code,
                "trade_date": day,
                "open": price,
                "pre_close": price,
                "close": price,
                "vol": 1_000_000.0,
                "amount": 100_000.0,
                "amount_rmb": 100_000_000.0,
            })
    treatment = {
        "daily": [
            {
                "date": day.strftime("%Y-%m-%d"),
                "gross_return": 0.0,
                "recorded_cost": 0.0,
            }
            for day in calendar[25:]
        ],
        "rebalances": [{
            "trade_date": calendar[25].strftime("%Y-%m-%d"),
            "signal_date": calendar[24].strftime("%Y-%m-%d"),
            "targets": qlib_codes,
        }],
    }
    bundle = {"treatments": {f"W{index}": treatment for index in range(1, 7)}}
    sources = RawSources(
        daily=pd.DataFrame(rows),
        index_daily=pd.DataFrame([
            {"ts_code": "000906.SH", "trade_date": day, "open": 100.0, "close": 100.0}
            for day in dates[25:]
        ]),
        stock_basic=pd.DataFrame([
            {"ts_code": code, "list_date": "20100101", "delist_date": ""}
            for code in codes
        ]),
        namechange=pd.DataFrame(columns=["ts_code", "name", "start_date", "end_date"]),
        suspend=pd.DataFrame(
            columns=["ts_code", "trade_date", "suspend_type", "suspend_timing"]
        ),
        dividends=pd.DataFrame(columns=[
            "ts_code", "end_date", "ann_date", "div_proc", "stk_div", "cash_div_tax",
            "record_date", "pay_date", "div_listdate", "imp_ann_date",
        ]),
        trade_cal=pd.DataFrame([
            {"exchange": "SSE", "cal_date": day, "is_open": "1"} for day in dates
        ]),
        manifest_sha256="0" * 64,
    )
    return bundle, sources


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
    receipt = root / "attempt-claim.json"
    observations: list[tuple[bool, int]] = []

    def reader(document: dict[str, object]) -> str:
        observations.append((receipt.is_file(), len(ledger.read_text().splitlines()) - 1))
        return str(document["experiment_id"])

    spec = EffectAttemptSpec(
        attempt_family="m6_head30_500k_delisting_risk_overlay_fixture",
        release_scope_sha256="a" * 64,
        attempt_ordinal=1,
        candidate_source="synthetic-head30",
        model_or_engine="paper-v2-delisting-risk-exit",
        engine_version="fixture-v1",
        code_sha256="b" * 64,
        data_snapshot_sha256="c" * 64,
        feature_or_formula="10 valid closes < 1 CNY; latch exit; no replacement",
        train_period="none; synthetic",
        valid_period="synthetic",
    )
    experiment_id = read_effect_after_claim(
        spec,
        ledger_path=ledger,
        receipt_path=receipt,
        effect_reader=reader,
        claimed_at="2026-08-23T12:00:00+08:00",
    )
    retry_blocked = False
    try:
        read_effect_after_claim(
            spec, ledger_path=ledger, receipt_path=receipt, effect_reader=reader
        )
    except RuntimeError:
        retry_blocked = True
    return {
        "claim_before_reader": observations == [(True, 1)],
        "same_scope_retry_blocked": retry_blocked,
        "experiment_id": experiment_id,
    }


def _scope_loader_fixture(root: Path, protocol: ReleaseProtocol) -> bool:
    registry = load_build_registry(validate_filesystem=False)
    component = registry.component("m6-head30-delisting-risk-release")
    records = [
        {"path": path, "sha256": canonical_sha256({"fixture_asset": path})}
        for path in component.assets
    ]
    asset_hashes = {record["path"]: record["sha256"] for record in records}
    component_snapshot = component_build_snapshot_sha256(records)
    inputs = protocol.blocked_scope["inputs"]
    revision = "a" * 40
    source_bundle = "b" * 64
    scope = {
        "scope_kind": SCOPE_KIND,
        "created_at": "2026-08-23T12:00:00+08:00",
        "protocol_sha256": protocol.sha256,
        "recovery_protocol_sha256": protocol.recovery_sha256,
        "scope_runtime_recovery_sha256": protocol.scope_runtime_recovery_sha256,
        "implementation": {
            "git_commit": revision,
            "origin_main_commit": revision,
            "source_bundle_sha256": source_bundle,
            "source_manifest_sha256": "c" * 64,
            "registry_sha256": registry.registry_sha256,
            "build_assets": records,
            "component_build_snapshot_sha256": component_snapshot,
        },
        "image": {
            "reference": IMAGE,
            "image_id": f"sha256:{'d' * 64}",
            "git_commit": revision,
            "source_bundle_sha256": source_bundle,
            "component_build_snapshot_sha256": component_snapshot,
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
            "family_attempts_before_run": 0,
            "new_attempts_consumed_at_claim": 1,
            "total_family_attempts_after_claim": 1,
            "same_scope_retry_authorized": False,
        },
        "container": {
            "compose_path": COMPOSE_PATH.name,
            "compose_sha256": asset_hashes[COMPOSE_PATH.name],
            "dockerfile_path": DOCKERFILE_PATH.name,
            "dockerfile_sha256": asset_hashes[DOCKERFILE_PATH.name],
            "network_mode": "none",
            "read_only_root": True,
            "run_as_non_root": True,
            "cap_drop_all": True,
            "no_new_privileges": True,
            "env_file_mounted": False,
            "docker_socket_mounted": False,
            "full_project_root_mounted": False,
            "production_write_mount_present": False,
            "canonical_ledger_mount": "runner-rw-auditor-ro",
            "claim_receipt_mount": "runner-rw-auditor-ro",
            "auditor_raw_or_r2_mount": False,
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
    scope_loader_pass = _scope_loader_fixture(root, protocol)
    cli = _cli_mapping()
    claim = _claim_fixture(root)
    bundle, sources = _synthetic()
    first = run_all(bundle, sources)
    first["result"] = evaluate(first)
    replay = run_all(bundle, sources)
    replay["result"] = evaluate(replay)
    independent = independently_evaluate(first)
    risk_orders = first["result"]["risk_exit"]["order_count"]
    if (
        first != replay
        or canonical_sha256(first["result"]) != canonical_sha256(independent)
        or risk_orders != 6
        or not all(cli.values())
        or not claim["claim_before_reader"]
        or not claim["same_scope_retry_blocked"]
        or not scope_loader_pass
    ):
        raise RuntimeError("M6-5C synthetic release fixture failed")
    return {
        "schema_version": "m6-head30-500k-delisting-risk-release-fixture-v1",
        "status": "PASS",
        "protocol_sha256": protocol.sha256,
        "scope_runtime_recovery_sha256": protocol.scope_runtime_recovery_sha256,
        "release_scope_loader_pass": scope_loader_pass,
        "runner_cli_mapping_pass": cli["runner"],
        "auditor_cli_mapping_pass": cli["auditor"],
        "claim_before_effect_reader": True,
        "same_scope_retry_blocked": True,
        "internal_replay_pass": True,
        "independent_reconstruction_pass": True,
        "forced_exit_order_count": risk_orders,
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
