"""Canonical identity registry across ledgers, G1 admissions, and the Alpha158 family."""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path
from typing import Any

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.trend_swing.contract import sha256_file
from shaiwei.research.rf_0b.contract import RFBError, RFBScope


ALLOWED_ATTEMPT_COLUMNS = frozenset({
    "attempt_id", "research_family", "topic", "canonical_expression", "expression_sha256",
    "expression_tokens", "ast_nodes", "max_lookback_days", "duplicate_of_attempt_id",
    "failure_class", "candidate_status",
})
FORBIDDEN_COLUMNS = frozenset({
    "discovery_rank_ic", "discovery_daily_ic_count", "discovery_coverage", "result_json",
    "trial_count", "valid_trial_sharpes", "admitted", "failed_gates",
})


def _read_ledger(path: Path, allowed: frozenset[str]) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        header = frozenset(reader.fieldnames or ())
        if not {"canonical_expression", "expression_sha256"} <= header:
            raise RFBError(f"RF-0B ledger identity columns are missing: {path.name}")
        rows = []
        for row in reader:
            rows.append({key: value for key, value in row.items() if key in allowed})
    return rows


def _attempt_section(path: Path, expected_sha256: str) -> dict[str, Any]:
    if sha256_file(path) != expected_sha256:
        raise RFBError(f"RF-0B attempt ledger differs: {path.name}")
    rows = _read_ledger(path, ALLOWED_ATTEMPT_COLUMNS)
    expressions = [
        (row["canonical_expression"], row["expression_sha256"])
        for row in rows
        if row.get("canonical_expression") and row.get("expression_sha256")
    ]
    for expression, digest in expressions:
        actual = hashlib.sha256(expression.encode()).hexdigest()
        if actual != digest:
            raise RFBError(f"RF-0B expression hash mismatch in {path.name}")
    hashes = sorted({digest for _, digest in expressions})
    clusters: dict[str, int] = {}
    for _, digest in expressions:
        clusters[digest] = clusters.get(digest, 0) + 1
    return {
        "attempt_rows": len(rows),
        "canonical_expression_rows": len(expressions),
        "unique_expression_hashes": len(hashes),
        "duplicate_clusters": sum(1 for count in clusters.values() if count > 1),
        "expression_hashes": hashes,
    }


def _g1_section(path: Path, expected_sha256: str) -> dict[str, Any]:
    if sha256_file(path) != expected_sha256:
        raise RFBError("RF-0B G1 admission ledger differs")
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        tokens = set()
        rows = 0
        for row in reader:
            family = (row.get("research_family") or "").strip()
            evidence = (row.get("evidence_sha256") or "").strip()
            if family and evidence:
                tokens.add(f"{family}:{evidence}")
            rows += 1
    return {
        "admission_rows": rows,
        "unique_identity_tokens": len(tokens),
        "identity_tokens": sorted(tokens),
        "outcome_fields_read": False,
    }


def _alpha158_section() -> dict[str, Any]:
    from qlib.contrib.data.loader import Alpha158DL

    fields, _ = Alpha158DL().get_feature_config()
    canonical = sorted({str(expression) for expression in fields})
    if len(canonical) != 158:
        raise RFBError("RF-0B Alpha158 family cardinality differs")
    return {
        "expression_count": len(canonical),
        "expression_hashes": sorted(
            {hashlib.sha256(expression.encode()).hexdigest() for expression in canonical}
        ),
    }


def build_identity_registry(scope: RFBScope, root: Path = PROJECT_ROOT) -> dict[str, Any]:
    frozen = scope.document["frozen_inputs"]
    sections = {
        "attempt_ledger_d1_v2": _attempt_section(
            root / frozen["attempt_ledger_d1_v2"]["path"],
            frozen["attempt_ledger_d1_v2"]["sha256"],
        ),
        "attempt_ledger_m1": _attempt_section(
            root / frozen["attempt_ledger_m1"]["path"], frozen["attempt_ledger_m1"]["sha256"]
        ),
        "attempt_ledger_m3": _attempt_section(
            root / frozen["attempt_ledger_m3"]["path"], frozen["attempt_ledger_m3"]["sha256"]
        ),
        "g1_admission_ledger": _g1_section(
            root / frozen["g1_admission_ledger"]["path"],
            frozen["g1_admission_ledger"]["sha256"],
        ),
        "alpha158_family": _alpha158_section(),
    }
    all_expression_hashes = sorted({
        digest
        for key, section in sections.items()
        if key != "g1_admission_ledger"
        for digest in section["expression_hashes"]
    })
    return {
        "schema_version": "rf-0b-identity-registry-v1",
        "protocol_sha256": scope.sha256,
        "sections": sections,
        "total_unique_expression_hashes": len(all_expression_hashes),
        "expression_hash_union": all_expression_hashes,
        "outcome_fields_read": False,
        "production_authorization": "none",
    }
