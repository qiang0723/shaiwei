"""Strict protocol and input-manifest contracts for the M5 dynamic data gate."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any

import yaml


PROTOCOL_ID = "m5-dynamic-fundamental-cross-pool-data-preexecution-v1"
BUILD_PROTOCOL_ID = "m5-dynamic-fundamental-data-gate-build-v1"
PROTOCOL_SCOPE_SHA256 = "ab8c33968c4ced325ec79524b774163f2991edd0c4d5d7eb7c139b27e9b17557"
REQUIRED_APIS = (
    "tushare.trade_cal",
    "tushare.income",
    "tushare.income_vip",
    "tushare.balancesheet",
    "tushare.balancesheet_vip",
    "tushare.cashflow",
    "tushare.cashflow_vip",
)
IDENTITY_FIELDS = ("ts_code", "f_ann_date", "end_date", "report_type", "update_flag")
STATEMENT_FIELDS = {
    "income": ("total_revenue", "total_cogs", "rd_exp"),
    "balancesheet": (
        "accounts_receiv",
        "inventories",
        "total_assets",
        "total_liab",
        "total_cur_assets",
        "total_cur_liab",
    ),
    "cashflow": ("n_cash_flows_fnc_act", "free_cashflow"),
}
API_FIELDS = {
    "tushare.trade_cal": ("exchange", "cal_date", "is_open"),
    **{
        f"tushare.{api}": (*IDENTITY_FIELDS, *STATEMENT_FIELDS[statement])
        for statement in STATEMENT_FIELDS
        for api in (statement, f"{statement}_vip")
    },
}
FORBIDDEN_TOKENS = {
    "daily",
    "daily_basic",
    "adj_factor",
    "index_daily",
    "label",
    "effect",
    "return",
    "model",
    "prediction",
    "holding",
}


class M5GateError(RuntimeError):
    """A frozen M5 contract, input identity, or data row is invalid."""


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_relative_path(value: str, name: str) -> str:
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise M5GateError(f"{name} must be a safe project-relative path")
    return path.as_posix()


def _sha(value: Any, name: str) -> str:
    normalized = str(value)
    if len(normalized) != 64 or any(character not in "0123456789abcdef" for character in normalized):
        raise M5GateError(f"{name} must be a lowercase SHA-256")
    return normalized


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    expected_direction: int
    inputs: tuple[str, ...]
    formula: str

    @property
    def required_tables(self) -> tuple[str, ...]:
        return tuple(sorted({value.split(".", 1)[0] for value in self.inputs}))


@dataclass(frozen=True)
class Universe:
    universe_id: str
    membership_relative_path: str
    membership_sha256: str
    filter_column: str | None
    filter_value: str | None


@dataclass(frozen=True)
class M5DataProtocol:
    path: Path
    document: dict[str, Any]
    build_document: dict[str, Any]
    sha256: str
    candidates: tuple[Candidate, ...]
    universes: tuple[Universe, ...]

    @classmethod
    def load(
        cls,
        path: Path,
        *,
        build_path: Path,
        project_root: Path,
    ) -> M5DataProtocol:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        build = yaml.safe_load(build_path.read_text(encoding="utf-8"))
        if not isinstance(document, dict) or not isinstance(build, dict):
            raise M5GateError("M5 protocol and build contract must be mappings")
        if document.get("protocol_id") != PROTOCOL_ID:
            raise M5GateError("M5 protocol ID differs")
        if build.get("build_protocol_id") != BUILD_PROTOCOL_ID:
            raise M5GateError("M5 build protocol ID differs")
        if build.get("protocol_scope_sha256") != PROTOCOL_SCOPE_SHA256:
            raise M5GateError("M5 protocol scope differs")
        for item in build.get("frozen_inputs", {}).values():
            frozen_path = project_root / _safe_relative_path(str(item.get("path", "")), "frozen input")
            if not frozen_path.is_file() or sha256_file(frozen_path) != _sha(item.get("sha256"), "frozen input"):
                raise M5GateError("M5 frozen input hash differs")
        candidates = tuple(
            Candidate(
                candidate_id=str(item["candidate_id"]),
                expected_direction=int(item["expected_direction"]),
                inputs=tuple(str(value) for value in item["inputs"]),
                formula=str(item["formula"]),
            )
            for item in document.get("candidates", [])
        )
        if len(candidates) != 8 or len({item.candidate_id for item in candidates}) != 8:
            raise M5GateError("M5 protocol must contain eight unique candidates")
        for candidate in candidates:
            if candidate.expected_direction not in {-1, 1} or not candidate.inputs:
                raise M5GateError("M5 candidate direction or inputs differ")
            for component in candidate.inputs:
                table, separator, field_period = component.partition(".")
                field, suffix = field_period.rsplit("_", 1)
                if (
                    separator != "."
                    or table not in STATEMENT_FIELDS
                    or field not in STATEMENT_FIELDS[table]
                    or suffix not in {"t", "p"}
                ):
                    raise M5GateError("M5 candidate input is outside the financial allowlist")
        universes = []
        for item in document.get("universe_inputs", []):
            member_filter = item.get("membership_filter") or {}
            universes.append(
                Universe(
                    universe_id=str(item["universe_id"]),
                    membership_relative_path=_safe_relative_path(
                        str(item["membership_relative_path"]), "membership"
                    ),
                    membership_sha256=_sha(item["membership_sha256"], "membership"),
                    filter_column=member_filter.get("column"),
                    filter_value=member_filter.get("value"),
                )
            )
        if len(universes) != 3 or len({item.universe_id for item in universes}) != 3:
            raise M5GateError("M5 protocol must contain three unique universes")
        if int(document["scope"]["evaluation_unit_count"]) != 24:
            raise M5GateError("M5 protocol must contain 24 evaluation units")
        return cls(
            path=path,
            document=document,
            build_document=build,
            sha256=sha256_file(path),
            candidates=candidates,
            universes=tuple(universes),
        )

    @property
    def candidate_ids(self) -> tuple[str, ...]:
        return tuple(item.candidate_id for item in self.candidates)

    @property
    def universe_ids(self) -> tuple[str, ...]:
        return tuple(item.universe_id for item in self.universes)


@dataclass(frozen=True)
class InputManifest:
    document: dict[str, Any]
    sha256: str
    physical_sha256: str = ""

    @classmethod
    def load(cls, path: Path, protocol: M5DataProtocol) -> InputManifest:
        serialized = path.read_text(encoding="utf-8")
        document = json.loads(serialized)
        expected_fields = {
            "schema_version",
            "created_at",
            "protocol_scope_sha256",
            "protocol_sha256",
            "semantic_rows_read",
            "ledger_selection_scope",
            "sources",
            "memberships",
        }
        if (
            not isinstance(document, dict)
            or set(document) != expected_fields
            or document.get("schema_version") != "m5-data-input-v1"
            or serialized != canonical_json(document) + "\n"
        ):
            raise M5GateError("M5 input manifest schema differs")
        try:
            created_at = datetime.fromisoformat(str(document["created_at"]))
        except ValueError as exc:
            raise M5GateError("M5 input manifest creation time is invalid") from exc
        if created_at.tzinfo is None:
            raise M5GateError("M5 input manifest creation time lacks timezone")
        if document.get("protocol_scope_sha256") != PROTOCOL_SCOPE_SHA256:
            raise M5GateError("M5 input manifest protocol scope differs")
        if document.get("protocol_sha256") != protocol.sha256:
            raise M5GateError("M5 input manifest protocol hash differs")
        if document.get("semantic_rows_read") is not False:
            raise M5GateError("preapproval input inventory must not read semantic rows")
        if document.get("ledger_selection_scope") != list(REQUIRED_APIS):
            raise M5GateError("M5 input manifest ledger selection scope differs")
        sources = document.get("sources")
        if (
            not isinstance(sources, list)
            or [item.get("source_api") for item in sources] != list(REQUIRED_APIS)
        ):
            raise M5GateError("M5 input manifest must bind exactly seven source APIs")
        batch_ids: set[str] = set()
        for source in sources:
            if set(source) != {"source_api", "selection_sha256", "batches"}:
                raise M5GateError("M5 input source envelope fields differ")
            api = str(source["source_api"])
            if any(token in api.lower().split(".") for token in FORBIDDEN_TOKENS):
                raise M5GateError("M5 input manifest includes a forbidden API")
            batches = source.get("batches")
            if not isinstance(batches, list) or not batches:
                raise M5GateError("each M5 source API requires at least one exact batch")
            if source.get("selection_sha256") != sha256_json(batches):
                raise M5GateError("M5 input source selection hash differs")
            for batch in batches:
                if set(batch) != {
                    "batch_id",
                    "batch_identity_sha256",
                    "relative_path",
                    "content_sha256",
                    "request_params_sha256",
                    "row_count",
                    "bytes",
                    "schema_fields",
                    "ingest_time",
                }:
                    raise M5GateError("M5 input batch metadata fields differ")
                batch_id = str(batch.get("batch_id", ""))
                if not batch_id or len(batch_id) > 128:
                    raise M5GateError("M5 input batch ID is empty or too long")
                if batch_id in batch_ids:
                    raise M5GateError("M5 input manifest repeats a batch identity")
                batch_ids.add(batch_id)
                _sha(batch.get("batch_identity_sha256"), "batch identity")
                _safe_relative_path(str(batch.get("relative_path", "")), "batch")
                _sha(batch.get("content_sha256"), "batch content")
                _sha(batch.get("request_params_sha256"), "batch request")
                if int(batch.get("row_count", -1)) < 0 or int(batch.get("bytes", -1)) <= 0:
                    raise M5GateError("M5 input batch metadata is invalid")
                fields = batch.get("schema_fields")
                if not isinstance(fields, list) or not set(API_FIELDS[api]) <= set(fields):
                    raise M5GateError("M5 input batch schema lacks an allowlisted field")
        memberships = document.get("memberships")
        if not isinstance(memberships, list) or len(memberships) != len(protocol.universes):
            raise M5GateError("M5 input membership count differs")
        for item in memberships:
            if set(item) != {
                "universe_id",
                "relative_path",
                "content_sha256",
                "row_count",
                "bytes",
                "schema_fields",
                "filter",
            }:
                raise M5GateError("M5 input membership metadata fields differ")
            if int(item.get("row_count", -1)) < 0 or int(item.get("bytes", -1)) <= 0:
                raise M5GateError("M5 input membership metadata is invalid")
            fields = item.get("schema_fields")
            if not isinstance(fields, list) or not {"trade_date", "ts_code"} <= set(fields):
                raise M5GateError("M5 input membership schema differs")
        expected_memberships = {
            (item.universe_id, item.membership_relative_path, item.membership_sha256)
            for item in protocol.universes
        }
        actual_memberships = {
            (
                str(item.get("universe_id")),
                _safe_relative_path(str(item.get("relative_path", "")), "membership"),
                _sha(item.get("content_sha256"), "membership"),
            )
            for item in memberships or []
        }
        if actual_memberships != expected_memberships:
            raise M5GateError("M5 input membership identities differ")
        universe_map = {item.universe_id: item for item in protocol.universes}
        for item in memberships:
            universe = universe_map[str(item["universe_id"])]
            expected_filter = (
                None
                if universe.filter_column is None
                else {"column": universe.filter_column, "value": universe.filter_value}
            )
            if item["filter"] != expected_filter:
                raise M5GateError("M5 input membership filter differs")
            if universe.filter_column and not {
                "formation_date",
                universe.filter_column,
            } <= set(item["schema_fields"]):
                raise M5GateError("M5 custom membership schema differs")
        return cls(
            document=document,
            sha256=sha256_json(document),
            physical_sha256=sha256_file(path),
        )
