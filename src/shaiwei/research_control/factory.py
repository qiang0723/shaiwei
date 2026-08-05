"""Canonical proposal construction from frozen server-side authority."""

from __future__ import annotations

from typing import Any

from .authority import AuthorityBundle, FamilyRule
from .models import ProposalCreate


class RequestBindingError(ValueError):
    """A strict request does not match the current frozen authority."""


def validate_request_binding(authority: AuthorityBundle, request: ProposalCreate) -> None:
    selected = set(request.universe_ids)
    if selected & set(authority.blocked_universe_ids) or not selected <= set(authority.eligible_universe_ids):
        raise RequestBindingError("selected universe is not eligible")
    family = authority.families.get(request.family_id)
    if family is None:
        raise RequestBindingError("unknown research family")
    if request.hypothesis_id != family.hypothesis_id:
        raise RequestBindingError("hypothesis does not match family")
    if request.falsification_rule_id != family.falsification_rule_id:
        raise RequestBindingError("falsification rule does not match family")
    if request.generation_mode not in family.allowed_generation_modes:
        raise RequestBindingError("generation mode is not allowed for family")
    if request.authority != authority.fixed_authority:
        raise RequestBindingError("authority fields differ from frozen values")


def _multiplicity(family: FamilyRule, planned_attempts: int) -> dict[str, Any]:
    primary = family.primary
    sensitivity = family.sensitivity
    return {
        "primary": {
            "scope_id": primary.scope_id,
            "prior_attempt_count": primary.prior_attempt_count,
            "evidence_path": primary.evidence_path,
            "evidence_sha256": primary.evidence_sha256,
            "primary_planned_after": primary.prior_attempt_count + planned_attempts,
        },
        "sensitivity": None
        if sensitivity is None
        else {
            "scope_id": sensitivity.scope_id,
            "prior_attempt_count": sensitivity.prior_attempt_count,
            "evidence_path": sensitivity.evidence_path,
            "evidence_sha256": sensitivity.evidence_sha256,
            "sensitivity_planned_after": sensitivity.prior_attempt_count + planned_attempts,
        },
        "planned_increment_policy": family.planned_increment_policy,
        "actual_research_attempt_increment": 0,
    }


def build_canonical_proposal(
    authority: AuthorityBundle,
    proposal_id: str,
    actor: str,
    request: ProposalCreate,
    request_sha: str,
    created_at: str,
    expires_at: str,
) -> dict[str, Any]:
    """Derive all non-user fields; none can be supplied or reset by clients."""
    family = authority.families[request.family_id]
    template = authority.proposal_template
    transfer = [item for item in request.universe_ids if item != request.home_universe_id]
    return {
        "schema_version": "m5-research-proposal-v1",
        "proposal_id": proposal_id,
        "created_by_actor_sha256": actor,
        "proposal_request_sha256": request_sha,
        "created_at": created_at,
        "expires_at": expires_at,
        "source_identity": {
            "config_sha256": authority.config_sha256,
            "authority_bundle_sha256": authority.authority_bundle_sha256,
            "strategy_factory_snapshot_id": authority.snapshot_id,
            "strategy_factory_snapshot_sha256": authority.snapshot_sha256,
        },
        "request": request.model_dump(mode="json"),
        "derived": {
            "research_stage": template["research_stage"],
            "evaluation_level": template["evaluation_level"],
            "home_universe_id": request.home_universe_id,
            "transfer_universe_ids": transfer,
            "universe_count": len(request.universe_ids),
            "evaluation_unit_cap": request.candidate_cap * len(request.universe_ids),
            "planned_generation_attempt_count": request.generation_attempt_cap,
            "multiplicity_context": _multiplicity(family, request.generation_attempt_cap),
            "factor_definition_state": template["factor_definition_state"],
            "model_identity": template["model_identity"],
            "portfolio_identity": template["portfolio_identity"],
            "stop_on_terminal": template["stop_on_terminal"],
            "no_budget_carryover": template["no_budget_carryover"],
        },
        "authority": request.authority.model_dump(mode="json"),
    }
