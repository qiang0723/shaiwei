"""Pure exact value commitments for M5 statement-version observations."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

import pandas as pd

from .contract import IDENTITY_FIELDS, STATEMENT_FIELDS, M5GateError, sha256_json
from .lineage_contract import Observation


def normalized_number(value: Any) -> str:
    if value is None or pd.isna(value):
        return "NULL"
    try:
        number = Decimal(str(value))
    except InvalidOperation as exc:
        raise M5GateError("M5 lineage statement value is not numeric") from exc
    if not number.is_finite():
        raise M5GateError("M5 lineage statement value is not finite")
    if number == 0:
        number = Decimal(0)
    return format(number.normalize(), "f")


def identity_document(observation: Observation) -> dict[str, str]:
    return dict(zip(IDENTITY_FIELDS, observation.statement_identity, strict=True))


def identity_sha256(observation: Observation) -> str:
    return sha256_json(
        {
            "table": observation.table,
            "statement_identity": identity_document(observation),
        }
    )


def value_version_sha256(observation: Observation) -> str:
    return sha256_json(
        {
            "table": observation.table,
            "fields": [
                [field, normalized_number(observation.business_values[field])]
                for field in STATEMENT_FIELDS[observation.table]
            ],
        }
    )


def observation_commitment(observation: Observation) -> dict[str, Any]:
    return {
        "identity_sha256": identity_sha256(observation),
        "value_version_sha256": value_version_sha256(observation),
        "source_kind": observation.source_kind,
        "source_api": observation.source_api,
        "request_params_sha256": observation.request_params_sha256,
        "batch_id_sha256": sha256_json(observation.batch_id),
        "content_sha256": observation.content_sha256,
        "local_observed_at": observation.local_observed_at,
    }
