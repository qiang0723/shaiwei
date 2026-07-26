import hashlib
from pathlib import Path

import yaml

from shaiwei.evaluation.g8 import comparator_codes
from shaiwei.ingest.g8_fund_evidence import G8CaptureProtocol
from shaiwei.ledger import sha256_file


RECOVERY_PATH = Path("config/g8_fund_primary_capture_recovery_v1.yaml")
ORIGINAL_PATH = Path("config/g8_fund_primary_capture_v1.yaml")
LEDGER_PATH = Path("ledger/g8_fund_evidence.csv")


def _recovery() -> dict:
    return yaml.safe_load(RECOVERY_PATH.read_text(encoding="utf-8"))


def test_g8_recovery_binds_failed_attempt_without_rewriting_it() -> None:
    protocol = _recovery()
    binding = protocol["recovery_binding"]

    assert protocol["status"] == "RESULT_BEFORE_EXECUTION_FROZEN"
    assert binding["original_protocol_sha256"] == sha256_file(ORIGINAL_PATH)
    ledger_lines = LEDGER_PATH.read_bytes().splitlines(keepends=True)
    frozen_failure_prefix = b"".join(ledger_lines[:2])
    assert binding["failure_ledger_sha256"] == hashlib.sha256(frozen_failure_prefix).hexdigest()
    assert binding["failure_http_statuses"] == [502, 502]
    assert binding["failure_bodies_empty"] is True
    assert binding["original_failed_evidence_remains_immutable"] is True
    assert binding["original_attempt_counts_for_recovery_acceptance"] is False
    assert binding["attempted_image_claimed_git_head_matches_repository"] is False


def test_g8_recovery_changes_only_execution_environment_and_remains_not_ready() -> None:
    recovery = _recovery()
    source = recovery["source"]
    scope = recovery["scope"]
    acceptance = recovery["acceptance"]

    assert source["execution_environment"] == "host_one_shot_no_env_file"
    assert source["trust_environment_proxy"] is False
    assert source["automatic_retries"] == 0
    assert source["post_capture_independent_verifier"] == "immutable_docker_image_offline"
    assert recovery["recovery_binding"]["changed_variable_only"] == "execution_environment"
    assert tuple(product["code"] for product in recovery["products"]) == comparator_codes()
    assert scope["strategy_results_access"] is False
    assert scope["g8_evaluation"] is False
    assert scope["scheduler_integration"] is False
    assert acceptance["ledger_rows"] == 54
    assert acceptance["original_failed_rows_preserved"] == 1
    assert acceptance["g8_status_after_capture"] == "NOT_READY"

    loaded = G8CaptureProtocol.load(RECOVERY_PATH)
    assert loaded.protocol_id == "g8-fund-primary-capture-recovery-v1"
    assert loaded.operator == "host-g8-evidence-recovery"
