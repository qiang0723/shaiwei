from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml

from shaiwei.research_gates.m5_dynamic.lineage_contract import CASE_ID, PROTOCOL_SCOPE_SHA256
from shaiwei.research_gates.m5_dynamic.statement_scope import is_frozen_annual_statement_row


ROOT = Path(__file__).parents[1]
SCOPE_PATH = ROOT / "config/m5_dynamic_fundamental_source_lineage_recovery_protocol_scope_v4.json"
BUILD_PATH = ROOT / "config/m5_dynamic_fundamental_source_lineage_build_v4.yaml"


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def test_scope_recovery_envelope_and_case_are_content_addressed() -> None:
    serialized = SCOPE_PATH.read_text(encoding="utf-8")
    document = json.loads(serialized)
    scope = document["scope"]

    assert serialized == json.dumps(document, ensure_ascii=False, indent=2) + "\n"
    assert document["protocol_scope_sha256"] == _canonical_sha256(scope)
    assert document["protocol_scope_sha256"] == PROTOCOL_SCOPE_SHA256
    proposal_id = scope["source_proposal"]["proposal_id"]
    expected_case = hashlib.sha256(
        f"m5-gate-case-v1\0{proposal_id}\0{PROTOCOL_SCOPE_SHA256}".encode()
    ).hexdigest()
    assert expected_case == CASE_ID
    assert scope["git_freeze"]["recovery_protocol_commit"] == (
        "cd13e6a0696f67248f20367e85e6cef85947b602"
    )
    assert scope["git_freeze"]["recovery_protocol_commit_pushed_before_scope_creation"] is True


def test_build_v4_binds_scope_case_and_stopped_predecessor() -> None:
    build = yaml.safe_load(BUILD_PATH.read_text(encoding="utf-8"))

    assert build["build_protocol_id"] == "m5-dynamic-fundamental-source-lineage-build-v4"
    assert build["protocol_scope_sha256"] == PROTOCOL_SCOPE_SHA256
    assert build["derived_case_id"] == CASE_ID
    assert build["registry"]["prior_stopped_case_reopen_authorized"] is False
    assert build["registry"]["new_case_id"] == CASE_ID
    assert build["construction"]["real_financial_rows_may_be_read"] is False
    assert build["authority"]["lineage_execution_authorized"] is False


def test_frozen_statement_scope_matches_r1_annual_domain() -> None:
    base = {"end_date": "20251231", "report_type": "1"}

    assert is_frozen_annual_statement_row(base) is True
    assert is_frozen_annual_statement_row({**base, "end_date": "2025-12-31"}) is True
    assert is_frozen_annual_statement_row({**base, "report_type": "5"}) is True
    assert is_frozen_annual_statement_row({**base, "end_date": "20250930"}) is False
    assert is_frozen_annual_statement_row({**base, "report_type": "2"}) is False
