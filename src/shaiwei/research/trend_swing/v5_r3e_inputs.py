"""Frozen identity and legacy-response readers for TS-v5-R3E."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from shaiwei.research.provider_contract import D1ControlError
from shaiwei.research.trend_swing.v5_contract import sha256_file


def verify_frozen_inputs(scope: dict[str, Any], root: Path) -> list[dict[str, str]]:
    frozen = scope["frozen_inputs"]
    files = {
        "config/ts_v5_r3c_llm_canary_scope_v1.yaml": frozen["r3c_scope_sha256"],
        "ledger/ts_v5_r3c_llm_attempts.csv": frozen["r3c_attempt_ledger_sha256"],
        "ledger/ts_v5_r3c_llm_transports.csv": frozen["r3c_transport_ledger_sha256"],
        "docs/TS_V5_R3C_LLM_CANARY_ACCEPTANCE_20260813.md": frozen["r3c_acceptance_sha256"],
        "config/ts_v5_r3d_offline_proposal_diagnostic_v1.yaml": frozen["r3d_scope_sha256"],
        "data/research/trend_swing/ts-v5-r3d-offline-proposal-diagnostic/diagnostic.json": frozen[
            "r3d_report_sha256"
        ],
        "data/research/trend_swing/ts-v5-r3d-offline-proposal-diagnostic/audit.json": frozen[
            "r3d_audit_sha256"
        ],
        "docs/TS_V5_R3D_OFFLINE_PROPOSAL_DIAGNOSTIC_ACCEPTANCE_20260813.md": frozen[
            "r3d_acceptance_sha256"
        ],
        "config/ts_v5_mechanism_proposal_v2.yaml": frozen["legacy_proposal_contract_sha256"],
        "src/shaiwei/research/trend_swing/v5_proposal_contract.py": frozen[
            "legacy_proposal_compiler_sha256"
        ],
        "src/shaiwei/research/trend_swing/v5_models.py": frozen["candidate_validator_sha256"],
        "config/ts_v5_mechanism_proposal_v3.yaml": frozen["bound_proposal_contract_sha256"],
    }
    for relative, expected in files.items():
        if sha256_file(root / relative) != expected:
            raise D1ControlError(f"TS-v5-R3E frozen input differs: {relative}")
    ledger_path = root / "ledger/ts_v5_r3c_llm_attempts.csv"
    with ledger_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if (
        len(rows) != 6
        or [int(row["ordinal"]) for row in rows] != list(range(1, 7))
        or any(row["mode"] != "INDEPENDENT" for row in rows)
        or any(row["failure_class"] != "PROPOSAL_SCHEMA_OR_COMPILER_INVALID" for row in rows)
    ):
        raise D1ControlError("TS-v5-R3E legacy attempt identity differs")
    return rows


def load_legacy_documents(
    scope: dict[str, Any], root: Path
) -> list[tuple[dict[str, str], dict[str, Any]]]:
    rows = verify_frozen_inputs(scope, root)
    documents = []
    for row in rows:
        path = root / row["raw_artifact_path"]
        if sha256_file(path) != row["raw_artifact_sha256"]:
            raise D1ControlError("TS-v5-R3E legacy raw response identity differs")
        try:
            envelope = json.loads(path.read_text(encoding="utf-8"))
            document = json.loads(envelope["content"])
        except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
            raise D1ControlError("TS-v5-R3E legacy content is invalid") from exc
        if not isinstance(document, dict):
            raise D1ControlError("TS-v5-R3E legacy content is not an object")
        documents.append((row, document))
    return documents
