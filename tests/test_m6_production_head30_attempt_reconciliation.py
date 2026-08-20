import csv
import hashlib
import json
from pathlib import Path

import pytest
import yaml

from shaiwei.ledger import PROJECT_ROOT, append_reconciled_experiment
from shaiwei.research.production_conversion.attempt_reconciliation import (
    AttemptReconciliationError,
    build_rows,
    reconcile,
    verify_target_rows,
)


PROTOCOL = PROJECT_ROOT / "config/m6_csi800_production_head30_attempt_ledger_reconciliation_v1.yaml"
HEADER = (
    "experiment_id,parent_experiment_id,ts,candidate_source,model_or_engine,engine_version,seed,"
    "prompt_hash,code_sha256,data_snapshot_sha256,feature_or_formula,params_json,train_period,"
    "valid_period,result_json,admitted,reject_reason\n"
)


def _write(path: Path, value: dict) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (
        yaml.safe_dump(value, allow_unicode=True, sort_keys=False)
        if path.suffix == ".yaml"
        else json.dumps(value, sort_keys=True)
    )
    path.write_text(payload, encoding="utf-8")
    return hashlib.sha256(payload.encode()).hexdigest()


def _fixture_protocol(tmp_path: Path) -> Path:
    protocol = yaml.safe_load(PROTOCOL.read_text(encoding="utf-8"))
    first, second = protocol["attempts"]
    sources = {
        "base_protocol": {
            "attempt_policy": {
                "attempt_family": "m6_portfolio_converter",
                "canonical_ledger": "ledger/experiments.csv",
                "required_candidate_source": "M6-production-head30-converter",
                "required_model_or_engine": "portfolio_converter",
                "failed_after_effect_read_still_consumes_attempt": True,
            }
        },
        "r1_release": {
            "release_scope_sha256": first["release_scope_sha256"],
            "scope": {
                "authority": {"experiment_ledger_write_authorized": False},
                "outputs": {"experiment_ledger_write_authorized": False},
                "image": {
                    "code_snapshot_sha256": first["code_snapshot_sha256"],
                    "git_commit": first["git_commit"],
                },
                "inputs": {"sealed_m6_effect": {"tree_sha256": "a" * 64}},
            },
        },
        "r1_failure": {
            "release_scope_sha256": first["release_scope_sha256"],
            "real_effect_read": True,
            "portfolio_attempts_consumed": 1,
            "formal_effect_report_written": False,
            "strategy_effective": "NOT_EVALUATED",
            "production_authorization": "none",
            "failed_at": first["terminal_at"],
            "error_type": "TypeError",
        },
        "r2_release": {
            "release_scope_sha256": second["release_scope_sha256"],
            "scope": {
                "authority": {"experiment_ledger_write_authorized": False},
                "outputs": {"experiment_ledger_write_authorized": False},
                "image": {
                    "code_snapshot_sha256": second["code_snapshot_sha256"],
                    "git_commit": second["git_commit"],
                },
                "inputs": {"sealed_m6_effect": {"tree_sha256": "a" * 64}},
            },
        },
        "r2_report": {
            "release_scope_sha256": second["release_scope_sha256"],
            "portfolio_attempts_consumed": 1,
            "decision": "VALIDATED_RESEARCH_SCALE",
            "production_authorization": "none",
            "first_pass_replay_equal": True,
            "result_sha256": "b" * 64,
        },
        "r2_audit_failure": {
            "portfolio_attempts_consumed": 1,
            "family_portfolio_attempts_consumed": 2,
            "audit_failed_at": second["terminal_at"],
        },
        "r7_authority": {
            "family_portfolio_attempts_consumed": 2,
            "additional_portfolio_attempt_count": 0,
            "independent_audit": "PASS",
            "strategy_effective": "VALIDATED_RESEARCH_SCALE",
            "production_authorization": "none",
            "audit_sha256": "c" * 64,
        },
    }
    for name, document in sources.items():
        identity = protocol["source_evidence"][name]
        identity["path"] = f"evidence/{name}.{'yaml' if name == 'base_protocol' else 'json'}"
        identity["sha256"] = _write(tmp_path / identity["path"], document)
    protocol_path = tmp_path / "protocol.yaml"
    _write(protocol_path, protocol)
    return protocol_path


def test_reconciliation_builds_exactly_two_consumed_attempt_rows(tmp_path: Path):
    protocol = _fixture_protocol(tmp_path)
    rows = build_rows(protocol, root=tmp_path)
    assert [row["experiment_id"] for row in rows] == ["e97f4e185e33", "3ce8e73c0733"]
    assert [row["params_json"]["attempt_ordinal"] for row in rows] == [1, 2]
    assert rows[0]["result_json"]["status"] == "FAILED_AFTER_EFFECT_READ"
    assert rows[1]["result_json"]["authoritative_decision"] == "VALIDATED_RESEARCH_SCALE"
    assert all(row["admitted"] is False for row in rows)


def test_reconciliation_is_idempotent_and_detects_mutated_target(tmp_path: Path):
    protocol = _fixture_protocol(tmp_path)
    ledger = tmp_path / "experiments.csv"
    ledger.write_text(HEADER, encoding="utf-8")
    first = reconcile(protocol, ledger, root=tmp_path)
    second = reconcile(protocol, ledger, root=tmp_path)
    assert first == second
    assert first["target_row_count"] == 2
    assert first["idempotency_replay_new_rows"] == 0
    with ledger.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 2
    rows[0]["code_sha256"] = "0" * 64
    with ledger.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(AttemptReconciliationError, match="differs"):
        verify_target_rows(ledger, build_rows(protocol, root=tmp_path))


def test_reconciled_writer_fails_on_same_id_with_different_content(tmp_path: Path):
    protocol = _fixture_protocol(tmp_path)
    ledger = tmp_path / "experiments.csv"
    ledger.write_text(HEADER, encoding="utf-8")
    row = build_rows(protocol, root=tmp_path)[0]
    assert append_reconciled_experiment(path=ledger, **row) is True
    changed = {**row, "code_sha256": "f" * 64}
    with pytest.raises(ValueError, match="key collision"):
        append_reconciled_experiment(path=ledger, **changed)


def test_source_hash_mismatch_fails_closed(tmp_path: Path):
    protocol_path = _fixture_protocol(tmp_path)
    protocol = yaml.safe_load(protocol_path.read_text(encoding="utf-8"))
    protocol["source_evidence"]["r1_failure"]["sha256"] = "0" * 64
    copied = tmp_path / "protocol.yaml"
    copied.write_text(yaml.safe_dump(protocol, allow_unicode=True, sort_keys=False), encoding="utf-8")
    with pytest.raises(AttemptReconciliationError, match="source identity mismatch"):
        build_rows(copied, root=tmp_path)
