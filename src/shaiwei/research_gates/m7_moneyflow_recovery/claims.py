"""Request-level pre-read claims and bounded mockable transport attempts."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Generic, TypeVar

from shaiwei.research_gates.m7_moneyflow.contract import (
    canonical_json,
    require_sha256,
    sha256_json,
)

from .contract import RecoveryError


T = TypeVar("T")
U = TypeVar("U")


class RetryableTransportError(RecoveryError):
    """A synthetic transport failure eligible for the frozen bounded retry."""


class SemanticResponseError(RecoveryError):
    """A response content failure that must never be retried in the same release."""


@dataclass(frozen=True)
class RequestClaimIdentity:
    release_scope_sha256: str
    request_sha256: str


@dataclass(frozen=True)
class ClaimedResult(Generic[U]):
    value: U
    attempt_count: int
    claim_sha256: str


def _claim_document(identity: RequestClaimIdentity) -> dict[str, object]:
    document = {
        "schema_version": "m7-moneyflow-recovery-request-claim-v1",
        "release_scope_sha256": require_sha256(identity.release_scope_sha256, "release scope SHA"),
        "request_sha256": require_sha256(identity.request_sha256, "request SHA"),
        "same_request_retry_authorized": False,
        "transport_attempt_cap_within_claim": 3,
        "semantic_failure_retry_authorized": False,
        "production_authorization": "none",
    }
    return {**document, "claim_sha256": sha256_json(document)}


def claim_request(root: Path, identity: RequestClaimIdentity) -> dict[str, object]:
    """Atomically consume a request before any provider loader is invoked."""

    document = _claim_document(identity)
    root.mkdir(parents=True, exist_ok=True)
    target = root / f"{identity.release_scope_sha256}.{identity.request_sha256}.json"
    payload = (canonical_json(document) + "\n").encode()
    try:
        with target.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as error:
        raise RecoveryError("recovery request was already claimed before provider read") from error
    descriptor = os.open(root, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return document


def execute_claimed_request(
    root: Path,
    identity: RequestClaimIdentity,
    fetch: Callable[[], T],
    validate: Callable[[T], U],
) -> ClaimedResult[U]:
    """Claim once, retry transport at most three times, and never retry semantics."""

    claim = claim_request(root, identity)
    for attempt in range(1, 4):
        try:
            response = fetch()
        except RetryableTransportError:
            if attempt == 3:
                raise
            continue
        value = validate(response)
        return ClaimedResult(value, attempt, str(claim["claim_sha256"]))
    raise AssertionError("bounded recovery request loop exhausted unexpectedly")
