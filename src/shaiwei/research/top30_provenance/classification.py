"""Frozen evidence-only classifications for M6-3C-R3."""

from __future__ import annotations

from typing import Any


CLASSIFICATIONS = {
    "ROOT_CAUSE_IDENTIFIED",
    "PRODUCER_ENVIRONMENT_IDENTIFIED_NOT_CAUSALLY_PROVEN",
    "PROVENANCE_GAP_CONFIRMED",
    "MIXED_UNRESOLVED",
}


def classify(facts: dict[str, Any]) -> str:
    if facts.get("unique_cause_proven") is True and facts.get("competing_explanation_count") == 0:
        return "ROOT_CAUSE_IDENTIFIED"
    if facts.get("canonical_producer_identity_complete") is True and facts.get("input_identity_pass") is True:
        return "PRODUCER_ENVIRONMENT_IDENTIFIED_NOT_CAUSALLY_PROVEN"
    if facts.get("canonical_producer_identity_complete") is False:
        return "PROVENANCE_GAP_CONFIRMED"
    return "MIXED_UNRESOLVED"


__all__ = ["CLASSIFICATIONS", "classify"]
