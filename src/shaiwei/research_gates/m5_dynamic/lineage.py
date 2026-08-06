"""Pure M5 version-lineage construction with fail-closed historical semantics."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .contract import IDENTITY_FIELDS, M5GateError, sha256_json
from .lineage_commitment import (
    identity_document,
    identity_sha256,
    observation_commitment,
    value_version_sha256,
)
from .lineage_contract import Observation, VersionEvidence


PASS_DISPOSITIONS = {"LOSSLESS_EXACT_DUPLICATE", "PIT_VERSION_CHAIN_RESOLVED"}
FAIL_DISPOSITIONS = {
    "FORWARD_ONLY_OBSERVED_VERSION",
    "UNRESOLVED_MISSING_EFFECTIVE_TIME",
    "UNRESOLVED_AMBIGUOUS_ORDER",
    "UNRESOLVED_INCOMPLETE_CHAIN",
}


@dataclass(frozen=True)
class LineageGroup:
    table: str
    identity_sha256: str
    disposition: str
    observed_value_versions: tuple[str, ...]
    evidence_tiers: tuple[str, ...]
    lineage_commitment_sha256: str
    local_observation_count: int


@dataclass(frozen=True)
class LineageAssessment:
    groups: tuple[LineageGroup, ...]
    report: dict[str, Any]

    @property
    def historical_pass(self) -> bool:
        return bool(self.report["historical_lineage_pass"])


def _utc(value: str) -> datetime:
    return datetime.fromisoformat(value).astimezone(timezone.utc)


def _effective_evidence(evidence: list[VersionEvidence], as_of: str) -> tuple[list[VersionEvidence], int]:
    cutoff = _utc(as_of)
    included = [item for item in evidence if _utc(item.provider_revision_effective_at) <= cutoff]
    return included, len(evidence) - len(included)


def _ordered_chain_disposition(
    observed_versions: set[str], evidence: list[VersionEvidence], as_of: str
) -> tuple[str, list[dict[str, Any]], int]:
    included, future_count = _effective_evidence(evidence, as_of)
    if not included:
        return "FORWARD_ONLY_OBSERVED_VERSION", [], future_count
    by_provider: dict[str, VersionEvidence] = {}
    for item in included:
        prior = by_provider.get(item.provider_version_id_sha256)
        if prior is not None and prior != item:
            return "UNRESOLVED_AMBIGUOUS_ORDER", [], future_count
        by_provider[item.provider_version_id_sha256] = item
    chain = sorted(
        by_provider.values(),
        key=lambda item: (
            item.provider_revision_effective_at,
            item.provider_version_id_sha256,
        ),
    )
    if len({item.provider_revision_effective_at for item in chain}) != len(chain):
        return "UNRESOLVED_AMBIGUOUS_ORDER", [], future_count
    evidenced_versions = {item.value_version_sha256 for item in chain}
    if not observed_versions <= evidenced_versions:
        return "UNRESOLVED_MISSING_EFFECTIVE_TIME", [], future_count
    if evidenced_versions != observed_versions:
        return "UNRESOLVED_INCOMPLETE_CHAIN", [], future_count
    expected_predecessor = None
    chain_documents = []
    for item in chain:
        if item.predecessor_provider_version_id_sha256 != expected_predecessor:
            return "UNRESOLVED_INCOMPLETE_CHAIN", [], future_count
        chain_documents.append(
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
        expected_predecessor = item.provider_version_id_sha256
    return "PIT_VERSION_CHAIN_RESOLVED", chain_documents, future_count


def _observations_follow_chain(observations: list[Observation], chain: list[dict[str, Any]]) -> bool:
    observed = []
    for item in sorted(
        observations,
        key=lambda value: (
            value.local_observed_at,
            value.source_api,
            value.batch_id,
        ),
    ):
        version = value_version_sha256(item)
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


def _group(
    observations: list[Observation],
    evidence: list[VersionEvidence],
    *,
    as_of: str,
) -> tuple[LineageGroup, int]:
    first = observations[0]
    versions = {value_version_sha256(item) for item in observations}
    observation_documents = sorted(
        (observation_commitment(item) for item in observations),
        key=lambda item: (
            item["local_observed_at"],
            item["source_api"],
            item["batch_id_sha256"],
            item["value_version_sha256"],
        ),
    )
    future_count = 0
    chain_documents: list[dict[str, Any]] = []
    if len(versions) == 1:
        disposition = "LOSSLESS_EXACT_DUPLICATE"
    else:
        announcement = datetime.strptime(first.statement_identity[1], "%Y%m%d").date()
        if any(_utc(item.provider_revision_effective_at).date() < announcement for item in evidence):
            disposition = "UNRESOLVED_INCOMPLETE_CHAIN"
        else:
            disposition, chain_documents, future_count = _ordered_chain_disposition(versions, evidence, as_of)
            if disposition == "PIT_VERSION_CHAIN_RESOLVED" and not _observations_follow_chain(
                observations, chain_documents
            ):
                disposition = "UNRESOLVED_INCOMPLETE_CHAIN"
                chain_documents = []
    commitment = {
        "table": first.table,
        "statement_identity": identity_document(first),
        "observations": observation_documents,
        "authoritative_chain": chain_documents,
        "disposition": disposition,
    }
    return (
        LineageGroup(
            table=first.table,
            identity_sha256=identity_sha256(first),
            disposition=disposition,
            observed_value_versions=tuple(sorted(versions)),
            evidence_tiers=tuple(sorted({item.evidence_tier for item in evidence})),
            lineage_commitment_sha256=sha256_json(commitment),
            local_observation_count=len(observations),
        ),
        future_count,
    )


def assess_lineage(
    observations: list[Observation],
    evidence: list[VersionEvidence],
    *,
    as_of: str,
) -> LineageAssessment:
    cutoff = datetime.fromisoformat(as_of)
    if cutoff.tzinfo is None:
        raise M5GateError("M5 lineage as_of must include timezone")
    cutoff_utc = cutoff.astimezone(timezone.utc)
    grouped: dict[tuple[str, tuple[str, ...]], list[Observation]] = defaultdict(list)
    for item in observations:
        if _utc(item.local_observed_at) > cutoff_utc:
            raise M5GateError("M5 lineage observation occurs after as_of")
        grouped[(item.table, item.statement_identity)].append(item)
    evidence_grouped: dict[tuple[str, tuple[str, ...]], list[VersionEvidence]] = defaultdict(list)
    for item in evidence:
        evidence_grouped[(item.table, item.statement_identity)].append(item)
    if set(evidence_grouped) - set(grouped):
        raise M5GateError("M5 lineage evidence references an unobserved identity")
    groups = []
    future_evidence_count = 0
    for key in sorted(grouped):
        group, future = _group(grouped[key], evidence_grouped.get(key, []), as_of=as_of)
        groups.append(group)
        future_evidence_count += future
    dispositions = Counter(item.disposition for item in groups)
    unresolved = {key: dispositions.get(key, 0) for key in sorted(FAIL_DISPOSITIONS)}
    tables = []
    for table in sorted({item.table for item in groups}):
        table_groups = [item for item in groups if item.table == table]
        table_dispositions = Counter(item.disposition for item in table_groups)
        table_tiers = Counter(tier for item in table_groups for tier in item.evidence_tiers)
        tables.append(
            {
                "table": table,
                "identity_group_count": len(table_groups),
                "conflicting_identity_group_count": sum(
                    len(item.observed_value_versions) > 1 for item in table_groups
                ),
                "disposition_counts": {
                    key: table_dispositions.get(key, 0)
                    for key in sorted(PASS_DISPOSITIONS | FAIL_DISPOSITIONS)
                },
                "evidence_tier_counts": dict(sorted(table_tiers.items())),
                "lineage_commitment_sha256": sha256_json(
                    [
                        {
                            "identity_sha256": item.identity_sha256,
                            "lineage_commitment_sha256": item.lineage_commitment_sha256,
                        }
                        for item in table_groups
                    ]
                ),
            }
        )
    conflicting_count = sum(len(item.observed_value_versions) > 1 for item in groups)
    historical_pass = bool(groups) and all(item.disposition in PASS_DISPOSITIONS for item in groups)
    report = {
        "schema_version": "m5-source-lineage-analysis-v1",
        "as_of": cutoff.astimezone(timezone.utc).isoformat(),
        "identity_field_count": len(IDENTITY_FIELDS),
        "identity_group_count": len(groups),
        "conflicting_identity_group_count": conflicting_count,
        "tables": tables,
        "disposition_counts": {
            key: dispositions.get(key, 0) for key in sorted(PASS_DISPOSITIONS | FAIL_DISPOSITIONS)
        },
        "unresolved_reason_counts": unresolved,
        "future_evidence_count": future_evidence_count,
        "historical_lineage_pass": historical_pass,
        "global_lineage_commitment_sha256": sha256_json(
            [
                {
                    "table": item.table,
                    "identity_sha256": item.identity_sha256,
                    "lineage_commitment_sha256": item.lineage_commitment_sha256,
                    "disposition": item.disposition,
                }
                for item in groups
            ]
        ),
    }
    return LineageAssessment(groups=tuple(groups), report=report)
