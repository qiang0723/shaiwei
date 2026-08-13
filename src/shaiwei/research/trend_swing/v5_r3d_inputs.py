"""Frozen input and request-authority verification for TS-v5-R3D."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import yaml

from shaiwei.research.provider_contract import D1ControlError
from shaiwei.research.trend_swing.v5_contract import sha256_file


def _request_authority_contract(
    rows: list[dict[str, str]], root: Path
) -> dict[str, Any]:
    schema_modes, assigned_modes = [], []
    request_root = root / "data/research/trend_swing/ts-v5-r3c-canary-001/artifacts/requests"
    for row in rows:
        path = request_root / f"{row['attempt_id']}-{row['request_sha256'][:12]}.json"
        request = json.loads(path.read_text(encoding="utf-8"))
        task = json.loads(request["messages"][1]["content"])
        schema_modes.append(
            task["proposal_schema"]["$defs"]["CandidateLineage"]["properties"]["mode"]["enum"]
        )
        assigned_modes.append(task.get("assigned_attempt_mode"))
    return {
        "approved_scope_independent_slots": 6,
        "attempt_ledger_mode_independent_count": sum(row["mode"] == "INDEPENDENT" for row in rows),
        "request_schema_allows_both_lineage_modes_count": sum(
            set(modes) == {"INDEPENDENT", "ADVERSARIAL_REVISION"} for modes in schema_modes
        ),
        "request_assigned_attempt_mode_count": sum(mode is not None for mode in assigned_modes),
        "approved_mode_bound_in_request": all(mode == "INDEPENDENT" for mode in assigned_modes),
    }


def verify_inputs(
    scope_document: dict[str, Any], root: Path
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    frozen = scope_document["frozen_inputs"]
    files = {
        "config/ts_v5_r3b_contract_projection_engineering_v1.yaml": frozen["r3b_scope_sha256"],
        "docs/TS_V5_R3B_CONTRACT_PROJECTION_ENGINEERING_ACCEPTANCE_20260813.md": frozen["r3b_acceptance_sha256"],
        "config/ts_v5_mechanism_proposal_v2.yaml": frozen["proposal_contract_sha256"],
        "src/shaiwei/research/trend_swing/v5_proposal_contract.py": frozen["proposal_compiler_sha256"],
        "src/shaiwei/research/trend_swing/v5_models.py": frozen["candidate_validator_sha256"],
        "config/ts_v5_r3c_llm_canary_scope_v1.yaml": frozen["r3c_scope_sha256"],
        "config/ts_v5_r3c_llm_execution_release_v1.yaml": frozen["r3c_release_sha256"],
        "ledger/ts_v5_r3c_llm_attempts.csv": frozen["r3c_attempt_ledger_sha256"],
        "ledger/ts_v5_r3c_llm_transports.csv": frozen["r3c_transport_ledger_sha256"],
        "data/research/trend_swing/ts-v5-r3c-canary-001/ts_v5_r3c_report.json": frozen["r3c_report_sha256"],
        "data/research/trend_swing/ts-v5-r3c-canary-001/ts_v5_r3c_audit.json": frozen["r3c_audit_sha256"],
        "docs/TS_V5_R3C_LLM_CANARY_ACCEPTANCE_20260813.md": frozen["r3c_acceptance_sha256"],
    }
    for relative, expected in files.items():
        if sha256_file(root / relative) != expected:
            raise D1ControlError(f"TS-v5-R3D frozen input differs: {relative}")
    with (root / "ledger/ts_v5_r3c_llm_attempts.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if (
        len(rows) != 6
        or [row["request_sha256"] for row in rows] != frozen["request_sha256"]
        or [row["raw_artifact_sha256"] for row in rows] != frozen["raw_envelope_sha256"]
        or [row["manifest_sha256"] for row in rows] != frozen["manifest_sha256"]
        or any(row["failure_class"] != "PROPOSAL_SCHEMA_OR_COMPILER_INVALID" for row in rows)
    ):
        raise D1ControlError("TS-v5-R3D attempt identity differs")
    r3c_scope = yaml.safe_load(
        (root / "config/ts_v5_r3c_llm_canary_scope_v1.yaml").read_text(encoding="utf-8")
    )
    if r3c_scope["attempt_contract"]["independent_slots"] != 6:
        raise D1ControlError("TS-v5-R3D approved slot mode differs")
    authority_contract = _request_authority_contract(rows, root)
    if (
        authority_contract["attempt_ledger_mode_independent_count"] != 6
        or authority_contract["request_schema_allows_both_lineage_modes_count"] != 6
        or authority_contract["request_assigned_attempt_mode_count"] != 0
    ):
        raise D1ControlError("TS-v5-R3D request authority evidence differs")
    return rows, authority_contract
