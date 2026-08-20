"""Audited, result-immutable reconciliation of the two M6 Head30 attempts."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

from shaiwei.ledger import PROJECT_ROOT, append_reconciled_experiment, sha256_file


class AttemptReconciliationError(RuntimeError):
    """Raised when historical evidence cannot support the exact ledger rows."""


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AttemptReconciliationError(f"expected JSON object: {path}")
    return value


def _load_protocol(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AttemptReconciliationError("reconciliation protocol must be a mapping")
    return value


def _resolve(root: Path, relative: str) -> Path:
    path = root / relative
    if not path.is_file():
        raise AttemptReconciliationError(f"missing reconciliation evidence: {relative}")
    return path


def _load_exact_sources(protocol: dict[str, Any], root: Path) -> dict[str, dict[str, Any]]:
    sources: dict[str, dict[str, Any]] = {}
    for name, identity in protocol["source_evidence"].items():
        path = _resolve(root, identity["path"])
        if sha256_file(path) != identity["sha256"]:
            raise AttemptReconciliationError(f"source identity mismatch: {name}")
        document = (
            yaml.safe_load(path.read_text(encoding="utf-8"))
            if path.suffix in {".yaml", ".yml"}
            else _load_json(path)
        )
        if not isinstance(document, dict):
            raise AttemptReconciliationError(f"source must be a mapping: {name}")
        sources[name] = document
    return sources


def _validate_frozen_contract(
    protocol: dict[str, Any], sources: dict[str, dict[str, Any]]
) -> None:
    frozen = protocol["frozen_contract"]
    base_attempt = sources["base_protocol"]["attempt_policy"]
    expected = {
        "attempt_family": frozen["attempt_family"],
        "canonical_ledger": protocol["authority"]["canonical_ledger"],
        "required_candidate_source": frozen["candidate_source"],
        "required_model_or_engine": frozen["model_or_engine"],
    }
    if any(base_attempt.get(key) != value for key, value in expected.items()):
        raise AttemptReconciliationError("base attempt contract differs from reconciliation")
    if not base_attempt.get("failed_after_effect_read_still_consumes_attempt"):
        raise AttemptReconciliationError("failed effect reads must consume an attempt")
    for key in ("r1_release", "r2_release"):
        release = sources[key]
        expected_scope = protocol["source_evidence"][key]["release_scope_sha256"]
        if release.get("release_scope_sha256") != expected_scope:
            raise AttemptReconciliationError(f"release scope mismatch: {key}")
        scope = release.get("scope", {})
        if scope.get("authority", {}).get("experiment_ledger_write_authorized") is not False:
            raise AttemptReconciliationError(f"original release did not forbid ledger writes: {key}")
        if scope.get("outputs", {}).get("experiment_ledger_write_authorized") is not False:
            raise AttemptReconciliationError(f"original output unexpectedly allowed ledger writes: {key}")


def _validate_attempt_evidence(
    protocol: dict[str, Any], sources: dict[str, dict[str, Any]]
) -> None:
    attempts = protocol["attempts"]
    r1, r2 = attempts
    failure = sources["r1_failure"]
    if not (
        failure.get("release_scope_sha256") == r1["release_scope_sha256"]
        and failure.get("real_effect_read") is True
        and failure.get("portfolio_attempts_consumed") == 1
        and failure.get("formal_effect_report_written") is False
        and failure.get("strategy_effective") == "NOT_EVALUATED"
        and failure.get("production_authorization") == "none"
        and failure.get("failed_at") == r1["terminal_at"]
    ):
        raise AttemptReconciliationError("R1 failure does not prove exactly one consumed attempt")
    report = sources["r2_report"]
    audit_failure = sources["r2_audit_failure"]
    if not (
        report.get("release_scope_sha256") == r2["release_scope_sha256"]
        and report.get("portfolio_attempts_consumed") == 1
        and report.get("decision") == "VALIDATED_RESEARCH_SCALE"
        and report.get("production_authorization") == "none"
        and audit_failure.get("portfolio_attempts_consumed") == 1
        and audit_failure.get("family_portfolio_attempts_consumed") == 2
        and audit_failure.get("audit_failed_at") == r2["terminal_at"]
    ):
        raise AttemptReconciliationError("R2 evidence does not prove the second consumed attempt")
    authority = sources["r7_authority"]
    if not (
        authority.get("family_portfolio_attempts_consumed") == 2
        and authority.get("additional_portfolio_attempt_count") == 0
        and authority.get("independent_audit") == "PASS"
        and authority.get("strategy_effective") == "VALIDATED_RESEARCH_SCALE"
        and authority.get("production_authorization") == "none"
    ):
        raise AttemptReconciliationError("R7 does not establish the authoritative family state")
    for attempt, release_key in zip(attempts, ("r1_release", "r2_release"), strict=True):
        image = sources[release_key]["scope"]["image"]
        if image.get("code_snapshot_sha256") != attempt["code_snapshot_sha256"]:
            raise AttemptReconciliationError(f"code snapshot mismatch: {release_key}")
        if image.get("git_commit") != attempt["git_commit"]:
            raise AttemptReconciliationError(f"Git identity mismatch: {release_key}")


def _attempt_row(
    *,
    protocol: dict[str, Any],
    attempt: dict[str, Any],
    parent_id: str,
    data_snapshot_sha256: str,
    result: dict[str, Any],
) -> dict[str, object]:
    frozen = protocol["frozen_contract"]
    return {
        "experiment_id": attempt["experiment_id"],
        "parent_experiment_id": parent_id,
        "ts": attempt["terminal_at"],
        "candidate_source": frozen["candidate_source"],
        "model_or_engine": frozen["model_or_engine"],
        "engine_version": frozen["engine_version"],
        "seed": "",
        "prompt_hash": "",
        "code_sha256": attempt["code_snapshot_sha256"],
        "data_snapshot_sha256": data_snapshot_sha256,
        "feature_or_formula": "rank-head Top30 equal-weight full-target conversion of sealed M6 scores",
        "params_json": {
            "attempt_family": frozen["attempt_family"],
            "attempt_ordinal": attempt["ordinal"],
            "git_commit": attempt["git_commit"],
            "historical_reconciliation": True,
            "release_scope_sha256": attempt["release_scope_sha256"],
        },
        "train_period": "sealed M6 W1-W6; no model fit",
        "valid_period": "historical W1-W6 production-converter evaluation",
        "result_json": result,
        "admitted": frozen["admitted"],
        "reject_reason": frozen["reject_reason"],
    }


def build_rows(protocol_path: Path, *, root: Path = PROJECT_ROOT) -> list[dict[str, object]]:
    protocol = _load_protocol(protocol_path)
    if protocol.get("schema_version") != "m6-production-head30-attempt-ledger-reconciliation-v1":
        raise AttemptReconciliationError("unsupported reconciliation schema")
    if protocol["authority"].get("new_attempt_increment") != 0:
        raise AttemptReconciliationError("historical reconciliation must not create an attempt")
    sources = _load_exact_sources(protocol, root)
    _validate_frozen_contract(protocol, sources)
    _validate_attempt_evidence(protocol, sources)
    attempts = protocol["attempts"]
    r1_scope = sources["r1_release"]["scope"]
    r2_scope = sources["r2_release"]["scope"]
    r1_snapshot = r1_scope["inputs"]["sealed_m6_effect"]["tree_sha256"]
    r2_snapshot = r2_scope["inputs"]["sealed_m6_effect"]["tree_sha256"]
    if r1_snapshot != r2_snapshot:
        raise AttemptReconciliationError("R1 and R2 do not share the sealed M6 input")
    r1_failure = sources["r1_failure"]
    r2_report = sources["r2_report"]
    authority = sources["r7_authority"]
    rows = [
        _attempt_row(
            protocol=protocol,
            attempt=attempts[0],
            parent_id="",
            data_snapshot_sha256=r1_snapshot,
            result={
                "attempt_consumed": True,
                "authoritative": False,
                "error_type": r1_failure["error_type"],
                "failure_evidence_sha256": protocol["source_evidence"]["r1_failure"]["sha256"],
                "production_authorization": "none",
                "status": attempts[0]["terminal_status"],
                "strategy_effective": "NOT_EVALUATED",
                "successor_release_scope_sha256": attempts[1]["release_scope_sha256"],
            },
        ),
        _attempt_row(
            protocol=protocol,
            attempt=attempts[1],
            parent_id=attempts[1]["parent_experiment_id"],
            data_snapshot_sha256=r2_snapshot,
            result={
                "attempt_consumed": True,
                "authoritative": True,
                "authoritative_audit_sha256": authority["audit_sha256"],
                "authoritative_decision": authority["strategy_effective"],
                "first_pass_replay_equal": r2_report["first_pass_replay_equal"],
                "primary_result_sha256": r2_report["result_sha256"],
                "production_authorization": "none",
                "report_sha256": protocol["source_evidence"]["r2_report"]["sha256"],
                "status": attempts[1]["terminal_status"],
            },
        ),
    ]
    expected_ids = set(protocol["frozen_contract"]["deterministic_experiment_ids"].values())
    if {str(row["experiment_id"]) for row in rows} != expected_ids:
        raise AttemptReconciliationError("deterministic experiment IDs differ from protocol")
    return rows


def _normalized(row: dict[str, object]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for key, value in row.items():
        if key in {"params_json", "result_json"} and isinstance(value, (dict, list)):
            normalized[key] = json.dumps(value, ensure_ascii=False, sort_keys=True)
        elif isinstance(value, bool):
            normalized[key] = str(value).lower()
        else:
            normalized[key] = str(value)
    return normalized


def verify_target_rows(ledger_path: Path, expected: list[dict[str, object]]) -> list[dict[str, str]]:
    with ledger_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    expected_by_id = {str(row["experiment_id"]): _normalized(row) for row in expected}
    actual = [row for row in rows if row.get("experiment_id") in expected_by_id]
    if len(actual) != len(expected_by_id):
        raise AttemptReconciliationError("ledger does not contain exactly two reconciled attempts")
    for row in actual:
        if row != expected_by_id[row["experiment_id"]]:
            raise AttemptReconciliationError(f"reconciled ledger row differs: {row['experiment_id']}")
    return sorted(actual, key=lambda row: row["experiment_id"])


def reconcile(
    protocol_path: Path, ledger_path: Path, *, root: Path = PROJECT_ROOT
) -> dict[str, Any]:
    protocol = _load_protocol(protocol_path)
    sources_before = {
        name: sha256_file(_resolve(root, identity["path"]))
        for name, identity in protocol["source_evidence"].items()
    }
    rows = build_rows(protocol_path, root=root)
    for row in rows:
        append_reconciled_experiment(path=ledger_path, **row)
    if any(append_reconciled_experiment(path=ledger_path, **row) for row in rows):
        raise AttemptReconciliationError("idempotency replay unexpectedly appended a row")
    actual = verify_target_rows(ledger_path, rows)
    sources_after = {
        name: sha256_file(_resolve(root, identity["path"]))
        for name, identity in protocol["source_evidence"].items()
    }
    if sources_before != sources_after:
        raise AttemptReconciliationError("source evidence changed during reconciliation")
    row_sha256 = hashlib.sha256(
        json.dumps(actual, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return {
        "schema_version": "m6-production-head30-attempt-ledger-reconciliation-receipt-v1",
        "reconciliation_id": protocol["reconciliation_id"],
        "reconciled_at": protocol["reconciled_at"],
        "attempt_family": protocol["frozen_contract"]["attempt_family"],
        "target_experiment_ids": sorted(row["experiment_id"] for row in actual),
        "target_row_count": len(actual),
        "target_rows_sha256": row_sha256,
        "idempotency_replay_new_rows": 0,
        "new_attempt_increment": 0,
        "authoritative_decision": "VALIDATED_RESEARCH_SCALE",
        "production_authorization": "none",
        "source_evidence_unchanged": True,
        "status": "PASS",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, default=PROJECT_ROOT / "ledger/experiments.csv")
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    receipt = reconcile(args.protocol.resolve(), args.ledger.resolve())
    payload = json.dumps(receipt, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    if args.receipt.exists() and args.receipt.read_text(encoding="utf-8") != payload:
        raise AttemptReconciliationError("existing reconciliation receipt differs")
    args.receipt.write_text(payload, encoding="utf-8")
    print(payload, end="")


if __name__ == "__main__":
    main()
