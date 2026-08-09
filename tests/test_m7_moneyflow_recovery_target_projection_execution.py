from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from shaiwei.research_gates.m7_moneyflow.contract import canonical_json


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "config/m7_moneyflow_recovery_target_projection_execution_manifest_v1.json"
MANIFEST_PHYSICAL_SHA256 = "7abf0889a9dd94364f68df08bb99d9e090e0f5b982000e604fbca50fc686ed5d"
CODE_RE = re.compile(r"[0-9]{6}\.(?:SH|SZ|BJ)")


def _load() -> dict[str, object]:
    serialized = MANIFEST.read_text(encoding="utf-8")
    document = json.loads(serialized)
    assert serialized == canonical_json(document) + "\n"
    return document


def test_execution_manifest_identity_and_authority_are_narrow() -> None:
    document = _load()
    assert hashlib.sha256(MANIFEST.read_bytes()).hexdigest() == MANIFEST_PHYSICAL_SHA256
    assert document["schema_version"] == (
        "m7-moneyflow-recovery-target-projection-execution-manifest-v1"
    )
    assert document["release_scope_sha256"] == (
        "9aca04576362455af66c5426bd0b4b6211d7edecc8b141de5ecee96ae5781614"
    )
    assert document["verdict"] == "GO_M7_RECOVERY_TARGET_PROJECTION_ONLY"
    authority = document["authority"]
    assert authority == {
        "adjusted_coverage_computed": False,
        "candidate_effect_model_backtest_run": False,
        "external_network_used": False,
        "moneyflow_numeric_value_columns_read": 0,
        "production_authorization": "none",
        "provider_call_count": 0,
        "research_attempt_increment": 0,
    }


def test_execution_manifest_proves_exact_projection_and_independent_audit() -> None:
    document = _load()
    projection = document["projection"]
    assert projection["track_a"]["member_rows"] == 908
    assert projection["track_b"]["member_rows"] == 541
    assert projection["track_a"]["unique_source_keys"] == 527
    assert projection["track_b"]["unique_source_keys"] == 541
    for track in ("track_a", "track_b"):
        assert projection[track]["intended_grain_duplicates"] == 0
        assert projection[track]["full_row_duplicates"] == 0
        assert projection[track]["bse_rows"] == 0
        assert projection[track]["pit_order_violations"] == 0
    assert projection["track_cross_intended_grain_overlap"] == 0
    assert projection["internal_replay_status"] == "PASS"
    audit = document["independent_audit"]
    assert audit["status"] == "PASS"
    assert audit["main_and_independent_targets_exact_match"] is True
    assert audit["independent_logical_content_sha256"] == {
        "track_a": projection["track_a"]["logical_content_sha256"],
        "track_b": projection["track_b"]["logical_content_sha256"],
    }


def test_execution_manifest_records_non_reentrant_live_boundary() -> None:
    idempotency = _load()["idempotency"]
    assert idempotency["projector_claim_present"] is True
    assert idempotency["auditor_claim_present"] is True
    assert idempotency["claim_before_semantic_loader"] is True
    assert idempotency["same_role_retry_authorized"] is False
    assert idempotency["same_scope_rerun_forbidden_by_user"] is True
    assert idempotency["live_second_invocation_performed"] is False
    assert idempotency["synthetic_same_image_second_invocation_stopped_before_loader"] is True


def test_execution_manifest_is_aggregate_only_and_desensitized() -> None:
    serialized = MANIFEST.read_text(encoding="utf-8")
    document = _load()
    assert document["security_codes_in_manifest"] is False
    assert CODE_RE.search(serialized) is None
    assert "sk-" not in serialized
    assert "/Users/" not in serialized
    assert "open.feishu.cn" not in serialized
