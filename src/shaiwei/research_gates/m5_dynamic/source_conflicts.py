"""Pure M5 statement-source classification with no file I/O or source selection."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

import pandas as pd

from .contract import IDENTITY_FIELDS, STATEMENT_FIELDS, M5GateError, sha256_json


CATEGORIES = (
    "EXACT_DUPLICATE_WITHIN_STANDARD",
    "EXACT_DUPLICATE_WITHIN_VIP",
    "CONSISTENT_OVERLAP_STANDARD_VIP",
    "CONFLICT_WITHIN_STANDARD",
    "CONFLICT_WITHIN_VIP",
    "CONFLICT_STANDARD_VIP",
)
CONFLICT_CATEGORIES = frozenset(CATEGORIES[3:])
SOURCE_KINDS = ("STANDARD", "VIP")


@dataclass(frozen=True)
class StatementSourceAssessment:
    canonical_frame: pd.DataFrame
    report: dict[str, Any]

    @property
    def conflict_count(self) -> int:
        return int(self.report["conflict_identity_group_count"])


@dataclass(frozen=True)
class SourceConflictAssessment:
    canonical_frames: dict[str, pd.DataFrame]
    report: dict[str, Any]

    @property
    def has_conflicts(self) -> bool:
        return bool(self.report["has_conflicts"])


def _normalized_number(value: Any) -> str:
    if value is None or pd.isna(value):
        return "NULL"
    try:
        number = Decimal(str(value))
    except InvalidOperation as exc:
        raise M5GateError("M5 statement value is not numeric") from exc
    if not number.is_finite():
        raise M5GateError("M5 statement value is not finite")
    if number == 0:
        number = Decimal(0)
    return format(number.normalize(), "f")


def _prepare(name: str, frame: pd.DataFrame, source_kind: str) -> pd.DataFrame:
    required = set(IDENTITY_FIELDS) | set(STATEMENT_FIELDS[name])
    if missing := required - set(frame.columns):
        raise M5GateError(f"tushare.{name} source missing columns: {sorted(missing)}")
    selected = frame.loc[:, sorted(required)].copy()
    selected["_source_kind"] = source_kind
    selected["_source_ordinal"] = range(len(selected))
    for column in IDENTITY_FIELDS:
        selected[column] = selected[column].astype("string")
    selected["end_date"] = selected["end_date"].str.replace("-", "", regex=False)
    selected["f_ann_date"] = selected["f_ann_date"].str.replace("-", "", regex=False)
    selected = selected.loc[
        selected["end_date"].str.endswith("1231", na=False)
        & selected["report_type"].isin(["1", "5"])
    ].copy()
    if selected.loc[:, list(IDENTITY_FIELDS)].isna().any(axis=None):
        raise M5GateError(f"{name} contains a missing source identity")
    return selected


def _variants(rows: pd.DataFrame, fields: tuple[str, ...]) -> set[tuple[str, ...]]:
    return {
        tuple(_normalized_number(row[field]) for field in fields)
        for row in rows.to_dict("records")
    }


def _category(
    standard: pd.DataFrame,
    vip: pd.DataFrame,
    standard_variants: set[tuple[str, ...]],
    vip_variants: set[tuple[str, ...]],
) -> str | None:
    if len(standard_variants) > 1:
        return "CONFLICT_WITHIN_STANDARD"
    if len(vip_variants) > 1:
        return "CONFLICT_WITHIN_VIP"
    if not standard.empty and not vip.empty:
        return (
            "CONSISTENT_OVERLAP_STANDARD_VIP"
            if standard_variants == vip_variants
            else "CONFLICT_STANDARD_VIP"
        )
    if len(standard) > 1:
        return "EXACT_DUPLICATE_WITHIN_STANDARD"
    if len(vip) > 1:
        return "EXACT_DUPLICATE_WITHIN_VIP"
    return None


def _conflicting_fields(group: pd.DataFrame, fields: tuple[str, ...]) -> list[str]:
    return [
        field
        for field in fields
        if len({_normalized_number(value) for value in group[field]}) > 1
    ]


def _variant_hashes(variants: set[tuple[str, ...]]) -> list[str]:
    return sorted(sha256_json(list(variant)) for variant in variants)


def assess_statement_sources(
    name: str,
    ordinary: pd.DataFrame,
    vip: pd.DataFrame,
) -> StatementSourceAssessment:
    if name not in STATEMENT_FIELDS:
        raise M5GateError("M5 statement table is outside the allowlist")
    fields = STATEMENT_FIELDS[name]
    combined = pd.concat(
        [_prepare(name, ordinary, "STANDARD"), _prepare(name, vip, "VIP")],
        ignore_index=True,
    )
    categories = {category: 0 for category in CATEGORIES}
    field_counts = {field: 0 for field in fields}
    canonical_rows: list[dict[str, Any]] = []
    commitments = []
    extra_rows = 0
    grouped = combined.groupby(list(IDENTITY_FIELDS), dropna=False, sort=True)
    for identity, group in grouped:
        standard = group.loc[group["_source_kind"].eq("STANDARD")]
        vip_rows = group.loc[group["_source_kind"].eq("VIP")]
        standard_variants = _variants(standard, fields)
        vip_variants = _variants(vip_rows, fields)
        category = _category(standard, vip_rows, standard_variants, vip_variants)
        if category is not None:
            categories[category] += 1
        conflicting = _conflicting_fields(group, fields)
        if category in CONFLICT_CATEGORIES:
            for field in conflicting:
                field_counts[field] += 1
            commitments.append(
                {
                    "identity": [
                        str(value)
                        for value in (
                            identity if isinstance(identity, tuple) else (identity,)
                        )
                    ],
                    "category": category,
                    "conflicting_fields": conflicting,
                    "source_variant_sha256": {
                        "STANDARD": _variant_hashes(standard_variants),
                        "VIP": _variant_hashes(vip_variants),
                    },
                }
            )
            continue
        preferred = standard if not standard.empty else vip_rows
        chosen = preferred.sort_values("_source_ordinal", kind="stable").iloc[0]
        canonical_rows.append(
            {column: chosen[column] for column in (*IDENTITY_FIELDS, *fields)}
        )
        extra_rows += len(group) - 1
    canonical = pd.DataFrame(
        canonical_rows,
        columns=(*IDENTITY_FIELDS, *fields),
    )
    conflict_count = sum(categories[category] for category in CONFLICT_CATEGORIES)
    return StatementSourceAssessment(
        canonical_frame=canonical,
        report={
            "table": name,
            "filtered_source_row_count": len(combined),
            "identity_group_count": int(grouped.ngroups),
            "canonical_row_count": len(canonical),
            "exact_duplicate_extra_row_count": extra_rows,
            "category_counts": categories,
            "conflict_identity_group_count": conflict_count,
            "conflict_field_counts": field_counts,
            "conflict_set_sha256": sha256_json(commitments),
        },
    )


def assess_all_statement_sources(
    frames: dict[str, pd.DataFrame],
) -> SourceConflictAssessment:
    canonical_frames: dict[str, pd.DataFrame] = {}
    reports = []
    commitments = []
    for table in STATEMENT_FIELDS:
        assessment = assess_statement_sources(
            table,
            frames[f"tushare.{table}"],
            frames[f"tushare.{table}_vip"],
        )
        canonical_frames[table] = assessment.canonical_frame
        reports.append(assessment.report)
        if assessment.conflict_count:
            commitments.append(
                {
                    "table": table,
                    "conflict_identity_group_count": assessment.conflict_count,
                    "conflict_set_sha256": assessment.report["conflict_set_sha256"],
                }
            )
    total = sum(int(report["conflict_identity_group_count"]) for report in reports)
    return SourceConflictAssessment(
        canonical_frames=canonical_frames,
        report={
            "schema_version": "m5-source-conflict-analysis-v2",
            "tables": reports,
            "total_conflict_identity_group_count": total,
            "global_conflict_set_sha256": sha256_json(commitments),
            "has_conflicts": total > 0,
        },
    )
