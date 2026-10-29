"""Frozen TP-F-1 contract: pinned protocol and addendum A1, bound inputs, and the R2-1R1 latch gate."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Mapping

import yaml

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.trend_swing.contract import sha256_file


class TPF1Error(RuntimeError):
    """Fail-closed TP-F-1 contract violation."""


PROTOCOL_RELATIVE = "config/tp_f_1_formal_small_batch_v1.yaml"
PROTOCOL_SHA256 = "ec38b15a679a144cb74be565fbfe53de8ba355e36e6289519d8944d89d46a809"
DOCUMENT_RELATIVE = "docs/TP_F_1_FORMAL_SMALL_BATCH_PROTOCOL_20261029.md"
DOCUMENT_SHA256 = "a91e72547831e31890f5af0073a5b3b32111c9ab2502fe7558573d7710afa34f"
ADDENDUM_RELATIVE = "config/tp_f_1_formal_small_batch_addendum_a1.yaml"
ADDENDUM_SHA256 = "b4e742e1b1d2700e7fdbcc8a00004d1232945e48bf3086ff0e24185fe0a49d81"
ADDENDUM_DOCUMENT_RELATIVE = "docs/TP_F_1_FORMAL_SMALL_BATCH_ADDENDUM_A1_20261029.md"
ADDENDUM_DOCUMENT_SHA256 = "1945950ca1dfe6c7759a83021bac1b0a92eaf13309aa3255e9dc8a170ff44b4b"
R2_1R1_REPORT_RELATIVE = "data/research/r2-1r1/r2-1r1-continuous-segment-checkpoint-v1/report.json"
FAMILY = "tp-f-1-trend-pullback-joint-state"
FAILURE_CLASSES = (
    "EMPTY_EXPRESSION",
    "RATIONALE_MISSING_OR_PLACEHOLDER",
    "UNSAFE_AST",
    "LEAKAGE_SENTINEL",
    "TOKEN_CEILING",
    "AST_NODE_CEILING",
    "BACKTRACK_CEILING",
    "SIGNATURE_UNPARSEABLE",
    "NOT_JOINT_STATE",
    "DUPLICATE_SEALED_REGISTRY",
    "DUPLICATE_CANONICAL_IDENTITY",
    "DUPLICATE_WITHIN_BATCH",
    "RESPONSE_SCHEMA",
)


def _pinned(root: Path, relative: str, expected: str) -> Path:
    path = root / relative
    if path.is_symlink() or not path.is_file() or sha256_file(path) != expected:
        raise TPF1Error(f"TP-F-1 frozen file differs: {relative}")
    return path


def _yaml(path: Path) -> dict[str, Any]:
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise TPF1Error(f"TP-F-1 YAML is invalid: {path.name}") from exc
    if not isinstance(document, dict):
        raise TPF1Error(f"TP-F-1 YAML is not a mapping: {path.name}")
    return document


def _check(document: Mapping[str, Any], addendum: Mapping[str, Any]) -> None:
    batch, candidate = document.get("batch_contract", {}), document.get("candidate_contract", {})
    execution, verdicts = document.get("execution_control", {}), document.get("verdicts", {})
    selection = addendum.get("change_1_selection", {}).get("new_rule", {})
    review = addendum.get("change_2_semantic_blind_review", {})
    required = {
        "protocol": document.get("protocol_id") == "tp-f-1-trend-pullback-joint-state-001",
        "production": document.get("production_authorization") == "none" and verdicts.get("production_authorization") == "none",
        "model": batch.get("model") == "deepseek-v4-pro" and batch.get("model_unavailable") == "BLOCKED_no_substitution",
        "budget": (batch.get("completed_responses_maximum"), batch.get("qualified_candidates_maximum"),
                   float(batch.get("single_batch_hard_ceiling_usd", 0)), float(batch.get("total_tp_f_ceiling_usd", 0))) == (8, 3, 1.0, 2.0),
        "serial": batch.get("serial_calls_only") is True and batch.get("no_backfill_or_substitution") is True,
        "grammar": (candidate.get("maximum_window_days_per_operator"), candidate.get("maximum_required_backtrack_trade_days"),
                    candidate.get("maximum_expression_tokens"), candidate.get("maximum_ast_nodes")) == (50, 100, 20, 80),
        "rationale": candidate.get("economic_rationale_minimum_chars") == 20 and candidate.get("placeholder_rationale_forbidden") is True,
        "joint state": candidate.get("joint_state_signature_required", {}).get("rule") == "tp_f_0b_identity_registry_joint_state_signature",
        "family n": document.get("effect_stage", {}).get("family_n") == "all_completed_responses_including_failures_and_duplicates",
        "single scope": execution.get("same_scope_rerun") == "forbidden" and execution.get("implementation_before_push") == "forbidden",
        "addendum parent": addendum.get("parent_protocol", {}).get("sha256") == PROTOCOL_SHA256
        and addendum.get("parent_protocol", {}).get("document_sha256") == DOCUMENT_SHA256,
        "selection": selection.get("metric") == "absolute_mean_daily_rank_ic_of_pit_neutralized_factor"
        and selection.get("minimum_valid_daily_ic_observations") == 252
        and addendum.get("change_1_selection", {}).get("selection_uses_out_of_sample_data") is False,
        "review": review.get("executor") == "user" and review.get("ruling_record") == "verbatim_user_text_transcribed_by_tool_never_fabricated"
        and tuple(review.get("veto_reasons", ())) == ("NOT_THIS_MECHANISM", "DISGUISED_DUPLICATE"),
        "one approval": addendum.get("one_exact_scope_and_one_verbatim_approval_cover_G_R_E_A") is True,
    }
    if failed := [name for name, ok in required.items() if not ok]:
        raise TPF1Error(f"TP-F-1 protocol or addendum authority differs: {failed}")


@dataclass(frozen=True)
class TPF1Scope:
    document: dict[str, Any]
    addendum: dict[str, Any]
    sha256: str = PROTOCOL_SHA256
    addendum_sha256: str = ADDENDUM_SHA256

    @classmethod
    def load(cls, root: Path = PROJECT_ROOT) -> "TPF1Scope":
        document = _yaml(_pinned(root, PROTOCOL_RELATIVE, PROTOCOL_SHA256))
        addendum = _yaml(_pinned(root, ADDENDUM_RELATIVE, ADDENDUM_SHA256))
        _pinned(root, DOCUMENT_RELATIVE, DOCUMENT_SHA256)
        _pinned(root, ADDENDUM_DOCUMENT_RELATIVE, ADDENDUM_DOCUMENT_SHA256)
        _check(document, addendum)
        return cls(document, addendum)


def bound_inputs(scope: TPF1Scope) -> dict[str, str]:
    chain = scope.document["authority_chain"]
    checks = {chain[name]["path"]: chain[name]["sha256"]
              for name in ("tp_f_0a", "tp_f_0b_protocol", "tp_f_0b_addendum_a1", "tp_f_0b_acceptance", "shape_reference", "r2_1r1_protocol")}
    checks[chain["judge"]["spec"]] = chain["judge"]["spec_sha256"]
    contract = scope.document["candidate_contract"]
    checks[contract["grammar"]["source"]] = contract["grammar"]["sha256"]
    signature = contract["joint_state_signature_required"]["implementation"]
    checks[signature["path"]] = signature["sha256"]
    return dict(sorted(checks.items()))


def validate_bound_inputs(scope: TPF1Scope, root: Path = PROJECT_ROOT) -> dict[str, str]:
    checks = bound_inputs(scope)
    for relative, expected in checks.items():
        _pinned(root, relative, expected)
    return checks


def require_r2_1r1_latch(root: Path = PROJECT_ROOT) -> dict[str, Any]:
    """Execution gate 1: the R2-1R1 checkpoint latched and its single descriptive report exists."""
    path = root / R2_1R1_REPORT_RELATIVE
    if not path.is_file():
        raise TPF1Error("TP-F-1 execution requires the latched R2-1R1 checkpoint report; none exists")
    report = json.loads(path.read_text(encoding="utf-8"))
    segment = report.get("segment", {})
    if report.get("schema_version") != "r2-1r1-descriptive-report-v1" or not segment.get("latch_day"):
        raise TPF1Error("TP-F-1 R2-1R1 report is not a latched descriptive report")
    if segment.get("live_dual_days", 0) < 20 or segment.get("rebalance_cycles", 0) < 2:
        raise TPF1Error("TP-F-1 R2-1R1 latched segment is below the frozen gate")
    return {"report_sha256": sha256_file(path), "latch_day": segment["latch_day"]}
