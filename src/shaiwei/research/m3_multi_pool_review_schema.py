"""Strict provider-response schema for M3-3 cross-pool adversarial reviews."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


M3_REVIEW_ROLES = (
    "construct_and_units",
    "economic_direction_and_cross_pool_coherence",
    "pit_and_numerical_stability",
    "redundancy_and_falsifiability",
)


class M3ReviewFinding(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    severity: Literal["critical", "major", "minor"]
    category: str = Field(min_length=3, max_length=80)
    statement: str = Field(min_length=20, max_length=1000)
    falsification_or_resolution: str = Field(min_length=20, max_length=1000)


class M3ReviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: Literal["m3-adversarial-review-response-v1"]
    candidate_id: str = Field(pattern=r"^[0-9a-f]{16}$")
    role: Literal[
        "construct_and_units",
        "economic_direction_and_cross_pool_coherence",
        "pit_and_numerical_stability",
        "redundancy_and_falsifiability",
    ]
    role_verdict: Literal["NO_BLOCKER_FOUND", "BLOCKER_FOUND"]
    summary: str = Field(min_length=40, max_length=1500)
    findings: list[M3ReviewFinding] = Field(max_length=6)
    formula_change_or_new_candidate_proposed: Literal[False]
    performance_claim_made: Literal[False]

    @model_validator(mode="after")
    def verdict_matches_findings(self) -> "M3ReviewResponse":
        blocking = any(item.severity in {"critical", "major"} for item in self.findings)
        if blocking != (self.role_verdict == "BLOCKER_FOUND"):
            raise ValueError("M3-3 role verdict differs from blocking findings")
        return self
