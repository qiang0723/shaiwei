"""Claim-first ordinal-two M6-5C entitlement recovery runner."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable

from shaiwei.paper.stock_dividend_entitlement import execute_entitlement_recovery_day
from shaiwei.research.effect_attempt_claim import EffectAttemptSpec, read_effect_after_claim
from shaiwei.research.model_attribution.audit_recovery_contract import effect_tree_identity
from shaiwei.research.model_attribution.contract import canonical_sha256, sha256_file
from shaiwei.research.production_conversion.contract import ProtocolError
from shaiwei.research.production_conversion.real_contract import write_once_document

from ..delisting_release_metrics import evaluate
from ..delisting_release_simulation import run_all
from ..sealed_inputs import load as load_sealed, verify_tree
from ..source_reader import load_sources
from .contract import Approval, ReleaseProtocol, ReleaseScope


def _empty(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    if any(root.iterdir()):
        raise ProtocolError("M6-5C-C-R4 effect root is not empty")


def _spec(release: ReleaseScope) -> EffectAttemptSpec:
    claim = release.scope["attempt_claim"]["spec"]
    return EffectAttemptSpec(
        attempt_family=claim["attempt_family"],
        release_scope_sha256=release.sha256,
        attempt_ordinal=claim["attempt_ordinal"],
        parent_experiment_id=claim["parent_experiment_id"],
        candidate_source=claim["candidate_source"],
        model_or_engine=claim["model_or_engine"],
        engine_version=claim["engine_version"],
        code_sha256=release.scope["implementation"]["source_bundle_sha256"],
        data_snapshot_sha256=release.scope["attempt_claim"]["input_identity_sha256"],
        feature_or_formula=claim["feature_or_formula"],
        train_period=claim["train_period"],
        valid_period=claim["valid_period"],
    )


def _read_and_run(
    receipt: dict[str, object],
    *,
    release: ReleaseScope,
    r2_root: Path,
    r7_audit: Path,
    raw_manifest: Path,
    project_root: Path,
) -> dict[str, Any]:
    verify_tree(r2_root, release)
    expected_r7 = release.scope["inputs"]["r7_audit"]
    if sha256_file(r7_audit) != expected_r7["sha256"]:
        raise ProtocolError("M6-5C-C-R4 R7 audit identity differs")
    raw = release.scope["inputs"]["raw_batch_manifest"]
    if sha256_file(raw_manifest) != raw["sha256"]:
        raise ProtocolError("M6-5C-C-R4 raw manifest identity differs")
    sealed = load_sealed(r2_root, release)
    sources = load_sources(raw_manifest, sealed, project_root=project_root)
    passes = []
    for _ in range(2):
        result = run_all(
            sealed,
            sources,
            day_executor=execute_entitlement_recovery_day,
        )
        result["result"] = evaluate(result)
        passes.append(result)
    if passes[0] != passes[1]:
        raise ProtocolError("M6-5C-C-R4 internal replay differs")
    return {"receipt": receipt, "first": passes[0], "replay": passes[1]}


def execute_loaded(
    *,
    release: ReleaseScope,
    approval: Approval,
    r2_root: Path,
    r7_audit: Path,
    raw_manifest: Path,
    project_root: Path,
    ledger_path: Path,
    receipt_path: Path,
    output_root: Path,
    effect_reader: Callable[[dict[str, object]], dict[str, Any]] | None = None,
    claimed_at: str | None = None,
) -> dict[str, Any]:
    runtime = release.verify_runtime_identity()
    _empty(output_root)
    claim_invoked = False
    reader = effect_reader or (
        lambda receipt: _read_and_run(
            receipt,
            release=release,
            r2_root=r2_root,
            r7_audit=r7_audit,
            raw_manifest=raw_manifest,
            project_root=project_root,
        )
    )
    try:
        claim_invoked = True
        payload = read_effect_after_claim(
            _spec(release),
            ledger_path=ledger_path,
            receipt_path=receipt_path,
            effect_reader=reader,
            claimed_at=claimed_at,
        )
        receipt = payload["receipt"]
        first, replay = payload["first"], payload["replay"]
        authorization = {
            "schema_version": "m6-head30-500k-delisting-entitlement-authorization-v1",
            "release_scope_sha256": release.sha256,
            "approval_sha256": approval.sha256,
            "claim_receipt_sha256": receipt["receipt_sha256"],
            "experiment_id": receipt["experiment_id"],
            "action": approval.document["action"],
            "production_authorization": "none",
        }
        write_once_document(output_root / "authorization.json", authorization)
        write_once_document(
            output_root / "effect_started.json",
            {
                "release_scope_sha256": release.sha256,
                "claim_receipt_sha256": receipt["receipt_sha256"],
                "attempt_ordinal": 2,
                "new_attempts_consumed": 1,
                "same_scope_retry_authorized": False,
            },
        )
        first_sha, _ = write_once_document(output_root / "first_pass/bundle.json", first)
        replay_sha, _ = write_once_document(output_root / "replay/bundle.json", replay)
        if first_sha != replay_sha:
            raise ProtocolError("M6-5C-C-R4 physical replay differs")
        result = first["result"]
        report = {
            "schema_version": "m6-head30-500k-delisting-entitlement-effect-report-v1",
            "release_scope_sha256": release.sha256,
            "approval_sha256": approval.sha256,
            "claim_receipt_sha256": receipt["receipt_sha256"],
            "experiment_id": receipt["experiment_id"],
            "parent_experiment_id": "6797875cf3c0",
            "runtime_identity": runtime,
            "sealed_r2_tree": effect_tree_identity(r2_root),
            "r7_audit_sha256": sha256_file(r7_audit),
            "raw_manifest_sha256": sha256_file(raw_manifest),
            "first_pass_bundle_sha256": first_sha,
            "replay_bundle_sha256": replay_sha,
            "first_pass_replay_equal": True,
            "result_sha256": canonical_sha256(result),
            "decision": result["decision"],
            "family_attempts_before_run": 1,
            "new_attempts_consumed": 1,
            "total_family_attempts": 2,
            "strategy_effectiveness_authority": "NOT_FOR_PRODUCTION_VERDICT",
            "production_authorization": "none",
        }
        report_sha, reused = write_once_document(output_root / "report.json", report)
        return {"report_sha256": report_sha, "reused": reused, "decision": result["decision"]}
    except Exception as error:
        write_once_document(
            output_root / "failure.json",
            {
                "schema_version": "m6-head30-500k-delisting-entitlement-effect-failure-v1",
                "release_scope_sha256": release.sha256,
                "approval_sha256": approval.sha256,
                "claim_receipt_exists": receipt_path.is_file(),
                "attempt_consumed_conservative": claim_invoked,
                "attempt_ordinal": 2,
                "same_scope_retry_authorized": False,
                "error_type": type(error).__name__,
                "error_message": str(error)[:500],
                "production_authorization": "none",
            },
        )
        raise


def run(**paths: Path) -> dict[str, Any]:
    protocol = ReleaseProtocol.load()
    release = ReleaseScope.load(paths.pop("release_path"), protocol)
    approval = Approval.load(paths.pop("approval_path"), release)
    return execute_loaded(release=release, approval=approval, **paths)


def main(argv: list[str] | None = None, *, executor: Any = run) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "release",
        "approval",
        "r2-root",
        "r7-audit",
        "raw-manifest",
        "project-root",
        "ledger",
        "claim-receipt",
        "output-root",
    ):
        parser.add_argument(f"--{name}", type=Path, required=True)
    values = vars(parser.parse_args(argv))
    result = executor(
        release_path=values["release"],
        approval_path=values["approval"],
        r2_root=values["r2_root"],
        r7_audit=values["r7_audit"],
        raw_manifest=values["raw_manifest"],
        project_root=values["project_root"],
        ledger_path=values["ledger"],
        receipt_path=values["claim_receipt"],
        output_root=values["output_root"],
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
