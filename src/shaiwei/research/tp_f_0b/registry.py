"""Sealed RF-0B registry reproduction and the TP-F extension layers (identity columns only, protocol §5)."""

from __future__ import annotations

from collections import Counter
import csv
import hashlib
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.rf_0b.contract import RFBScope
from shaiwei.research.rf_0b.registry import build_identity_registry
from shaiwei.research.tp_f_0b.contract import TPFError, TPFScope
from shaiwei.research.tp_f_0b.signature import SignatureRule, census, signature
from shaiwei.research.trend_swing.contract import sha256_file
from shaiwei.research.trend_swing.v6.engine import canonical_json


TS_V5_LEDGERS = ("ts_v5", "ts_v5_r2", "ts_v5_r3c", "ts_v5_r3f")
ATTEMPT_LEDGERS = ("d1_v2", "m1", "m3")


def reproduce_sealed_registry(scope: TPFScope, root: Path = PROJECT_ROOT) -> dict[str, Any]:
    """Rebuild with the original RF-0B rule and protocol; the canonical bytes must hash to the sealed file."""
    sealed = scope.document["identity_registry"]["sealed_base"]
    registry = build_identity_registry(RFBScope.load(), root)
    if hashlib.sha256(canonical_json(registry) + b"\n").hexdigest() != sealed["sha256"]:
        raise TPFError("TP-F-0B identity registry does not reproduce the sealed RF-0B registry byte for byte")
    if sha256_file(root / sealed["path"]) != sealed["sha256"]:
        raise TPFError("TP-F-0B sealed RF-0B registry file differs")
    return registry


def read_allowed(path: Path, allowed: Iterable[str]) -> list[dict[str, str]]:
    """Read a ledger keeping only allowed identity columns; effect columns are dropped on read."""
    keep = set(allowed)
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if not keep <= set(reader.fieldnames or ()):
            raise TPFError(f"TP-F-0B ledger lacks allowed identity columns: {path.name}")
        return [{key: row[key] for key in keep} for row in reader]


def _ledger(scope: TPFScope, name: str, kind: str, root: Path) -> list[dict[str, str]]:
    frozen = scope.document["frozen_inputs"]
    row = frozen["identity_ledgers"][name]
    path = root / row["path"]
    if sha256_file(path) != row["sha256"]:
        raise TPFError(f"TP-F-0B identity ledger differs: {row['path']}")
    allowed = frozen["ledger_columns_allowed"][kind]
    if set(allowed) & set(frozen["ledger_columns_forbidden"]):
        raise TPFError("TP-F-0B allowed and forbidden ledger columns overlap")
    return read_allowed(path, allowed)


def ts_v5_layer(scope: TPFScope, root: Path = PROJECT_ROOT) -> dict[str, Any]:
    rows = [row for name in TS_V5_LEDGERS for row in _ledger(scope, name, "ts_v5", root)]
    expected = scope.document["identity_registry"]["extension_layers"]["ts_v5_semantic_layer"]["attempts"]
    if len(rows) != expected:
        raise TPFError(f"TP-F-0B TS v5 semantic layer has {len(rows)} attempts, frozen {expected}")
    return semantic_layer(rows)


def semantic_layer(rows: list[Mapping[str, str]]) -> dict[str, Any]:
    """Same-belief layer: empty signatures (unparsed attempts) are counted but carry no identity."""
    signatures = Counter(row["semantic_signature"] for row in rows if row["semantic_signature"])
    fingerprints = {row["candidate_fingerprint"] for row in rows if row["candidate_fingerprint"]}
    return {
        "attempts": len(rows),
        "with_candidate_fingerprint": sum(bool(row["candidate_fingerprint"]) for row in rows),
        "unique_candidate_fingerprints": len(fingerprints),
        "unique_semantic_signatures": len(signatures),
        "semantic_signature_collisions": sum(count - 1 for count in signatures.values() if count > 1),
        "semantic_signature_hashes": sorted(signatures),
    }


def g1_v2_layer(scope: TPFScope, root: Path = PROJECT_ROOT) -> dict[str, Any]:
    v1 = _ledger(scope, "g1_v1_admissions", "admissions", root)
    v2 = _ledger(scope, "g1_v2_admissions", "admissions", root)
    new_families = sorted({row["research_family"] for row in v2} - {row["research_family"] for row in v1})
    if new_families:
        raise TPFError(f"TP-F-0B g1-v2 re-judge introduced research families outside G1: {new_families}")
    return {"v2_rows": len(v2), "new_research_families": 0, "new_identity": 0}


def public_factor_layer(scope: TPFScope, rule: SignatureRule) -> dict[str, Any]:
    from shaiwei.research.g1_calibration.controls import ROUTE_EXPRESSIONS

    routes = scope.document["identity_registry"]["extension_layers"]["public_factor_references"]["routes"]
    items = {}
    for route in sorted(routes):
        item = signature(ROUTE_EXPRESSIONS[route], rule)
        items[route] = {
            "mechanism": routes[route],
            "canonical_sha256": item.canonical_sha256,
            "trend_components": item.trend_components,
            "pullback_components": item.pullback_components,
            "joint_state": item.joint_state,
        }
    return items


def alpha158_expressions() -> list[str]:
    from qlib.contrib.data.loader import Alpha158DL

    fields, _ = Alpha158DL().get_feature_config()
    expressions = sorted({str(expression) for expression in fields})
    if len(expressions) != 158:
        raise TPFError("TP-F-0B Alpha158 family cardinality differs")
    return expressions


def joint_state_census(scope: TPFScope, rule: SignatureRule, alpha158: list[str], root: Path = PROJECT_ROOT) -> dict[str, Any]:
    sources: dict[str, Any] = {"alpha158": census(alpha158, rule, fail_closed=True)}
    for name in ATTEMPT_LEDGERS:
        rows = _ledger(scope, name, "factor_attempts", root)
        sources[f"attempt_ledger_{name}"] = census(
            (row["canonical_expression"] for row in rows if row["canonical_expression"]), rule, fail_closed=False
        )
    sources["g1_admissions"] = "not_expression_bearing_identity_tokens_only"
    sources["ts_v5"] = "not_expression_bearing_semantic_signatures_only"
    return sources


def build_extension_registry(
    scope: TPFScope,
    *,
    alpha158: Callable[[], list[str]] = alpha158_expressions,
    root: Path = PROJECT_ROOT,
) -> dict[str, Any]:
    sealed = reproduce_sealed_registry(scope, root)
    rule = SignatureRule.from_protocol(scope.document["identity_registry"]["joint_state_signature"])
    joint = joint_state_census(scope, rule, alpha158(), root)
    return {
        "schema_version": "tp-f-0b-identity-registry-extension-v1",
        "protocol_sha256": scope.sha256,
        "sealed_base": {
            "sha256": scope.document["identity_registry"]["sealed_base"]["sha256"],
            "reproduced_byte_for_byte": True,
            "total_unique_expression_hashes": sealed["total_unique_expression_hashes"],
        },
        "extension_layers": {
            "public_factor_references": public_factor_layer(scope, rule),
            "ts_v5_semantic_layer": ts_v5_layer(scope, root),
            "g1_v2_rejudge": g1_v2_layer(scope, root),
        },
        "joint_state_census": joint,
        "outcome_fields_read": False,
        "production_authorization": "none",
    }


def identity_verdict(registry: Mapping[str, Any]) -> str:
    return "REJECT_DUPLICATE" if registry["joint_state_census"]["alpha158"]["joint_state"] >= 1 else "IDENTITY_SPACE_OPEN"
