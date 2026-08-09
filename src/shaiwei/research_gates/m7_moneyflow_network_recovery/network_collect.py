"""Sequential collection of one sealed M7 recovery request plan."""

from __future__ import annotations

from pathlib import Path
from time import sleep
from typing import Any, Callable

from shaiwei.research_gates.m7_moneyflow.contract import sha256_json

from shaiwei.research_gates.m7_moneyflow_recovery.batch_store import (
    BatchIdentity,
    write_batch,
)
from shaiwei.research_gates.m7_moneyflow_recovery.contract import RecoveryProtocol
from shaiwei.research_gates.m7_moneyflow_recovery.planning import MoneyflowRequest
from shaiwei.research_gates.m7_moneyflow_recovery.providers import (
    BaostockQueryClient,
    TushareQueryClient,
    collect_moneyflow,
    collect_status,
)

from .request_plan import RequestPlanData
from .sealing import write_canonical_once


Pause = Callable[[float], None]


def _seal_collection(
    batch_root: Path,
    *,
    release_scope_sha256: str,
    role: str,
    receipts: list[dict[str, Any]],
    total_attempt_count: int,
) -> dict[str, Any]:
    document = {
        "schema_version": "m7-moneyflow-recovery-collection-manifest-v1",
        "release_scope_sha256": release_scope_sha256,
        "role": role,
        "request_count": len(receipts),
        "total_transport_attempt_count": total_attempt_count,
        "receipt_identity_bundle_sha256": sha256_json(
            [str(item["receipt_sha256"]) for item in receipts]
        ),
        "request_identity_bundle_sha256": sha256_json(
            [str(item["request_sha256"]) for item in receipts]
        ),
        "semantic_retry_count": 0,
        "sequential_execution": True,
        "security_codes_in_manifest": False,
        "production_ledger_written": False,
        "production_authorization": "none",
    }
    manifest_sha = write_canonical_once(batch_root / "collection_manifest.json", document)
    return {**document, "manifest_sha256": manifest_sha}


def collect_status_plan(
    protocol: RecoveryProtocol,
    plan: RequestPlanData,
    *,
    release_scope_sha256: str,
    client: BaostockQueryClient,
    batch_root: Path,
    claim_root: Path,
    inter_request_seconds: float = 0.10,
    pause: Pause = sleep,
) -> dict[str, Any]:
    receipts: list[dict[str, Any]] = []
    attempts = 0
    for index, request in enumerate(plan.status_requests):
        result = collect_status(
            claim_root,
            release_scope_sha256=release_scope_sha256,
            client=client,
            request=request,
        )
        attempts += result.attempt_count
        receipts.append(
            write_batch(
                batch_root,
                BatchIdentity(
                    release_scope_sha256,
                    request.identity_sha256,
                    "baostock.history_k_data_plus",
                    "exact_status_window",
                ),
                result.value,
            )
        )
        if index + 1 < len(plan.status_requests):
            pause(inter_request_seconds)
    return _seal_collection(
        batch_root,
        release_scope_sha256=release_scope_sha256,
        role="status_collector",
        receipts=receipts,
        total_attempt_count=attempts,
    )


def collect_moneyflow_plan(
    protocol: RecoveryProtocol,
    plan: RequestPlanData,
    *,
    release_scope_sha256: str,
    client: TushareQueryClient,
    batch_root: Path,
    claim_root: Path,
    inter_request_seconds: float = 0.25,
    pause: Pause = sleep,
) -> dict[str, Any]:
    requests: tuple[MoneyflowRequest, ...] = plan.moneyflow_requests
    receipts: list[dict[str, Any]] = []
    attempts = 0
    for index, request in enumerate(requests):
        result = collect_moneyflow(
            claim_root,
            release_scope_sha256=release_scope_sha256,
            client=client,
            protocol=protocol,
            request=request,
        )
        attempts += result.attempt_count
        receipts.append(
            write_batch(
                batch_root,
                BatchIdentity(
                    release_scope_sha256,
                    request.identity_sha256,
                    "tushare.moneyflow",
                    request.shape,
                ),
                result.value,
            )
        )
        if index + 1 < len(requests):
            pause(inter_request_seconds)
    return _seal_collection(
        batch_root,
        release_scope_sha256=release_scope_sha256,
        role="moneyflow_collector",
        receipts=receipts,
        total_attempt_count=attempts,
    )


def collection_activation_id(
    *, release_scope_sha256: str, plan_manifest_sha256: str, role: str
) -> str:
    return sha256_json(
        {
            "release_scope_sha256": release_scope_sha256,
            "plan_manifest_sha256": plan_manifest_sha256,
            "role": role,
        }
    )
