"""Claim-first canonical attempt accounting for future real-effect runners."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Callable, TypeVar

from shaiwei.ledger import append_experiment_once


CLAIM_SCHEMA = "shaiwei-effect-attempt-claim-v1"
RECEIPT_SCHEMA = "shaiwei-effect-attempt-claim-receipt-v1"
CLAIM_STATUS = "CLAIMED_BEFORE_EFFECT_READ"
_HEX12 = re.compile(r"[0-9a-f]{12}\Z")
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_SECRET_VALUE = re.compile(
    r"(?:sk-[A-Za-z0-9]{16,}|open-apis/bot/v2/hook/|(?:TOKEN|SECRET|PASSWORD|API_KEY)\s*=)",
    re.IGNORECASE,
)
_RECEIPT_KEYS = {
    "schema_version",
    "receipt_sha256",
    "claim_schema",
    "experiment_id",
    "release_scope_sha256",
    "attempt_ordinal",
    "claimed_at",
    "ledger_row_sha256",
    "canonical_ledger",
    "effect_read_allowed",
    "same_scope_retry_authorized",
    "production_authorization",
}
T = TypeVar("T")


class EffectAttemptClaimError(RuntimeError):
    """Raised when a real-effect attempt cannot be claimed or verified."""


def _canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _safe_text(value: str, field: str) -> str:
    if (
        not 1 <= len(value) <= 300
        or any(ord(character) < 32 for character in value)
        or Path(value).is_absolute()
        or _SECRET_VALUE.search(value)
    ):
        raise EffectAttemptClaimError(f"effect attempt {field} is invalid")
    return value


def _timestamp(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise EffectAttemptClaimError("effect attempt timestamp is invalid") from error
    if parsed.tzinfo is None:
        raise EffectAttemptClaimError("effect attempt timestamp lacks timezone")
    return parsed.isoformat()


@dataclass(frozen=True)
class EffectAttemptSpec:
    attempt_family: str
    release_scope_sha256: str
    attempt_ordinal: int
    candidate_source: str
    model_or_engine: str
    engine_version: str
    code_sha256: str
    data_snapshot_sha256: str
    feature_or_formula: str
    train_period: str
    valid_period: str
    parent_experiment_id: str = ""

    def validate(self) -> None:
        for field in (
            "attempt_family",
            "candidate_source",
            "model_or_engine",
            "engine_version",
            "feature_or_formula",
            "train_period",
            "valid_period",
        ):
            _safe_text(str(getattr(self, field)), field)
        if not _HEX64.fullmatch(self.release_scope_sha256):
            raise EffectAttemptClaimError("effect attempt release scope is invalid")
        if not _HEX64.fullmatch(self.code_sha256) or not _HEX64.fullmatch(
            self.data_snapshot_sha256
        ):
            raise EffectAttemptClaimError("effect attempt source identity is invalid")
        if self.attempt_ordinal < 1:
            raise EffectAttemptClaimError("effect attempt ordinal is invalid")
        if self.parent_experiment_id and not _HEX12.fullmatch(self.parent_experiment_id):
            raise EffectAttemptClaimError("effect attempt parent identity is invalid")

    @property
    def experiment_id(self) -> str:
        self.validate()
        identity = {
            "schema_version": CLAIM_SCHEMA,
            "attempt_family": self.attempt_family,
            "release_scope_sha256": self.release_scope_sha256,
            "attempt_ordinal": self.attempt_ordinal,
        }
        return _sha256(identity)[:12]


def build_claim_row(spec: EffectAttemptSpec, *, claimed_at: str) -> dict[str, str]:
    """Build a complete existing-schema ledger row without any effect values."""
    spec.validate()
    timestamp = _timestamp(claimed_at)
    params = {
        "attempt_family": spec.attempt_family,
        "attempt_ordinal": spec.attempt_ordinal,
        "claim_schema": CLAIM_SCHEMA,
        "release_scope_sha256": spec.release_scope_sha256,
        "same_scope_retry_authorized": False,
    }
    result = {
        "attempt_consumed": True,
        "authoritative": False,
        "production_authorization": "none",
        "status": CLAIM_STATUS,
    }
    return {
        "experiment_id": spec.experiment_id,
        "parent_experiment_id": spec.parent_experiment_id,
        "ts": timestamp,
        "candidate_source": spec.candidate_source,
        "model_or_engine": spec.model_or_engine,
        "engine_version": spec.engine_version,
        "seed": "",
        "prompt_hash": "",
        "code_sha256": spec.code_sha256,
        "data_snapshot_sha256": spec.data_snapshot_sha256,
        "feature_or_formula": spec.feature_or_formula,
        "params_json": _canonical(params),
        "train_period": spec.train_period,
        "valid_period": spec.valid_period,
        "result_json": _canonical(result),
        "admitted": "false",
        "reject_reason": "effect attempt claim; not a factor-admission experiment",
    }


def _receipt(row: dict[str, str], spec: EffectAttemptSpec) -> dict[str, object]:
    body: dict[str, object] = {
        "schema_version": RECEIPT_SCHEMA,
        "claim_schema": CLAIM_SCHEMA,
        "experiment_id": row["experiment_id"],
        "release_scope_sha256": spec.release_scope_sha256,
        "attempt_ordinal": spec.attempt_ordinal,
        "claimed_at": row["ts"],
        "ledger_row_sha256": _sha256(row),
        "canonical_ledger": "ledger/experiments.csv",
        "effect_read_allowed": True,
        "same_scope_retry_authorized": False,
        "production_authorization": "none",
    }
    return {**body, "receipt_sha256": _sha256(body)}


def _write_receipt(path: Path, document: dict[str, object]) -> None:
    payload = _canonical(document) + "\n"
    try:
        with path.open("x", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as error:
        raise EffectAttemptClaimError("effect attempt receipt already exists") from error
    descriptor = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def claim_effect_attempt(
    spec: EffectAttemptSpec,
    *,
    ledger_path: Path,
    receipt_path: Path,
    claimed_at: str | None = None,
) -> dict[str, object]:
    """Durably consume one scope before any caller is allowed to read effects."""
    spec.validate()
    if ledger_path.name != "experiments.csv" or not ledger_path.is_file():
        raise EffectAttemptClaimError("canonical effect attempt ledger is invalid")
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    if receipt_path.exists():
        raise EffectAttemptClaimError("effect attempt scope was already claimed")
    timestamp = claimed_at or datetime.now(timezone.utc).isoformat()
    row = build_claim_row(spec, claimed_at=timestamp)
    try:
        appended = append_experiment_once(path=ledger_path, **row)
    except ValueError as error:
        raise EffectAttemptClaimError("effect attempt scope was already claimed") from error
    if not appended:
        raise EffectAttemptClaimError("effect attempt scope was already claimed")
    receipt = _receipt(row, spec)
    _write_receipt(receipt_path, receipt)
    return receipt


def read_effect_after_claim(
    spec: EffectAttemptSpec,
    *,
    ledger_path: Path,
    receipt_path: Path,
    effect_reader: Callable[[dict[str, object]], T],
    claimed_at: str | None = None,
) -> T:
    """Call the injected effect reader only after the canonical claim is durable."""
    receipt = claim_effect_attempt(
        spec,
        ledger_path=ledger_path,
        receipt_path=receipt_path,
        claimed_at=claimed_at,
    )
    return effect_reader(receipt)


def verify_effect_attempt_claim(
    *, ledger_path: Path, receipt_path: Path
) -> dict[str, object]:
    """Independently bind one receipt to exactly one immutable canonical row."""
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise EffectAttemptClaimError("effect attempt receipt is invalid") from error
    if not isinstance(receipt, dict) or set(receipt) != _RECEIPT_KEYS:
        raise EffectAttemptClaimError("effect attempt receipt schema differs")
    unsigned = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
    if receipt.get("receipt_sha256") != _sha256(unsigned):
        raise EffectAttemptClaimError("effect attempt receipt identity differs")
    if (
        receipt.get("schema_version") != RECEIPT_SCHEMA
        or receipt.get("claim_schema") != CLAIM_SCHEMA
        or receipt.get("effect_read_allowed") is not True
        or receipt.get("same_scope_retry_authorized") is not False
        or receipt.get("production_authorization") != "none"
    ):
        raise EffectAttemptClaimError("effect attempt receipt authority differs")
    with ledger_path.open(newline="", encoding="utf-8") as handle:
        matches = [
            row
            for row in csv.DictReader(handle)
            if row["experiment_id"] == receipt["experiment_id"]
        ]
    if len(matches) != 1 or _sha256(matches[0]) != receipt.get("ledger_row_sha256"):
        raise EffectAttemptClaimError("effect attempt canonical row differs")
    return receipt
