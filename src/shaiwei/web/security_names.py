"""Content-addressed, read-only security-name projection for Web views."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
from typing import Any
import uuid

SCHEMA_VERSION = "web-security-name-catalog-v1"
POINTER_SCHEMA_VERSION = "web-security-name-pointer-v1"
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "data/web/security_names"
DEFAULT_LEDGER_PATH = PROJECT_ROOT / "ledger/ingest_batches.csv"
CODE_PATTERN = re.compile(r"^\d{6}\.(SH|SZ)$")
EXCHANGE_TEST_CODE_PATTERN = re.compile(r"^T\d{6}\.(SH|SZ)$")
DATE_PATTERN = re.compile(r"^\d{8}$")


class SecurityNameError(RuntimeError):
    pass


def _canonical(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def _clean(value: object) -> str:
    text = str(value).strip()
    return "" if text.lower() in {"nan", "nat", "none", "<na>"} else text


def _date(value: object, *, optional: bool = False) -> str:
    text = _clean(value).replace("-", "")
    if optional and not text:
        return ""
    if not DATE_PATTERN.fullmatch(text):
        raise SecurityNameError("security-name source contains an invalid date")
    try:
        datetime.strptime(text, "%Y%m%d")
    except ValueError as error:
        raise SecurityNameError("security-name source contains an invalid date") from error
    return text


def _timestamp(value: object) -> str:
    text = _clean(value)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as error:
        raise SecurityNameError("security-name source cutoff is invalid") from error
    if parsed.tzinfo is None:
        raise SecurityNameError("security-name source cutoff is missing a timezone")
    return text


def _code(value: object) -> str:
    text = _clean(value).upper()
    if not CODE_PATTERN.fullmatch(text):
        raise SecurityNameError("security-name source contains an unsupported security code")
    return text


def _require_columns(frame: Any, required: set[str], label: str) -> None:
    missing = required - set(frame.columns)
    if missing:
        raise SecurityNameError(f"{label} source is missing required columns")


def project_catalog(
    namechange: Any,
    stock_basic: Any,
    *,
    source_cutoff: str,
    source_identities: dict[str, dict[str, object]],
) -> dict[str, object]:
    """Normalize registered source frames without carrying raw file paths."""
    source_cutoff = _timestamp(source_cutoff)
    _require_columns(namechange, {"ts_code", "name", "start_date", "end_date"}, "namechange")
    _require_columns(stock_basic, {"ts_code", "name", "list_date", "list_status"}, "stock_basic")

    history: list[dict[str, str]] = []
    excluded_bse_history = 0
    for row in namechange.loc[:, ["ts_code", "name", "start_date", "end_date"]].itertuples(
        index=False
    ):
        raw_code = _clean(row.ts_code).upper()
        if raw_code.endswith(".BJ"):
            excluded_bse_history += 1
            continue
        code = _code(raw_code)
        name = _clean(row.name)
        start = _date(row.start_date)
        end = _date(row.end_date, optional=True)
        if not name or (end and start > end):
            raise SecurityNameError("namechange source contains an invalid interval")
        history.append(
            {"ts_code": code, "name": name, "start_date": start, "end_date": end}
        )
    history.sort(key=lambda row: (row["ts_code"], row["start_date"], row["end_date"], row["name"]))
    history_keys = {
        (row["ts_code"], row["name"], row["start_date"], row["end_date"])
        for row in history
    }
    if len(history_keys) != len(history):
        raise SecurityNameError("namechange source contains duplicate intervals")

    fallback: list[dict[str, str]] = []
    excluded_bse_basic = 0
    excluded_exchange_test_basic = 0
    seen_codes: set[str] = set()
    for row in stock_basic.loc[:, ["ts_code", "name", "list_date", "list_status"]].itertuples(
        index=False
    ):
        raw_code = _clean(row.ts_code).upper()
        if raw_code.endswith(".BJ"):
            excluded_bse_basic += 1
            continue
        if EXCHANGE_TEST_CODE_PATTERN.fullmatch(raw_code):
            excluded_exchange_test_basic += 1
            continue
        code = _code(raw_code)
        if code in seen_codes:
            raise SecurityNameError("stock_basic source contains duplicate security codes")
        seen_codes.add(code)
        name = _clean(row.name)
        if not name:
            raise SecurityNameError("stock_basic source contains a blank security name")
        fallback.append(
            {
                "ts_code": code,
                "name": name,
                "list_date": _date(row.list_date),
                "list_status": _clean(row.list_status),
            }
        )
    fallback.sort(key=lambda row: row["ts_code"])

    return {
        "schema_version": SCHEMA_VERSION,
        "source_cutoff": source_cutoff,
        "sources": source_identities,
        "quality": {
            "history_row_count": len(history),
            "history_security_count": len({row["ts_code"] for row in history}),
            "fallback_security_count": len(fallback),
            "excluded_bse_history_count": excluded_bse_history,
            "excluded_bse_basic_count": excluded_bse_basic,
            "excluded_exchange_test_basic_count": excluded_exchange_test_basic,
        },
        "history": history,
        "fallback": fallback,
    }


def _latest_source_identity(source_api: str, ledger_path: Path) -> dict[str, object]:
    with ledger_path.open(newline="", encoding="utf-8") as handle:
        selected = [row for row in csv.DictReader(handle) if row.get("source_api") == source_api]
    if not selected:
        raise SecurityNameError(f"no registered source batches for {source_api}")
    latest: dict[str, dict[str, str]] = {}
    for row in sorted(selected, key=lambda value: value["ingest_time"]):
        params = json.dumps(
            json.loads(row["params_json"]),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        latest[params] = row
    identity_rows = [
        {
            "batch_id": row["batch_id"],
            "params_json": json.loads(row["params_json"]),
            "row_count": int(row["row_count"]),
            "content_sha256": row["content_sha256"],
        }
        for row in sorted(latest.values(), key=lambda value: value["batch_id"])
    ]
    return {
        "source_api": source_api,
        "batch_count": len(identity_rows),
        "row_count": sum(int(row["row_count"]) for row in identity_rows),
        "latest_ingest_time": max(row["ingest_time"] for row in latest.values()),
        "identity_sha256": hashlib.sha256(_canonical(identity_rows)).hexdigest(),
    }


def _write_atomic(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_bytes(payload)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def write_projection(
    *,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    ledger_path: Path = DEFAULT_LEDGER_PATH,
) -> dict[str, object]:
    """Build one deterministic projection from hash-verified registered Parquet batches."""
    from shaiwei.ingest.catalog import load_latest_api

    identities = {
        source: _latest_source_identity(source, ledger_path)
        for source in ("tushare.namechange", "tushare.stock_basic")
    }
    source_cutoff = max(str(value["latest_ingest_time"]) for value in identities.values())
    document = project_catalog(
        load_latest_api("tushare.namechange", ledger_path=ledger_path),
        load_latest_api("tushare.stock_basic", ledger_path=ledger_path),
        source_cutoff=source_cutoff,
        source_identities=identities,
    )
    payload = _canonical(document)
    digest = hashlib.sha256(payload).hexdigest()
    relative_bundle = f"data/web/security_names/{digest}/bundle.json"
    bundle_path = output_root / digest / "bundle.json"
    if bundle_path.exists() and bundle_path.read_bytes() != payload:
        raise SecurityNameError("content-addressed security-name projection collision")
    if not bundle_path.exists():
        _write_atomic(bundle_path, payload)
    pointer = {
        "schema_version": POINTER_SCHEMA_VERSION,
        "bundle_path": relative_bundle,
        "bundle_sha256": digest,
    }
    _write_atomic(output_root / "current.json", _canonical(pointer))
    return {
        "status": "PASS",
        "bundle_path": relative_bundle,
        "bundle_sha256": digest,
        "source_cutoff": source_cutoff,
        **dict(document["quality"]),
    }


@dataclass(frozen=True)
class SecurityNameCatalog:
    source_cutoff: str
    history: dict[str, tuple[dict[str, str], ...]]
    fallback: dict[str, dict[str, str]]
    quality: dict[str, int]

    @classmethod
    def from_document(cls, document: dict[str, object]) -> "SecurityNameCatalog":
        if document.get("schema_version") != SCHEMA_VERSION:
            raise SecurityNameError("security-name projection schema differs")
        source_cutoff = _timestamp(document.get("source_cutoff"))
        history_by_code: dict[str, list[dict[str, str]]] = {}
        history_keys: set[tuple[str, str, str, str]] = set()
        for value in list(document.get("history", [])):
            row = dict(value)
            code = _code(row.get("ts_code"))
            name = _clean(row.get("name"))
            start = _date(row.get("start_date"))
            end = _date(row.get("end_date"), optional=True)
            if not name or (end and start > end):
                raise SecurityNameError("security-name projection contains an invalid interval")
            key = (code, name, start, end)
            if key in history_keys:
                raise SecurityNameError("security-name projection contains duplicate intervals")
            history_keys.add(key)
            history_by_code.setdefault(code, []).append(
                {"name": name, "start_date": start, "end_date": end}
            )
        fallback: dict[str, dict[str, str]] = {}
        for value in list(document.get("fallback", [])):
            row = dict(value)
            code = _code(row.get("ts_code"))
            if code in fallback:
                raise SecurityNameError("security-name projection fallback is not unique")
            name = _clean(row.get("name"))
            if not name:
                raise SecurityNameError("security-name projection contains a blank fallback")
            fallback[code] = {
                "name": name,
                "list_date": _date(row.get("list_date")),
            }
        quality = dict(document.get("quality", {}))
        required_quality = {
            "history_row_count",
            "history_security_count",
            "fallback_security_count",
            "excluded_bse_history_count",
            "excluded_bse_basic_count",
            "excluded_exchange_test_basic_count",
        }
        if set(quality) != required_quality:
            raise SecurityNameError("security-name projection quality fields differ")
        normalized_quality = {key: int(value) for key, value in quality.items()}
        if any(value < 0 for value in normalized_quality.values()):
            raise SecurityNameError("security-name projection quality count is invalid")
        if (
            normalized_quality["history_row_count"] != len(history_keys)
            or normalized_quality["history_security_count"] != len(history_by_code)
            or normalized_quality["fallback_security_count"] != len(fallback)
        ):
            raise SecurityNameError("security-name projection quality counts do not close")
        return cls(
            source_cutoff=source_cutoff,
            history={key: tuple(value) for key, value in history_by_code.items()},
            fallback=fallback,
            quality=normalized_quality,
        )

    def resolve(self, code: str, as_of: str) -> dict[str, str | None]:
        normalized_code = _code(code)
        normalized_date = _date(as_of)
        active = [
            row
            for row in self.history.get(normalized_code, ())
            if row["start_date"] <= normalized_date
            and (not row["end_date"] or normalized_date <= row["end_date"])
        ]
        if active:
            latest_start = max(row["start_date"] for row in active)
            names = {row["name"] for row in active if row["start_date"] == latest_start}
            if len(names) != 1:
                raise SecurityNameError("security-name projection is ambiguous at requested date")
            return {
                "security_name": next(iter(names)),
                "security_name_source": "NAMECHANGE_PIT",
                "security_name_status": "PASS",
            }
        current = self.fallback.get(normalized_code)
        if current is not None and current["list_date"] <= normalized_date:
            return {
                "security_name": current["name"],
                "security_name_source": "STOCK_BASIC_CURRENT_FALLBACK",
                "security_name_status": "WARN",
            }
        return {
            "security_name": None,
            "security_name_source": "UNAVAILABLE",
            "security_name_status": "NOT_READY",
        }


def main() -> int:
    print(json.dumps(write_projection(), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
