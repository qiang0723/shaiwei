"""Shared authority and sealed-input loading for M7 network recovery roles."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from shaiwei.research_gates.m7_moneyflow.contract import sha256_file, sha256_json

from shaiwei.research_gates.m7_moneyflow_recovery.batch_reader import (
    assemble_inputs,
    read_receipt,
)
from shaiwei.research_gates.m7_moneyflow_recovery.contract import (
    RecoveryError,
    RecoveryProtocol,
)
from shaiwei.research_gates.m7_moneyflow_recovery.inputs import RecoveryInputs
from shaiwei.research_gates.m7_moneyflow_recovery.projection_sealing import (
    logical_target_sha256,
)
from shaiwei.research_gates.m7_moneyflow_recovery.target_projection import (
    OUTPUT_COLUMNS,
    recovery_request_targets,
)

from .network_contract import NetworkReleaseProtocol
from .network_release import NetworkRecoveryApproval, NetworkRecoveryRelease
from .request_plan import RequestPlanData
from .request_plan_store import read_request_plan
from .sealing import read_canonical


@dataclass(frozen=True)
class RuntimeAuthority:
    network: NetworkReleaseProtocol
    recovery: RecoveryProtocol
    release: NetworkRecoveryRelease
    approval: NetworkRecoveryApproval
    plan_manifest: dict[str, Any]
    plan_manifest_sha256: str
    plan_root: Path


@dataclass(frozen=True)
class SealedRuntimeInputs:
    plan: RequestPlanData
    inputs: RecoveryInputs
    batch_manifest_sha256: str
    receipt_count: int
    collection_manifests: dict[str, dict[str, Any]]


def load_runtime_authority(
    project_root: Path,
    *,
    plan_root: Path,
    release_scope: Path,
    approval_envelope: Path,
) -> RuntimeAuthority:
    network = NetworkReleaseProtocol.load(
        project_root / "config/m7_moneyflow_evidence_recovery_network_release_v1.yaml",
        project_root=project_root,
    )
    recovery = RecoveryProtocol.load(
        project_root / "config/m7_moneyflow_evidence_recovery_v1.yaml",
        engineering_path=project_root / "config/m7_moneyflow_evidence_recovery_engineering_v1.yaml",
        project_root=project_root,
    )
    manifest_path = plan_root / "request_plan_manifest.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise RecoveryError("recovery network request-plan manifest is missing")
    manifest_sha = sha256_file(manifest_path)
    plan_manifest = read_canonical(manifest_path)
    release = NetworkRecoveryRelease.load(
        release_scope,
        network,
        plan_manifest=plan_manifest,
        plan_manifest_sha256=manifest_sha,
    )
    approval = NetworkRecoveryApproval.load(approval_envelope, release)
    return RuntimeAuthority(
        network,
        recovery,
        release,
        approval,
        plan_manifest,
        manifest_sha,
        plan_root,
    )


def load_runtime_plan(authority: RuntimeAuthority) -> RequestPlanData:
    plan, observed = read_request_plan(
        authority.plan_root,
        expected_manifest_sha256=authority.plan_manifest_sha256,
    )
    if observed != authority.plan_manifest:
        raise RecoveryError("recovery network request-plan manifest changed")
    return plan


def role_activation_id(authority: RuntimeAuthority, role: str) -> str:
    return sha256_json(
        {
            "release_scope_sha256": authority.release.sha256,
            "approval_sha256": authority.approval.sha256,
            "plan_manifest_sha256": authority.plan_manifest_sha256,
            "role": role,
        }
    )


def _load_target(
    authority: RuntimeAuthority,
    *,
    target_root: Path,
    track: str,
) -> pd.DataFrame:
    item = authority.plan_manifest["target_identity"][track]
    filename = authority.network.document["frozen_predecessors"][f"{track}_target"]["file"]
    path = target_root / str(filename)
    if path.is_symlink() or not path.is_file() or sha256_file(path) != item["physical_sha256"]:
        raise RecoveryError("recovery network projected target physical identity differs")
    projected = pd.read_parquet(path, columns=list(OUTPUT_COLUMNS)).astype("string")
    if (
        logical_target_sha256(projected) != item["logical_sha256"]
        or len(projected) != int(item["member_rows"])
        or len(projected.drop_duplicates(["ts_code", "source_date"]))
        != int(item["unique_source_keys"])
    ):
        raise RecoveryError("recovery network projected target logical identity differs")
    return recovery_request_targets(projected)


def _receipt_path(root: Path, source: str, shape: str, request_sha256: str) -> Path:
    return root / source / shape / request_sha256 / "receipt.json"


def _verify_collection_manifest(
    root: Path,
    *,
    role: str,
    release_scope_sha256: str,
    expected_request_sha256s: list[str],
    expected_receipts: list[Path],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    manifest_path = root / "collection_manifest.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise RecoveryError("recovery network collection manifest is missing")
    manifest = read_canonical(manifest_path)
    observed_paths = set(root.rglob("receipt.json"))
    if observed_paths != set(expected_receipts):
        raise RecoveryError("recovery network collection receipt set differs")
    receipts = [read_receipt(root, path)[0] for path in expected_receipts]
    if (
        manifest.get("role") != role
        or manifest.get("release_scope_sha256") != release_scope_sha256
        or int(manifest.get("request_count", -1)) != len(expected_request_sha256s)
        or manifest.get("request_identity_bundle_sha256")
        != sha256_json(expected_request_sha256s)
        or manifest.get("receipt_identity_bundle_sha256")
        != sha256_json([str(item["receipt_sha256"]) for item in receipts])
    ):
        raise RecoveryError("recovery network collection manifest identity differs")
    return {**manifest, "manifest_sha256": sha256_file(manifest_path)}, receipts


def assemble_runtime_inputs(
    authority: RuntimeAuthority,
    *,
    target_root: Path,
    status_root: Path,
    moneyflow_root: Path,
) -> SealedRuntimeInputs:
    plan = load_runtime_plan(authority)
    track_a = _load_target(authority, target_root=target_root, track="track_a")
    track_b = _load_target(authority, target_root=target_root, track="track_b")
    status_ids = [item.identity_sha256 for item in plan.status_requests]
    full_ids = [item.identity_sha256 for item in plan.full_market_requests]
    targeted_ids = [item.identity_sha256 for item in plan.targeted_requests]
    status_paths = [
        _receipt_path(status_root, "baostock.history_k_data_plus", "exact_status_window", item)
        for item in status_ids
    ]
    full_paths = [
        _receipt_path(moneyflow_root, "tushare.moneyflow", "full_market_by_trade_date", item)
        for item in full_ids
    ]
    targeted_paths = [
        _receipt_path(moneyflow_root, "tushare.moneyflow", "one_security_one_date", item)
        for item in targeted_ids
    ]
    status_manifest, status_receipts = _verify_collection_manifest(
        status_root,
        role="status_collector",
        release_scope_sha256=authority.release.sha256,
        expected_request_sha256s=status_ids,
        expected_receipts=status_paths,
    )
    moneyflow_manifest, moneyflow_receipts = _verify_collection_manifest(
        moneyflow_root,
        role="moneyflow_collector",
        release_scope_sha256=authority.release.sha256,
        expected_request_sha256s=[*full_ids, *targeted_ids],
        expected_receipts=[*full_paths, *targeted_paths],
    )
    inputs = assemble_inputs(
        authority.recovery,
        release_scope_sha256=authority.release.sha256,
        status_root=status_root,
        moneyflow_root=moneyflow_root,
        track_a=track_a,
        track_b=track_b,
        daily_keys=track_b[["ts_code", "trade_date"]].drop_duplicates().reset_index(drop=True),
        official_dates=plan.official_dates,
        status_receipts=status_paths,
        full_market_receipts=full_paths,
        targeted_receipts=targeted_paths,
        status_request_sha256s=frozenset(status_ids),
        full_market_request_sha256s=frozenset(full_ids),
        targeted_request_sha256s=frozenset(targeted_ids),
    )
    receipts = [*status_receipts, *moneyflow_receipts]
    return SealedRuntimeInputs(
        plan,
        inputs,
        sha256_json(receipts),
        len(receipts),
        {"status": status_manifest, "moneyflow": moneyflow_manifest},
    )
