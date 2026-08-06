"""Independent exact M5 source-conflict audit with no runner imports or I/O."""

from __future__ import annotations

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


def _number(value: Any) -> str:
    if value is None or pd.isna(value):
        return "NULL"
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise M5GateError("M5 audit statement value is not numeric") from exc
    if not result.is_finite():
        raise M5GateError("M5 audit statement value is not finite")
    if result == 0:
        result = Decimal(0)
    return format(result.normalize(), "f")


def _source(name: str, frame: pd.DataFrame, kind: str) -> pd.DataFrame:
    required = set(IDENTITY_FIELDS) | set(STATEMENT_FIELDS[name])
    if missing := required - set(frame.columns):
        raise M5GateError(f"M5 audit source missing columns: {sorted(missing)}")
    result = frame.loc[:, sorted(required)].copy()
    result["_kind"] = kind
    result["_ordinal"] = range(len(result))
    for column in IDENTITY_FIELDS:
        result[column] = result[column].astype("string")
    for column in ("end_date", "f_ann_date"):
        result[column] = result[column].str.replace("-", "", regex=False)
    result = result.loc[
        result["end_date"].str.endswith("1231", na=False)
        & result["report_type"].isin(["1", "5"])
    ].copy()
    if result.loc[:, list(IDENTITY_FIELDS)].isna().any(axis=None):
        raise M5GateError(f"{name} contains a missing source identity")
    return result


def _variants(frame: pd.DataFrame, fields: tuple[str, ...]) -> set[tuple[str, ...]]:
    return {
        tuple(_number(row[field]) for field in fields)
        for row in frame.to_dict("records")
    }


def _classify(
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
        if standard_variants == vip_variants:
            return "CONSISTENT_OVERLAP_STANDARD_VIP"
        return "CONFLICT_STANDARD_VIP"
    if len(standard) > 1:
        return "EXACT_DUPLICATE_WITHIN_STANDARD"
    if len(vip) > 1:
        return "EXACT_DUPLICATE_WITHIN_VIP"
    return None


def audit_statement_sources(
    name: str,
    ordinary: pd.DataFrame,
    vip: pd.DataFrame,
) -> dict[str, Any]:
    if name not in STATEMENT_FIELDS:
        raise M5GateError("M5 audit statement table is outside the allowlist")
    fields = STATEMENT_FIELDS[name]
    combined = pd.concat(
        [_source(name, ordinary, "STANDARD"), _source(name, vip, "VIP")],
        ignore_index=True,
    )
    categories = {category: 0 for category in CATEGORIES}
    field_counts = {field: 0 for field in fields}
    commitments = []
    grouped = combined.groupby(list(IDENTITY_FIELDS), dropna=False, sort=True)
    for identity, group in grouped:
        standard = group.loc[group["_kind"].eq("STANDARD")]
        vip_rows = group.loc[group["_kind"].eq("VIP")]
        standard_variants = _variants(standard, fields)
        vip_variants = _variants(vip_rows, fields)
        category = _classify(
            standard, vip_rows, standard_variants, vip_variants
        )
        if category is not None:
            categories[category] += 1
        if category not in CONFLICT_CATEGORIES:
            continue
        conflicting = [
            field
            for field in fields
            if len({_number(value) for value in group[field]}) > 1
        ]
        for field in conflicting:
            field_counts[field] += 1
        values = identity if isinstance(identity, tuple) else (identity,)
        commitments.append(
            {
                "identity": [str(value) for value in values],
                "category": category,
                "conflicting_fields": conflicting,
                "source_variant_sha256": {
                    "STANDARD": sorted(
                        sha256_json(list(variant)) for variant in standard_variants
                    ),
                    "VIP": sorted(
                        sha256_json(list(variant)) for variant in vip_variants
                    ),
                },
            }
        )
    conflict_count = sum(categories[item] for item in CONFLICT_CATEGORIES)
    return {
        "table": name,
        "category_counts": categories,
        "conflict_identity_group_count": conflict_count,
        "conflict_field_counts": field_counts,
        "conflict_set_sha256": sha256_json(commitments),
    }


def audit_all_statement_sources(frames: dict[str, pd.DataFrame]) -> dict[str, Any]:
    reports = [
        audit_statement_sources(
            name,
            frames[f"tushare.{name}"],
            frames[f"tushare.{name}_vip"],
        )
        for name in STATEMENT_FIELDS
    ]
    commitments = [
        {
            "table": item["table"],
            "conflict_identity_group_count": item[
                "conflict_identity_group_count"
            ],
            "conflict_set_sha256": item["conflict_set_sha256"],
        }
        for item in reports
        if item["conflict_identity_group_count"]
    ]
    total = sum(int(item["conflict_identity_group_count"]) for item in reports)
    return {
        "table_category_counts": reports,
        "total_conflict_identity_group_count": total,
        "global_conflict_set_sha256": sha256_json(commitments),
        "has_conflicts": total > 0,
    }
