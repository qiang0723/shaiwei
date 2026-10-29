"""Frozen TP-F-0B contract: pinned protocol and addendum A1, bound inputs, raw and qlib identity, output paths."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import yaml

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.trend_swing.contract import sha256_file
from shaiwei.research.trend_swing.recovery_store import CORE_SOURCES
from shaiwei.research.trend_swing.sources import source_paths
from shaiwei.transform.qlib_bin import qlib_tree_integrity


class TPFError(RuntimeError):
    """Fail-closed TP-F-0B contract violation."""


PROTOCOL_RELATIVE = "config/tp_f_0b_data_identity_preflight_v1.yaml"
PROTOCOL_SHA256 = "b5bc05f51e5701208320c96e2551e192deade69e60f6eb5fd33debcd10cee87a"
DOCUMENT_RELATIVE = "docs/TP_F_0B_DATA_IDENTITY_PREFLIGHT_PROTOCOL_20261027.md"
DOCUMENT_SHA256 = "a3ebc0c9cf44871b4b7ecc770896c57f4b9e150e95bc7f58aa1f0afca577caec"
ADDENDUM_RELATIVE = "config/tp_f_0b_data_identity_preflight_addendum_a1.yaml"
ADDENDUM_SHA256 = "00457fd99f55fd3ae6fd31152867f7e87684ecd63676fbe725878344e81af80b"
ADDENDUM_DOCUMENT_RELATIVE = "docs/TP_F_0B_DATA_IDENTITY_PREFLIGHT_ADDENDUM_A1_20261029.md"
ADDENDUM_DOCUMENT_SHA256 = "561e4170836ef3e4435f8fcb5bd96c86add117a275120c8d48364b60ec16b723"
A1_BASIS = "member_days_not_confirmed_suspended_by_rf_0c_two_layer_rule"
OUTPUT_ROOT = PROJECT_ROOT / "data/research/tp-f/tp-f-0b-data-identity-preflight-v1"
AUDIT_ROOT = PROJECT_ROOT / "data/research/tp-f/tp-f-0b-audit"
CONTROL_ROOT = PROJECT_ROOT / "data/control/tp-f-0b"


def _pinned(root: Path, relative: str, expected: str, label: str) -> Path:
    path = root / relative
    if path.is_symlink() or not path.is_file() or sha256_file(path) != expected:
        raise TPFError(f"TP-F-0B {label} differs from its frozen identity: {relative}")
    return path


def _mapping(path: Path, label: str) -> dict[str, Any]:
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise TPFError(f"TP-F-0B {label} YAML is invalid") from exc
    if not isinstance(document, dict):
        raise TPFError(f"TP-F-0B {label} YAML is not a mapping")
    return document


def _check_protocol(document: Mapping[str, Any]) -> None:
    objective, execution = document.get("objective", {}), document.get("execution_control", {})
    raw = document.get("frozen_inputs", {}).get("raw_market_store", {})
    verdicts = document.get("verdicts", {})
    required = {
        "schema": document.get("schema_version") == "tp-f-0b-data-identity-preflight-v1",
        "status": document.get("status") == "RESULT_BLIND_DATA_AND_IDENTITY_PREFLIGHT_FROZEN_BEFORE_IMPLEMENTATION",
        "production": document.get("production_authorization") == "none",
        "no candidates": objective.get("candidate_generation") is False,
        "no effect": objective.get("strategy_effect_evaluation") is False,
        "grammar frozen": document.get("candidate_grammar", {}).get("grammar_change_authorized") is False,
        "raw immutable": raw.get("raw_data_mutation_authorized") is False and raw.get("network_requests_authorized") is False,
        "no BSE": document.get("frozen_inputs", {}).get("bse_allowed") is False,
        "thresholds frozen": document.get("gates", {}).get("threshold_change_after_profile") == "forbidden",
        "exact registry": document.get("identity_registry", {}).get("sealed_base", {}).get("reproduction_rule")
        == "exact_byte_equality_required",
        "synthetic fixtures": document.get("adversarial_fixtures", {}).get("fixtures_are_synthetic_only") is True,
        "fixture first": execution.get("fixtures_must_pass_before_real_profile") is True,
        "offline": execution.get("external_network_or_provider") is False and execution.get("docker_network_mode") == "none",
        "no secrets": execution.get("env_or_secret_read") is False,
        "no llm": execution.get("deepseek_or_any_llm_call") is False,
        "no model": execution.get("model_training_prediction_or_backtest") is False,
        "no production": execution.get("paper_web_scheduler_or_production_change") is False,
        "single scope": execution.get("same_scope_rerun") == "forbidden",
        "approval": execution.get("exact_scope_and_verbatim_user_approval_before_real_profile") is True,
        "effect": verdicts.get("strategy_effective") == "NOT_EVALUATED" and verdicts.get("production_authorization") == "none",
    }
    if failed := [name for name, ok in required.items() if not ok]:
        raise TPFError(f"TP-F-0B protocol authority or contract differs: {failed}")


def _check_addendum(addendum: Mapping[str, Any], gates: Mapping[str, Any]) -> None:
    parent, change = addendum.get("parent_protocol", {}), addendum.get("single_change", {})
    unchanged = change.get("thresholds_unchanged", {})
    required = (
        addendum.get("schema_version") == "tp-f-0b-data-identity-preflight-addendum-a1-v1",
        addendum.get("production_authorization") == "none",
        parent.get("sha256") == PROTOCOL_SHA256 and parent.get("document_sha256") == DOCUMENT_SHA256,
        parent.get("original_text_preserved") is True,
        change.get("new_basis") == A1_BASIS,
        change.get("no_bar_unexplained_days_stay_in_denominator") is True,
        change.get("other_gates_period_signature_and_verdict_rules_unchanged") is True,
        set(change.get("gates_affected", ())) == {"raw_open_coverage_minimum", "raw_prev_close_join_minimum"},
        all(gates.get(name) == value for name, value in unchanged.items()) and len(unchanged) == 2,
        addendum.get("result_blind", {}).get("change_after_real_profile") == "forbidden",
    )
    if not all(required):
        raise TPFError("TP-F-0B addendum A1 authority or contract differs")


@dataclass(frozen=True)
class TPFScope:
    document: dict[str, Any]
    addendum: dict[str, Any]
    sha256: str = PROTOCOL_SHA256
    addendum_sha256: str = ADDENDUM_SHA256

    @classmethod
    def load(cls, root: Path = PROJECT_ROOT) -> "TPFScope":
        document = _mapping(_pinned(root, PROTOCOL_RELATIVE, PROTOCOL_SHA256, "protocol"), "protocol")
        addendum = _mapping(_pinned(root, ADDENDUM_RELATIVE, ADDENDUM_SHA256, "addendum A1"), "addendum A1")
        _pinned(root, DOCUMENT_RELATIVE, DOCUMENT_SHA256, "protocol document")
        _pinned(root, ADDENDUM_DOCUMENT_RELATIVE, ADDENDUM_DOCUMENT_SHA256, "addendum A1 document")
        _check_protocol(document)
        _check_addendum(addendum, document["gates"])
        return cls(document, addendum)

    @property
    def manifest_relative(self) -> str:
        return self.document["frozen_inputs"]["raw_market_store"]["manifest"]["path"]

    @property
    def qlib_root_relative(self) -> str:
        return Path(self.document["frozen_inputs"]["qlib_cache"]["manifest"]["path"]).parent.as_posix()


def bound_inputs(scope: TPFScope) -> dict[str, str]:
    """Every hash-bound input file (relative path -> frozen sha256)."""
    frozen = scope.document["frozen_inputs"]
    checks = {
        frozen["raw_market_store"]["manifest"]["path"]: frozen["raw_market_store"]["manifest"]["sha256"],
        frozen["qlib_cache"]["manifest"]["path"]: frozen["qlib_cache"]["manifest"]["sha256"],
        scope.document["candidate_grammar"]["source"]: scope.document["candidate_grammar"]["source_sha256"],
        scope.document["identity_registry"]["sealed_base"]["path"]: scope.document["identity_registry"]["sealed_base"]["sha256"],
    }
    machine = scope.document["authority_chain"]["machine_reused"]
    checks[machine["protocol"]] = machine["protocol_sha256"]
    for row in frozen["identity_ledgers"].values():
        checks[row["path"]] = row["sha256"]
    return dict(sorted(checks.items()))


def validate_bound_inputs(scope: TPFScope, root: Path = PROJECT_ROOT) -> dict[str, str]:
    checks = bound_inputs(scope)
    for relative, expected in checks.items():
        _pinned(root, relative, expected, "bound input")
    return checks


def validate_raw_artifacts(manifest: Mapping[str, Any], required: list[str], root: Path = PROJECT_ROOT) -> str:
    """Re-hash every immutable raw artifact the panel reads; returns one bundle digest over (source, path, sha)."""
    missing = sorted(set(required) - set(CORE_SOURCES))
    if missing:
        raise TPFError(f"TP-F-0B required layers are outside the reused store: {missing}")
    digest = hashlib.sha256()
    for source in CORE_SOURCES:
        records = manifest.get("sources", {}).get(source, {}).get("artifacts", [])
        paths = source_paths(manifest, source, root)
        if not records or len(paths) != len(records):
            raise TPFError(f"TP-F-0B raw layer has no immutable artifacts: {source}")
        for record, path in zip(records, paths, strict=True):
            actual = sha256_file(Path(path))
            if actual != record["content_sha256"]:
                raise TPFError(f"TP-F-0B raw artifact differs from its manifest: {record['path']}")
            digest.update(f"{source}\0{record['path']}\0{actual}\n".encode())
    return digest.hexdigest()


def validate_qlib_cache(scope: TPFScope, root: Path = PROJECT_ROOT) -> dict[str, Any]:
    frozen = scope.document["frozen_inputs"]["qlib_cache"]
    qlib_root = root / scope.qlib_root_relative
    manifest = json.loads((root / frozen["manifest"]["path"]).read_text(encoding="utf-8"))
    integrity = qlib_tree_integrity(qlib_root)
    if manifest.get("artifact_sha256") != frozen["artifact_sha256"] or integrity["artifact_sha256"] != frozen["artifact_sha256"]:
        raise TPFError("TP-F-0B qlib cache differs from its frozen artifact identity")
    calendar = (qlib_root / "calendars/day.txt").read_text(encoding="utf-8").split()
    expected = frozen["calendar"]
    if not calendar or (calendar[0], calendar[-1], len(calendar)) != (expected["first"], expected["last"], expected["days"]):
        raise TPFError("TP-F-0B qlib calendar differs from the frozen calendar")
    return {"artifact_sha256": integrity["artifact_sha256"], "calendar_days": len(calendar)}
