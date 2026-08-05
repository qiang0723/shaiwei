"""Strict value objects and canonical hashes for the M5-2 registry."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any


SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
CANDIDATE_RE = re.compile(r"^m5_[a-z0-9_]+_v1$")


class RegistryError(RuntimeError):
    """The command, persisted registry, or evidence is invalid."""


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_json(value: Any) -> str:
    return sha256_text(canonical_json(value))


def require_sha256(value: str, name: str) -> str:
    normalized = str(value)
    if SHA256_RE.fullmatch(normalized) is None:
        raise RegistryError(f"{name} must be a lowercase SHA-256")
    return normalized


def require_utc_iso(value: str, name: str) -> str:
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError as exc:
        raise RegistryError(f"{name} must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise RegistryError(f"{name} must use explicit UTC")
    return parsed.isoformat()


@dataclass(frozen=True)
class AxisState:
    lifecycle_state: str
    data_gate_status: str
    engineering_gate_status: str
    evidence_tier: str
    authoritative_outcome: str = "NOT_EVALUATED"
    production_authorization: str = "none"

    def as_dict(self) -> dict[str, str]:
        return asdict(self)

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> AxisState:
        keys = tuple(cls.__dataclass_fields__)
        if set(value) != set(keys) or any(not isinstance(value[key], str) for key in keys):
            raise RegistryError("axis state has an unknown or missing field")
        result = cls(**{key: value[key] for key in keys})
        if result.authoritative_outcome != "NOT_EVALUATED":
            raise RegistryError("M5-2 preexecution cannot evaluate strategy outcome")
        if result.production_authorization != "none":
            raise RegistryError("M5-2 preexecution cannot authorize production")
        return result


@dataclass(frozen=True)
class GateIdentity:
    proposal_id: str
    proposal_request_sha256: str
    canonical_proposal_sha256: str
    proposal_head_event_sha256: str
    proposal_export_sha256: str
    protocol_scope_sha256: str
    protocol_sha256: str
    proposal_expires_at: str
    candidate_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in (
            "proposal_id",
            "proposal_request_sha256",
            "canonical_proposal_sha256",
            "proposal_head_event_sha256",
            "proposal_export_sha256",
            "protocol_scope_sha256",
            "protocol_sha256",
        ):
            require_sha256(getattr(self, name), name)
        require_utc_iso(self.proposal_expires_at, "proposal_expires_at")
        if len(self.candidate_ids) != 8 or len(set(self.candidate_ids)) != 8:
            raise RegistryError("M5-2 identity must bind eight unique candidates")
        if any(CANDIDATE_RE.fullmatch(value) is None for value in self.candidate_ids):
            raise RegistryError("candidate identity is outside the frozen M5 namespace")

    @property
    def case_id(self) -> str:
        return sha256_text(
            "m5-gate-case-v1\0" + self.proposal_id + "\0" + self.protocol_scope_sha256
        )

    def as_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["candidate_ids"] = list(self.candidate_ids)
        return result


INITIAL_STATE = AxisState(
    lifecycle_state="IMPORTED",
    data_gate_status="NOT_READY",
    engineering_gate_status="NOT_READY",
    evidence_tier="PROPOSAL_ONLY",
)
