"""Independent M5 lineage recomputation; no primary lineage imports."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

import pandas as pd

from .contract import IDENTITY_FIELDS, STATEMENT_FIELDS, M5GateError, sha256_json
from .lineage_contract import Observation, VersionEvidence


PASS = {"LOSSLESS_EXACT_DUPLICATE", "PIT_VERSION_CHAIN_RESOLVED"}
FAIL = {
    "FORWARD_ONLY_OBSERVED_VERSION",
    "UNRESOLVED_MISSING_EFFECTIVE_TIME",
    "UNRESOLVED_AMBIGUOUS_ORDER",
    "UNRESOLVED_INCOMPLETE_CHAIN",
}


def _number(value: Any) -> str:
    if value is None or pd.isna(value):
        return "NULL"
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise M5GateError("M5 lineage audit value is not numeric") from exc
    if not result.is_finite():
        raise M5GateError("M5 lineage audit value is not finite")
    if result == 0:
        result = Decimal(0)
    return format(result.normalize(), "f")


def _identity(item: Observation) -> dict[str, str]:
    return dict(zip(IDENTITY_FIELDS, item.statement_identity, strict=True))


def _identity_sha(item: Observation) -> str:
    return sha256_json({"table": item.table, "statement_identity": _identity(item)})


def _value_sha(item: Observation) -> str:
    return sha256_json(
        {
            "table": item.table,
            "fields": [
                [field, _number(item.business_values[field])] for field in STATEMENT_FIELDS[item.table]
            ],
        }
    )


def _observation(item: Observation) -> dict[str, Any]:
    return {
        "identity_sha256": _identity_sha(item),
        "value_version_sha256": _value_sha(item),
        "source_kind": item.source_kind,
        "source_api": item.source_api,
        "request_params_sha256": item.request_params_sha256,
        "batch_id_sha256": sha256_json(item.batch_id),
        "content_sha256": item.content_sha256,
        "local_observed_at": item.local_observed_at,
    }


def _lineage(
    versions: set[str], evidence: list[VersionEvidence], as_of: str
) -> tuple[str, list[dict[str, Any]], int]:
    cutoff = datetime.fromisoformat(as_of).astimezone(timezone.utc)
    current = [
        item
        for item in evidence
        if datetime.fromisoformat(item.provider_revision_effective_at).astimezone(timezone.utc) <= cutoff
    ]
    future = len(evidence) - len(current)
    if not current:
        return "FORWARD_ONLY_OBSERVED_VERSION", [], future
    by_provider: dict[str, VersionEvidence] = {}
    for item in current:
        existing = by_provider.get(item.provider_version_id_sha256)
        if existing is not None and existing != item:
            return "UNRESOLVED_AMBIGUOUS_ORDER", [], future
        by_provider[item.provider_version_id_sha256] = item
    ordered = sorted(
        by_provider.values(),
        key=lambda item: (
            item.provider_revision_effective_at,
            item.provider_version_id_sha256,
        ),
    )
    if len({item.provider_revision_effective_at for item in ordered}) != len(ordered):
        return "UNRESOLVED_AMBIGUOUS_ORDER", [], future
    evidenced = {item.value_version_sha256 for item in ordered}
    if not versions <= evidenced:
        return "UNRESOLVED_MISSING_EFFECTIVE_TIME", [], future
    if evidenced != versions:
        return "UNRESOLVED_INCOMPLETE_CHAIN", [], future
    previous = None
    documents = []
    for item in ordered:
        if item.predecessor_provider_version_id_sha256 != previous:
            return "UNRESOLVED_INCOMPLETE_CHAIN", [], future
        documents.append(
            {
                "provider_version_id_sha256": item.provider_version_id_sha256,
                "value_version_sha256": item.value_version_sha256,
                "predecessor_provider_version_id_sha256": (item.predecessor_provider_version_id_sha256),
                "evidence_tier": item.evidence_tier,
                "provider_revision_effective_at": item.provider_revision_effective_at,
                "evidence_content_sha256": item.evidence_content_sha256,
                "evidence_locator_sha256": item.evidence_locator_sha256,
            }
        )
        previous = item.provider_version_id_sha256
    return "PIT_VERSION_CHAIN_RESOLVED", documents, future


def _observed_chain_matches(observations: list[Observation], chain: list[dict[str, Any]]) -> bool:
    observed = []
    for item in sorted(
        observations,
        key=lambda value: (
            value.local_observed_at,
            value.source_api,
            value.batch_id,
        ),
    ):
        version = _value_sha(item)
        if not observed or observed[-1] != version:
            observed.append(version)
    chain_values = [item["value_version_sha256"] for item in chain]
    cursor = 0
    for version in observed:
        try:
            cursor = chain_values.index(version, cursor) + 1
        except ValueError:
            return False
    return True


def audit_lineage(
    observations: list[Observation],
    evidence: list[VersionEvidence],
    *,
    as_of: str,
) -> dict[str, Any]:
    cutoff = datetime.fromisoformat(as_of)
    if cutoff.tzinfo is None:
        raise M5GateError("M5 lineage audit as_of lacks timezone")
    cutoff_utc = cutoff.astimezone(timezone.utc)
    groups: dict[tuple[str, tuple[str, ...]], list[Observation]] = defaultdict(list)
    evidence_groups: dict[tuple[str, tuple[str, ...]], list[VersionEvidence]] = defaultdict(list)
    for item in observations:
        if datetime.fromisoformat(item.local_observed_at).astimezone(timezone.utc) > cutoff_utc:
            raise M5GateError("M5 lineage audit observation occurs after as_of")
        groups[(item.table, item.statement_identity)].append(item)
    for item in evidence:
        evidence_groups[(item.table, item.statement_identity)].append(item)
    if set(evidence_groups) - set(groups):
        raise M5GateError("M5 lineage audit evidence identity is unobserved")
    audited = []
    future_count = 0
    for key in sorted(groups):
        items = groups[key]
        versions = {_value_sha(item) for item in items}
        chain_documents: list[dict[str, Any]] = []
        if len(versions) == 1:
            disposition = "LOSSLESS_EXACT_DUPLICATE"
        else:
            announcement = datetime.strptime(items[0].statement_identity[1], "%Y%m%d").date()
            group_evidence = evidence_groups.get(key, [])
            if any(
                datetime.fromisoformat(item.provider_revision_effective_at).astimezone(timezone.utc).date()
                < announcement
                for item in group_evidence
            ):
                disposition = "UNRESOLVED_INCOMPLETE_CHAIN"
                future = 0
            else:
                disposition, chain_documents, future = _lineage(versions, group_evidence, as_of)
                if disposition == "PIT_VERSION_CHAIN_RESOLVED" and not _observed_chain_matches(
                    items, chain_documents
                ):
                    disposition = "UNRESOLVED_INCOMPLETE_CHAIN"
                    chain_documents = []
            future_count += future
        observations_document = sorted(
            (_observation(item) for item in items),
            key=lambda item: (
                item["local_observed_at"],
                item["source_api"],
                item["batch_id_sha256"],
                item["value_version_sha256"],
            ),
        )
        commitment = {
            "table": items[0].table,
            "statement_identity": _identity(items[0]),
            "observations": observations_document,
            "authoritative_chain": chain_documents,
            "disposition": disposition,
        }
        audited.append(
            {
                "table": items[0].table,
                "identity_sha256": _identity_sha(items[0]),
                "disposition": disposition,
                "version_count": len(versions),
                "evidence_tiers": sorted({item.evidence_tier for item in evidence_groups.get(key, [])}),
                "lineage_commitment_sha256": sha256_json(commitment),
            }
        )
    disposition_counts = Counter(item["disposition"] for item in audited)
    tables = []
    for table in sorted({item["table"] for item in audited}):
        items = [item for item in audited if item["table"] == table]
        dispositions = Counter(item["disposition"] for item in items)
        tiers = Counter(tier for item in items for tier in item["evidence_tiers"])
        tables.append(
            {
                "table": table,
                "identity_group_count": len(items),
                "conflicting_identity_group_count": sum(item["version_count"] > 1 for item in items),
                "disposition_counts": {key: dispositions.get(key, 0) for key in sorted(PASS | FAIL)},
                "evidence_tier_counts": dict(sorted(tiers.items())),
                "lineage_commitment_sha256": sha256_json(
                    [
                        {
                            "identity_sha256": item["identity_sha256"],
                            "lineage_commitment_sha256": item["lineage_commitment_sha256"],
                        }
                        for item in items
                    ]
                ),
            }
        )
    historical_pass = bool(audited) and all(item["disposition"] in PASS for item in audited)
    return {
        "as_of": cutoff.astimezone(timezone.utc).isoformat(),
        "identity_field_count": len(IDENTITY_FIELDS),
        "identity_group_count": len(audited),
        "conflicting_identity_group_count": sum(item["version_count"] > 1 for item in audited),
        "tables": tables,
        "disposition_counts": {key: disposition_counts.get(key, 0) for key in sorted(PASS | FAIL)},
        "unresolved_reason_counts": {key: disposition_counts.get(key, 0) for key in sorted(FAIL)},
        "future_evidence_count": future_count,
        "historical_lineage_pass": historical_pass,
        "global_lineage_commitment_sha256": sha256_json(
            [
                {
                    "table": item["table"],
                    "identity_sha256": item["identity_sha256"],
                    "lineage_commitment_sha256": item["lineage_commitment_sha256"],
                    "disposition": item["disposition"],
                }
                for item in audited
            ]
        ),
    }
