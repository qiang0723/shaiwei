"""Immutable G8 statutory fund evidence capture.

This module captures the regulator's unauthenticated HTTP source only.  It
cannot construct total returns, evaluate G8, or authorize scheduler use.
"""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import math
import os
import re
import sys
import time
import uuid
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import httpx
import yaml

from shaiwei.evaluation.g8 import comparator_codes
from shaiwei.ledger import append_g8_fund_evidence, sha256_file
from shaiwei.provenance import code_snapshot_sha256, git_head


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PROTOCOL_PATH = PROJECT_ROOT / "config" / "g8_fund_primary_capture_v1.yaml"
DEFAULT_LEDGER_PATH = PROJECT_ROOT / "ledger" / "g8_fund_evidence.csv"
PRIMARY_PROTOCOL_ID = "g8-fund-primary-capture-v1"
RECOVERY_PROTOCOL_ID = "g8-fund-primary-capture-recovery-v1"
ALLOWED_PROTOCOL_IDS = frozenset({PRIMARY_PROTOCOL_ID, RECOVERY_PROTOCOL_ID})
BUNDLE_SCHEMA = "g8-primary-evidence-bundle-v1"
NORMAL_STATUS = "PRIMARY_CAPTURED_UNAUTHENTICATED"
SOURCE_TRANSPORT = "HTTP_UNAUTHENTICATED"
SAFE_SEGMENT = re.compile(r"^[A-Za-z0-9_.=-]+$")

LEDGER_HEADER = (
    "evidence_id",
    "protocol_id",
    "request_id",
    "evidence_kind",
    "product_code",
    "period_start",
    "period_end",
    "parent_request_id",
    "captured_at",
    "first_http_status",
    "second_http_status",
    "first_body_sha256",
    "second_body_sha256",
    "bundle_path",
    "bundle_sha256",
    "parsed_row_count",
    "source_transport",
    "verification_status",
    "revision_of_evidence_id",
    "error_code",
    "operator",
)


class G8EvidenceError(RuntimeError):
    """Fail-closed G8 evidence error with a stable, non-sensitive code."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        rendered = f"{code}: {detail}" if detail else code
        super().__init__(rendered)


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_json(value: object) -> str:
    return _sha256_bytes(_canonical_json(value).encode("utf-8"))


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso_utc(value: datetime) -> str:
    if value.tzinfo is None:
        raise G8EvidenceError("NAIVE_CAPTURE_TIME")
    return value.astimezone(timezone.utc).isoformat()


def _safe_segment(value: str) -> str:
    if SAFE_SEGMENT.fullmatch(value) is None:
        raise G8EvidenceError("UNSAFE_PATH_SEGMENT")
    return value


def _empty(value: object) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _decimal_text(value: object) -> str:
    if isinstance(value, bool) or value is None:
        raise G8EvidenceError("NAV_VALUE_INVALID")
    rendered = str(value).strip()
    if not rendered:
        raise G8EvidenceError("NAV_VALUE_INVALID")
    try:
        parsed = Decimal(rendered)
    except InvalidOperation as error:
        raise G8EvidenceError("NAV_VALUE_INVALID") from error
    if not parsed.is_finite():
        raise G8EvidenceError("NAV_VALUE_INVALID")
    return rendered


def _integer(value: object, *, code: str) -> int:
    if isinstance(value, bool):
        raise G8EvidenceError(code)
    try:
        rendered = int(value)
    except (TypeError, ValueError) as error:
        raise G8EvidenceError(code) from error
    return rendered


def _mapping(value: object, *, code: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise G8EvidenceError(code)
    return value


def _read_yaml_mapping(path: Path, *, code: str) -> dict[str, Any]:
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise G8EvidenceError(code) from error
    if not isinstance(document, dict):
        raise G8EvidenceError(code)
    return document


def _validate_recovery_protocol(document: dict[str, Any], *, project_root: Path) -> None:
    binding = _mapping(document.get("recovery_binding"), code="RECOVERY_BINDING_MISSING")
    original_path = project_root / str(binding.get("original_protocol_path", ""))
    if (
        not original_path.is_file()
        or binding.get("original_protocol_sha256") != sha256_file(original_path)
    ):
        raise G8EvidenceError("RECOVERY_ORIGINAL_PROTOCOL_HASH_MISMATCH")
    original = _read_yaml_mapping(original_path, code="RECOVERY_ORIGINAL_PROTOCOL_INVALID")
    if original.get("protocol_id") != PRIMARY_PROTOCOL_ID:
        raise G8EvidenceError("RECOVERY_ORIGINAL_PROTOCOL_INVALID")

    claimed_head = str(binding.get("attempted_image_claimed_git_head", ""))
    implementation_head = str(binding.get("original_implementation_git_head", ""))
    if (
        re.fullmatch(r"[0-9a-f]{40}", claimed_head) is None
        or re.fullmatch(r"[0-9a-f]{40}", implementation_head) is None
        or claimed_head == implementation_head
        or binding.get("attempted_image_claimed_git_head_matches_repository") is not False
        or binding.get("original_failed_evidence_remains_immutable") is not True
        or binding.get("original_attempt_counts_for_recovery_acceptance") is not False
        or binding.get("changed_variable_only") != "execution_environment"
    ):
        raise G8EvidenceError("RECOVERY_BINDING_INVALID")

    source = dict(_mapping(document.get("source"), code="SOURCE_MISSING"))
    if source.pop("execution_environment", None) != "host_one_shot_no_env_file":
        raise G8EvidenceError("RECOVERY_EXECUTION_ENVIRONMENT_INVALID")
    if source.pop("post_capture_independent_verifier", None) != "immutable_docker_image_offline":
        raise G8EvidenceError("RECOVERY_VERIFIER_INVALID")
    if source != original.get("source"):
        raise G8EvidenceError("RECOVERY_SOURCE_SEMANTICS_CHANGED")

    acceptance = dict(_mapping(document.get("acceptance"), code="ACCEPTANCE_MISSING"))
    if acceptance.pop("original_failed_rows_preserved", None) != 1:
        raise G8EvidenceError("RECOVERY_FAILURE_PRESERVATION_INVALID")
    if acceptance != original.get("acceptance"):
        raise G8EvidenceError("RECOVERY_ACCEPTANCE_CHANGED")

    unchanged_sections = (
        "source_feasibility_binding",
        "scope",
        "nav_request",
        "dividend_request",
        "double_fetch",
        "storage",
        "products",
    )
    if any(document.get(key) != original.get(key) for key in unchanged_sections):
        raise G8EvidenceError("RECOVERY_SEMANTICS_CHANGED")


@dataclass(frozen=True)
class Product:
    code: str
    expected_name: str
    fund_id: int


@dataclass(frozen=True)
class G8CaptureProtocol:
    path: Path
    document: dict[str, Any]
    sha256: str
    products: tuple[Product, ...]
    capture_start: date
    capture_end: date
    data_root: Path
    ledger_path: Path

    @classmethod
    def load(cls, path: Path = DEFAULT_PROTOCOL_PATH, *, project_root: Path = PROJECT_ROOT) -> "G8CaptureProtocol":
        try:
            document = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as error:
            raise G8EvidenceError("PROTOCOL_UNREADABLE") from error
        if not isinstance(document, dict):
            raise G8EvidenceError("PROTOCOL_SCHEMA_INVALID")
        protocol_id = document.get("protocol_id")
        if protocol_id not in ALLOWED_PROTOCOL_IDS:
            raise G8EvidenceError("PROTOCOL_ID_INVALID")
        if document.get("status") != "RESULT_BEFORE_EXECUTION_FROZEN":
            raise G8EvidenceError("PROTOCOL_NOT_FROZEN")
        if document.get("execution_authorized") is not True:
            raise G8EvidenceError("EXECUTION_NOT_AUTHORIZED")
        if document.get("production_authorization") != "none":
            raise G8EvidenceError("PRODUCTION_SCOPE_INVALID")

        binding = _mapping(document.get("source_feasibility_binding"), code="SOURCE_BINDING_MISSING")
        source_path = project_root / str(binding.get("protocol_path", ""))
        if not source_path.is_file() or binding.get("protocol_sha256") != sha256_file(source_path):
            raise G8EvidenceError("SOURCE_PROTOCOL_HASH_MISMATCH")
        if binding.get("prior_verdict") != "GO_G8_1_PRIMARY_CAPTURE_ONLY":
            raise G8EvidenceError("SOURCE_GATE_NOT_GO")

        if protocol_id == RECOVERY_PROTOCOL_ID:
            _validate_recovery_protocol(document, project_root=project_root)

        scope = _mapping(document.get("scope"), code="SCOPE_MISSING")
        forbidden_true = (
            "strategy_results_access",
            "g8_evaluation",
            "total_return_construction",
            "manager_https_crosscheck",
            "fee_document_collection",
            "scheduler_integration",
            "web_changes",
        )
        if any(scope.get(key) is not False for key in forbidden_true):
            raise G8EvidenceError("SCOPE_EXPANSION_FORBIDDEN")
        try:
            capture_start = date.fromisoformat(str(scope["capture_start"]))
            capture_end = date.fromisoformat(str(scope["capture_end"]))
        except (KeyError, ValueError) as error:
            raise G8EvidenceError("CAPTURE_WINDOW_INVALID") from error
        if capture_start > capture_end:
            raise G8EvidenceError("CAPTURE_WINDOW_INVALID")
        expected_counts = {
            "product_count": 6,
            "expected_nav_requests": 6,
            "expected_usable_nav_rows": 48,
            "expected_dividend_requests": 48,
            "expected_logical_requests": 54,
            "expected_http_observations": 108,
        }
        if any(scope.get(key) != value for key, value in expected_counts.items()):
            raise G8EvidenceError("CAPTURE_COUNTS_INVALID")

        source = _mapping(document.get("source"), code="SOURCE_MISSING")
        if (
            source.get("scheme") != "http"
            or source.get("host") != "eid.csrc.gov.cn"
            or source.get("origin") != "http://eid.csrc.gov.cn"
            or source.get("authenticated_transport") is not False
            or source.get("trust_environment_proxy") is not False
            or source.get("automatic_retries") != 0
        ):
            raise G8EvidenceError("SOURCE_BOUNDARY_INVALID")

        raw_products = document.get("products")
        if not isinstance(raw_products, list):
            raise G8EvidenceError("PRODUCTS_INVALID")
        products = tuple(
            Product(
                code=str(_mapping(item, code="PRODUCT_INVALID").get("code", "")),
                expected_name=str(item.get("expected_name", "")),
                fund_id=_integer(item.get("fund_id"), code="PRODUCT_FUND_ID_INVALID"),
            )
            for item in raw_products
        )
        if tuple(product.code for product in products) != comparator_codes():
            raise G8EvidenceError("PRODUCT_ORDER_MISMATCH")
        if any(not product.expected_name or product.fund_id <= 0 for product in products):
            raise G8EvidenceError("PRODUCT_IDENTITY_INVALID")

        storage = _mapping(document.get("storage"), code="STORAGE_MISSING")
        data_root = project_root / str(storage.get("data_root", ""))
        ledger_path = project_root / str(storage.get("ledger_path", ""))
        if data_root != project_root / "data/g8/fund_evidence":
            raise G8EvidenceError("DATA_ROOT_INVALID")
        if ledger_path != project_root / "ledger/g8_fund_evidence.csv":
            raise G8EvidenceError("LEDGER_PATH_INVALID")
        return cls(
            path=path,
            document=document,
            sha256=sha256_file(path),
            products=products,
            capture_start=capture_start,
            capture_end=capture_end,
            data_root=data_root,
            ledger_path=ledger_path,
        )

    @property
    def protocol_id(self) -> str:
        return str(self.document["protocol_id"])

    @property
    def source_origin(self) -> str:
        return str(self.document["source"]["origin"])

    @property
    def timeout_seconds(self) -> float:
        return float(self.document["source"]["request_timeout_seconds"])

    @property
    def minimum_interval_seconds(self) -> float:
        return float(self.document["source"]["minimum_request_start_interval_seconds"])

    @property
    def safe_response_headers(self) -> frozenset[str]:
        return frozenset(str(item).lower() for item in self.document["storage"]["response_headers_allowlist"])

    @property
    def operator(self) -> str:
        if self.protocol_id == RECOVERY_PROTOCOL_ID:
            return "host-g8-evidence-recovery"
        return "docker-g8-evidence"


@dataclass(frozen=True)
class RequestSpec:
    protocol_id: str
    origin: str
    method: str
    path: str
    params: dict[str, str]
    form: dict[str, str]
    evidence_kind: str
    product: Product
    period_start: str
    period_end: str
    parent_request_id: str = ""

    @property
    def identity_document(self) -> dict[str, object]:
        return {
            "protocol_id": self.protocol_id,
            "origin": self.origin,
            "method": self.method,
            "path": self.path,
            "params": self.params,
            "form": self.form,
            "evidence_kind": self.evidence_kind,
            "product_code": self.product.code,
            "period_start": self.period_start,
            "period_end": self.period_end,
            "parent_request_id": self.parent_request_id,
        }

    @property
    def request_id(self) -> str:
        return _sha256_json(self.identity_document)


@dataclass(frozen=True)
class Observation:
    received_at: str
    http_status: int
    headers: tuple[tuple[str, str], ...]
    body: bytes
    error_class: str

    @property
    def body_sha256(self) -> str:
        return _sha256_bytes(self.body)

    def as_document(self) -> dict[str, object]:
        return {
            "received_at": self.received_at,
            "http_status": self.http_status,
            "headers": [list(item) for item in self.headers],
            "body_sha256": self.body_sha256,
            "body_base64": base64.b64encode(self.body).decode("ascii"),
            "error_class": self.error_class,
        }


@dataclass(frozen=True)
class CaptureResult:
    evidence_id: str
    request_id: str
    evidence_kind: str
    product_code: str
    bundle_path: Path
    bundle_sha256: str
    parsed_records: tuple[dict[str, object], ...]
    appended: bool


def nav_request_spec(protocol: G8CaptureProtocol, product: Product) -> RequestSpec:
    start = protocol.capture_start.isoformat()
    end = protocol.capture_end.isoformat()
    ao_data = [
        {"name": "sEcho", "value": 1},
        {"name": "iDisplayStart", "value": 0},
        {"name": "iDisplayLength", "value": 100},
        {"name": "fundType", "value": "all"},
        {"name": "fundCompanyShortName", "value": ""},
        {"name": "fundCode", "value": product.code},
        {"name": "fundName", "value": ""},
        {"name": "startDate", "value": start},
        {"name": "endDate", "value": end},
    ]
    return RequestSpec(
        protocol_id=protocol.protocol_id,
        origin=protocol.source_origin,
        method="GET",
        path="/fund/disclose/getPublicFundJZInfoMore.do",
        params={"aoData": _canonical_json(ao_data)},
        form={},
        evidence_kind="NAV_RANGE",
        product=product,
        period_start=start,
        period_end=end,
    )


def dividend_request_spec(
    protocol: G8CaptureProtocol,
    product: Product,
    nav_record: dict[str, object],
    *,
    parent_request_id: str,
) -> RequestSpec:
    valuation_date = str(nav_record["valuation_date"])
    return RequestSpec(
        protocol_id=protocol.protocol_id,
        origin=protocol.source_origin,
        method="POST",
        path="/fund/disclose/getDividendInfo.do",
        params={},
        form={
            "uploadDetailId": str(nav_record["upload_detail_id"]),
            "fundName": product.expected_name,
            "fundCode": product.code,
            "thisLevel": "1",
            "thisName": product.expected_name,
            "thisCode": product.code,
        },
        evidence_kind="DIVIDEND_NOTE",
        product=product,
        period_start=valuation_date,
        period_end=valuation_date,
        parent_request_id=parent_request_id,
    )


def parse_nav_response(
    body: bytes,
    *,
    product: Product,
    capture_start: date,
    capture_end: date,
    expected_rows: int,
) -> tuple[dict[str, object], ...]:
    try:
        document = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise G8EvidenceError("NAV_JSON_INVALID") from error
    root = _mapping(document, code="NAV_ROOT_INVALID")
    raw_rows = root.get("aaData")
    if not isinstance(raw_rows, list):
        raise G8EvidenceError("NAV_ROWS_MISSING")
    if len(raw_rows) > 100:
        raise G8EvidenceError("NAV_PAGE_OVERFLOW")
    for count_key in ("iTotalRecords", "iTotalDisplayRecords"):
        if _integer(root.get(count_key), code="NAV_COUNT_INVALID") != len(raw_rows):
            raise G8EvidenceError("NAV_PAGE_INCOMPLETE")

    usable: list[dict[str, object]] = []
    master_dates: list[str] = []
    for raw in raw_rows:
        row = _mapping(raw, code="NAV_ROW_INVALID")
        if str(row.get("code", "")) != product.code:
            raise G8EvidenceError("NAV_PRODUCT_CODE_MISMATCH")
        valuation_text = str(row.get("valuationDate", ""))
        try:
            valuation = date.fromisoformat(valuation_text)
        except ValueError as error:
            raise G8EvidenceError("NAV_DATE_INVALID") from error
        if not capture_start <= valuation <= capture_end:
            raise G8EvidenceError("NAV_DATE_OUT_OF_RANGE")
        classification = _mapping(row.get("classification"), code="NAV_CLASSIFICATION_INVALID")
        classification_code = str(classification.get("code", ""))
        if classification_code == "2030-1030":
            if not _empty(row.get("shareNetValue")) or not _empty(row.get("totalNetValue")):
                raise G8EvidenceError("NAV_MASTER_ROW_NONEMPTY")
            master_dates.append(valuation_text)
            continue
        if classification_code != "2030-1010":
            raise G8EvidenceError("NAV_UNKNOWN_CLASSIFICATION")
        if str(row.get("shortName", "")) != product.expected_name:
            raise G8EvidenceError("NAV_PRODUCT_NAME_MISMATCH")
        fund = _mapping(row.get("fund"), code="NAV_FUND_IDENTITY_INVALID")
        fund_id = _integer(fund.get("idStr"), code="NAV_FUND_ID_INVALID")
        if fund_id != product.fund_id:
            raise G8EvidenceError("NAV_FUND_ID_MISMATCH")
        upload = _mapping(row.get("uploadInfoDetail"), code="NAV_UPLOAD_IDENTITY_INVALID")
        upload_id = _integer(upload.get("idStr"), code="NAV_UPLOAD_ID_INVALID")
        if upload_id <= 0:
            raise G8EvidenceError("NAV_UPLOAD_ID_INVALID")
        usable.append(
            {
                "product_code": product.code,
                "product_name": product.expected_name,
                "fund_id": fund_id,
                "classification_code": classification_code,
                "valuation_date": valuation_text,
                "share_net_value": _decimal_text(row.get("shareNetValue")),
                "total_net_value": _decimal_text(row.get("totalNetValue")),
                "upload_detail_id": upload_id,
                "source_row_sha256": _sha256_json(row),
            }
        )

    usable.sort(key=lambda row: (str(row["valuation_date"]), int(row["upload_detail_id"])))
    dates = [str(row["valuation_date"]) for row in usable]
    upload_ids = [int(row["upload_detail_id"]) for row in usable]
    if len(usable) != expected_rows:
        raise G8EvidenceError("NAV_USABLE_COUNT_MISMATCH")
    if len(dates) != len(set(dates)):
        raise G8EvidenceError("NAV_DUPLICATE_PRODUCT_DATE")
    if len(upload_ids) != len(set(upload_ids)):
        raise G8EvidenceError("NAV_DUPLICATE_UPLOAD_ID")
    if sorted(master_dates) != dates:
        raise G8EvidenceError("NAV_MASTER_DATE_COVERAGE_MISMATCH")
    return tuple(usable)


def parse_dividend_response(
    body: bytes,
    *,
    product: Product,
    valuation_date: str,
    upload_detail_id: int,
) -> tuple[dict[str, object], ...]:
    try:
        document = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise G8EvidenceError("DIVIDEND_JSON_INVALID") from error
    root = _mapping(document, code="DIVIDEND_ROOT_INVALID")
    if str(root.get("fundCode", "")) != product.code:
        raise G8EvidenceError("DIVIDEND_PRODUCT_CODE_MISMATCH")
    if str(root.get("fundName", "")) != product.expected_name:
        raise G8EvidenceError("DIVIDEND_PRODUCT_NAME_MISMATCH")
    if str(root.get("isFenji", "")).lower() not in {"true", "false"}:
        raise G8EvidenceError("DIVIDEND_CLASSIFICATION_INVALID")
    special = _mapping(root.get("specialPoint"), code="DIVIDEND_SPECIAL_POINT_INVALID")
    required = ("fenhongjinE", "changwai", "changnei", "remark", "specialPoint")
    if any(key not in special for key in required):
        raise G8EvidenceError("DIVIDEND_FIELDS_MISSING")
    for key in required:
        if special[key] is not None and not isinstance(special[key], (str, int, float)):
            raise G8EvidenceError("DIVIDEND_FIELD_TYPE_INVALID")
        if isinstance(special[key], float) and not math.isfinite(special[key]):
            raise G8EvidenceError("DIVIDEND_FIELD_TYPE_INVALID")
    return (
        {
            "product_code": product.code,
            "product_name": product.expected_name,
            "valuation_date": valuation_date,
            "upload_detail_id": upload_detail_id,
            "is_fenji": str(root["isFenji"]).lower(),
            "fenhongjine": special["fenhongjinE"],
            "changwai": special["changwai"],
            "changnei": special["changnei"],
            "remark": special["remark"],
            "special_point": special["specialPoint"],
        },
    )


def _read_ledger(path: Path) -> list[dict[str, str]]:
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            if tuple(reader.fieldnames or ()) != LEDGER_HEADER:
                raise G8EvidenceError("LEDGER_HEADER_MISMATCH")
            rows = list(reader)
    except OSError as error:
        raise G8EvidenceError("LEDGER_UNREADABLE") from error
    evidence_ids = [row["evidence_id"] for row in rows]
    if len(evidence_ids) != len(set(evidence_ids)):
        raise G8EvidenceError("LEDGER_DUPLICATE_EVIDENCE_ID")
    return rows


def _relative_project_path(path: Path, project_root: Path) -> str:
    try:
        return path.resolve().relative_to(project_root.resolve()).as_posix()
    except ValueError as error:
        raise G8EvidenceError("BUNDLE_PATH_OUTSIDE_PROJECT") from error


def _atomic_write_new(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, path)
    except FileExistsError as error:
        raise G8EvidenceError("BUNDLE_ALREADY_EXISTS_WITHOUT_LEDGER") from error
    finally:
        temporary.unlink(missing_ok=True)


def _load_bundle(path: Path) -> dict[str, Any]:
    try:
        document = json.loads(path.read_bytes())
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as error:
        raise G8EvidenceError("BUNDLE_UNREADABLE") from error
    if not isinstance(document, dict) or document.get("schema_version") != BUNDLE_SCHEMA:
        raise G8EvidenceError("BUNDLE_SCHEMA_INVALID")
    return document


def _verify_recovery_failure_binding(
    protocol: G8CaptureProtocol,
    *,
    ledger_path: Path,
    project_root: Path,
) -> bool:
    if protocol.protocol_id != RECOVERY_PROTOCOL_ID:
        return False
    binding = _mapping(protocol.document.get("recovery_binding"), code="RECOVERY_BINDING_MISSING")
    try:
        ledger_lines = ledger_path.read_bytes().splitlines(keepends=True)
    except OSError as error:
        raise G8EvidenceError("LEDGER_UNREADABLE") from error
    if len(ledger_lines) < 2:
        raise G8EvidenceError("RECOVERY_FAILURE_LEDGER_PREFIX_MISSING")
    frozen_prefix = b"".join(ledger_lines[:2])
    if _sha256_bytes(frozen_prefix) != binding.get("failure_ledger_sha256"):
        raise G8EvidenceError("RECOVERY_FAILURE_LEDGER_PREFIX_MISMATCH")

    rows = _read_ledger(ledger_path)
    matches = [row for row in rows if row["evidence_id"] == binding.get("failure_evidence_id")]
    if len(matches) != 1:
        raise G8EvidenceError("RECOVERY_FAILURE_ROW_MISSING")
    row = matches[0]
    empty_body_sha256 = _sha256_bytes(b"")
    expected_statuses = [
        _integer(row["first_http_status"], code="RECOVERY_FAILURE_HTTP_STATUS_INVALID"),
        _integer(row["second_http_status"], code="RECOVERY_FAILURE_HTTP_STATUS_INVALID"),
    ]
    if (
        row["protocol_id"] != PRIMARY_PROTOCOL_ID
        or row["verification_status"] != "QUARANTINED_HTTP_STATUS"
        or row["error_code"] != "HTTP_STATUS_INVALID"
        or expected_statuses != binding.get("failure_http_statuses")
        or row["first_body_sha256"] != empty_body_sha256
        or row["second_body_sha256"] != empty_body_sha256
        or binding.get("failure_bodies_empty") is not True
        or row["bundle_sha256"] != binding.get("failure_bundle_sha256")
    ):
        raise G8EvidenceError("RECOVERY_FAILURE_ROW_MISMATCH")

    relative_bundle = Path(row["bundle_path"])
    if relative_bundle.is_absolute():
        raise G8EvidenceError("RECOVERY_FAILURE_BUNDLE_PATH_INVALID")
    bundle_path = (project_root / relative_bundle).resolve()
    allowed_root = (project_root / "data/g8/fund_evidence/bundles").resolve()
    if not bundle_path.is_relative_to(allowed_root):
        raise G8EvidenceError("RECOVERY_FAILURE_BUNDLE_PATH_INVALID")
    if not bundle_path.is_file() or sha256_file(bundle_path) != binding.get("failure_bundle_sha256"):
        raise G8EvidenceError("RECOVERY_FAILURE_BUNDLE_HASH_MISMATCH")
    bundle = _load_bundle(bundle_path)
    observations = bundle.get("observations")
    if not isinstance(observations, list) or len(observations) != 2:
        raise G8EvidenceError("RECOVERY_FAILURE_BUNDLE_MISMATCH")
    decoded = [
        _decode_observation(item, allowed_headers=protocol.safe_response_headers)
        for item in observations
    ]
    if (
        bundle.get("protocol_id") != PRIMARY_PROTOCOL_ID
        or bundle.get("protocol_sha256") != binding.get("original_protocol_sha256")
        or bundle.get("evidence_id") != row["evidence_id"]
        or bundle.get("request_id") != row["request_id"]
        or bundle.get("verification_status") != row["verification_status"]
        or bundle.get("error_code") != row["error_code"]
        or decoded != [(empty_body_sha256, 502), (empty_body_sha256, 502)]
    ):
        raise G8EvidenceError("RECOVERY_FAILURE_BUNDLE_MISMATCH")
    return True


class EvidenceCollector:
    def __init__(
        self,
        *,
        protocol: G8CaptureProtocol,
        client: httpx.Client,
        project_root: Path = PROJECT_ROOT,
        data_root: Path | None = None,
        ledger_path: Path | None = None,
        now: Callable[[], datetime] = _utc_now,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
        minimum_interval_seconds: float | None = None,
        execution_code_sha256: str | None = None,
        execution_git_head: str | None = None,
    ) -> None:
        self.protocol = protocol
        self.client = client
        self.project_root = project_root.resolve()
        self.data_root = (data_root or protocol.data_root).resolve()
        self.ledger_path = (ledger_path or protocol.ledger_path).resolve()
        self.now = now
        self.sleep = sleep
        self.monotonic = monotonic
        self.minimum_interval_seconds = (
            protocol.minimum_interval_seconds
            if minimum_interval_seconds is None
            else minimum_interval_seconds
        )
        self.execution_code_sha256 = execution_code_sha256 or code_snapshot_sha256()
        self.execution_git_head = execution_git_head or git_head()
        self._last_request_started: float | None = None
        _read_ledger(self.ledger_path)
        _verify_recovery_failure_binding(
            protocol,
            ledger_path=self.ledger_path,
            project_root=self.project_root,
        )
        if self.minimum_interval_seconds < 0:
            raise G8EvidenceError("REQUEST_INTERVAL_INVALID")
        if re.fullmatch(r"[0-9a-f]{64}", self.execution_code_sha256) is None:
            raise G8EvidenceError("CODE_SNAPSHOT_INVALID")
        if re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", self.execution_git_head) is None:
            raise G8EvidenceError("GIT_HEAD_INVALID")

    def _wait_for_rate_limit(self) -> None:
        current = self.monotonic()
        if self._last_request_started is not None:
            remaining = self.minimum_interval_seconds - (current - self._last_request_started)
            if remaining > 0:
                self.sleep(remaining)
                current = self.monotonic()
        self._last_request_started = current

    def _observe(self, spec: RequestSpec) -> Observation:
        self._wait_for_rate_limit()
        try:
            response = self.client.request(
                spec.method,
                spec.path,
                params=spec.params or None,
                data=spec.form or None,
            )
            headers = tuple(
                sorted(
                    (key.lower(), value)
                    for key, value in response.headers.multi_items()
                    if key.lower() in self.protocol.safe_response_headers
                )
            )
            return Observation(
                received_at=_iso_utc(self.now()),
                http_status=response.status_code,
                headers=headers,
                body=response.content,
                error_class="",
            )
        except httpx.RequestError as error:
            return Observation(
                received_at=_iso_utc(self.now()),
                http_status=0,
                headers=(),
                body=b"",
                error_class=type(error).__name__,
            )

    def capture(
        self,
        spec: RequestSpec,
        parser: Callable[[bytes], tuple[dict[str, object], ...]],
    ) -> CaptureResult:
        observations = (self._observe(spec), self._observe(spec))
        first, second = observations
        parsed: tuple[dict[str, object], ...] = ()
        status = NORMAL_STATUS
        error_code = ""
        if first.error_class or second.error_class:
            status = "QUARANTINED_TRANSPORT_ERROR"
            error_code = "TRANSPORT_ERROR"
        elif first.http_status != 200 or second.http_status != 200:
            status = "QUARANTINED_HTTP_STATUS"
            error_code = "HTTP_STATUS_INVALID"
        elif first.body != second.body:
            status = "QUARANTINED_DOUBLE_FETCH_MISMATCH"
            error_code = "DOUBLE_FETCH_MISMATCH"
        else:
            try:
                parsed = parser(first.body)
            except G8EvidenceError as error:
                status = "QUARANTINED_SCHEMA"
                error_code = error.code

        rows = _read_ledger(self.ledger_path)
        prior_rows = [row for row in rows if row["request_id"] == spec.request_id]
        pair = (first.body_sha256, second.body_sha256)
        same_rows = [
            row
            for row in prior_rows
            if (row["first_body_sha256"], row["second_body_sha256"]) == pair
        ]
        different_rows = [row for row in prior_rows if row not in same_rows]
        if status == NORMAL_STATUS and different_rows:
            status = "QUARANTINED_REVISION"
            error_code = "PRIOR_REQUEST_CONTENT_DIFFERS"
        revision_of = different_rows[-1]["evidence_id"] if different_rows else ""
        evidence_id = _sha256_json(
            {
                "protocol_id": self.protocol.protocol_id,
                "request_id": spec.request_id,
                "first_body_sha256": first.body_sha256,
                "second_body_sha256": second.body_sha256,
            }
        )

        if same_rows:
            row = same_rows[-1]
            if row["evidence_id"] != evidence_id or row["verification_status"] != status:
                raise G8EvidenceError("EXISTING_EVIDENCE_STATUS_CONFLICT")
            bundle_path = self.project_root / row["bundle_path"]
            if not bundle_path.is_file() or sha256_file(bundle_path) != row["bundle_sha256"]:
                raise G8EvidenceError("EXISTING_BUNDLE_HASH_MISMATCH")
            document = _load_bundle(bundle_path)
            existing_parsed = document.get("parsed_records")
            if not isinstance(existing_parsed, list):
                raise G8EvidenceError("EXISTING_BUNDLE_PARSED_INVALID")
            result = CaptureResult(
                evidence_id=evidence_id,
                request_id=spec.request_id,
                evidence_kind=spec.evidence_kind,
                product_code=spec.product.code,
                bundle_path=bundle_path,
                bundle_sha256=row["bundle_sha256"],
                parsed_records=tuple(existing_parsed),
                appended=False,
            )
            if status != NORMAL_STATUS:
                raise G8EvidenceError(error_code or "QUARANTINED_EVIDENCE_REUSED")
            return result

        bundle = {
            "schema_version": BUNDLE_SCHEMA,
            "protocol_id": self.protocol.protocol_id,
            "protocol_sha256": self.protocol.sha256,
            "execution": {
                "code_snapshot_sha256": self.execution_code_sha256,
                "git_head": self.execution_git_head,
            },
            "evidence_id": evidence_id,
            "request_id": spec.request_id,
            "request": spec.identity_document,
            "observations": [observation.as_document() for observation in observations],
            "parsed_records": list(parsed),
            "verification_status": status,
            "revision_of_evidence_id": revision_of,
            "error_code": error_code,
        }
        payload = (_canonical_json(bundle) + "\n").encode("utf-8")
        bundle_path = (
            self.data_root
            / "bundles"
            / _safe_segment(spec.evidence_kind.lower())
            / _safe_segment(spec.product.code)
            / f"{evidence_id}.json"
        )
        _atomic_write_new(bundle_path, payload)
        bundle_sha256 = sha256_file(bundle_path)
        bundle_relative = _relative_project_path(bundle_path, self.project_root)
        append_g8_fund_evidence(
            path=self.ledger_path,
            evidence_id=evidence_id,
            protocol_id=self.protocol.protocol_id,
            request_id=spec.request_id,
            evidence_kind=spec.evidence_kind,
            product_code=spec.product.code,
            period_start=spec.period_start,
            period_end=spec.period_end,
            parent_request_id=spec.parent_request_id,
            captured_at=first.received_at,
            first_http_status=first.http_status,
            second_http_status=second.http_status,
            first_body_sha256=first.body_sha256,
            second_body_sha256=second.body_sha256,
            bundle_path=bundle_relative,
            bundle_sha256=bundle_sha256,
            parsed_row_count=len(parsed),
            source_transport=SOURCE_TRANSPORT,
            verification_status=status,
            revision_of_evidence_id=revision_of,
            error_code=error_code,
            operator=self.protocol.operator,
        )
        result = CaptureResult(
            evidence_id=evidence_id,
            request_id=spec.request_id,
            evidence_kind=spec.evidence_kind,
            product_code=spec.product.code,
            bundle_path=bundle_path,
            bundle_sha256=bundle_sha256,
            parsed_records=parsed,
            appended=True,
        )
        if status != NORMAL_STATUS:
            raise G8EvidenceError(error_code or "EVIDENCE_QUARANTINED")
        return result


def _decode_observation(document: object, *, allowed_headers: frozenset[str]) -> tuple[str, int]:
    observation = _mapping(document, code="BUNDLE_OBSERVATION_INVALID")
    body_base64 = observation.get("body_base64")
    if not isinstance(body_base64, str):
        raise G8EvidenceError("BUNDLE_BODY_MISSING")
    try:
        body = base64.b64decode(body_base64, validate=True)
    except ValueError as error:
        raise G8EvidenceError("BUNDLE_BODY_BASE64_INVALID") from error
    digest = _sha256_bytes(body)
    if observation.get("body_sha256") != digest:
        raise G8EvidenceError("BUNDLE_BODY_HASH_MISMATCH")
    status = _integer(observation.get("http_status"), code="BUNDLE_HTTP_STATUS_INVALID")
    headers = observation.get("headers")
    if not isinstance(headers, list):
        raise G8EvidenceError("BUNDLE_HEADERS_INVALID")
    forbidden = {"set-cookie", "authorization", "proxy-authenticate"}
    for item in headers:
        if (
            not isinstance(item, list)
            or len(item) != 2
            or str(item[0]).lower() in forbidden
            or str(item[0]).lower() not in allowed_headers
        ):
            raise G8EvidenceError("BUNDLE_HEADERS_INVALID")
    return digest, status


def verify_evidence_ledger(
    protocol: G8CaptureProtocol,
    *,
    ledger_path: Path | None = None,
    project_root: Path = PROJECT_ROOT,
) -> dict[str, object]:
    path = ledger_path or protocol.ledger_path
    rows = _read_ledger(path)
    recovery_failure_preserved = _verify_recovery_failure_binding(
        protocol,
        ledger_path=path,
        project_root=project_root.resolve(),
    )
    relevant = [row for row in rows if row["protocol_id"] == protocol.protocol_id]
    bundle_manifest: list[dict[str, str]] = []
    kind_counts: dict[str, int] = {}
    parsed_counts: dict[str, int] = {}
    status_counts: dict[str, int] = {}
    execution_snapshots: set[str] = set()
    execution_heads: set[str] = set()
    for row in relevant:
        if Path(row["bundle_path"]).is_absolute():
            raise G8EvidenceError("LEDGER_ABSOLUTE_PATH_FORBIDDEN")
        bundle_path = (project_root / row["bundle_path"]).resolve()
        allowed_root = (project_root / "data/g8/fund_evidence/bundles").resolve()
        if not bundle_path.is_relative_to(allowed_root):
            raise G8EvidenceError("LEDGER_BUNDLE_PATH_OUTSIDE_ROOT")
        if not bundle_path.is_file() or sha256_file(bundle_path) != row["bundle_sha256"]:
            raise G8EvidenceError("LEDGER_BUNDLE_HASH_MISMATCH")
        bundle = _load_bundle(bundle_path)
        if bundle.get("protocol_id") != protocol.protocol_id or bundle.get("protocol_sha256") != protocol.sha256:
            raise G8EvidenceError("BUNDLE_PROTOCOL_MISMATCH")
        request = bundle.get("request")
        if _sha256_json(request) != row["request_id"] or bundle.get("request_id") != row["request_id"]:
            raise G8EvidenceError("BUNDLE_REQUEST_ID_MISMATCH")
        request_mapping = _mapping(request, code="BUNDLE_REQUEST_INVALID")
        request_ledger_fields = {
            "protocol_id": row["protocol_id"],
            "evidence_kind": row["evidence_kind"],
            "product_code": row["product_code"],
            "period_start": row["period_start"],
            "period_end": row["period_end"],
            "parent_request_id": row["parent_request_id"],
        }
        if any(request_mapping.get(key) != value for key, value in request_ledger_fields.items()):
            raise G8EvidenceError("BUNDLE_REQUEST_LEDGER_MISMATCH")
        observations = bundle.get("observations")
        if not isinstance(observations, list) or len(observations) != 2:
            raise G8EvidenceError("BUNDLE_OBSERVATION_COUNT_MISMATCH")
        decoded = [
            _decode_observation(item, allowed_headers=protocol.safe_response_headers)
            for item in observations
        ]
        if decoded[0] != (row["first_body_sha256"], int(row["first_http_status"])):
            raise G8EvidenceError("BUNDLE_FIRST_OBSERVATION_MISMATCH")
        if decoded[1] != (row["second_body_sha256"], int(row["second_http_status"])):
            raise G8EvidenceError("BUNDLE_SECOND_OBSERVATION_MISMATCH")
        expected_evidence_id = _sha256_json(
            {
                "protocol_id": protocol.protocol_id,
                "request_id": row["request_id"],
                "first_body_sha256": row["first_body_sha256"],
                "second_body_sha256": row["second_body_sha256"],
            }
        )
        if row["evidence_id"] != expected_evidence_id or bundle.get("evidence_id") != expected_evidence_id:
            raise G8EvidenceError("BUNDLE_EVIDENCE_ID_MISMATCH")
        parsed = bundle.get("parsed_records")
        if not isinstance(parsed, list) or len(parsed) != int(row["parsed_row_count"]):
            raise G8EvidenceError("BUNDLE_PARSED_COUNT_MISMATCH")
        if bundle.get("verification_status") != row["verification_status"]:
            raise G8EvidenceError("BUNDLE_STATUS_MISMATCH")
        if bundle.get("revision_of_evidence_id") != row["revision_of_evidence_id"]:
            raise G8EvidenceError("BUNDLE_REVISION_ID_MISMATCH")
        if bundle.get("error_code") != row["error_code"]:
            raise G8EvidenceError("BUNDLE_ERROR_CODE_MISMATCH")
        if row["source_transport"] != SOURCE_TRANSPORT:
            raise G8EvidenceError("LEDGER_SOURCE_TRANSPORT_INVALID")
        if row["verification_status"] == NORMAL_STATUS and (
            decoded[0][1] != 200
            or decoded[1][1] != 200
            or decoded[0][0] != decoded[1][0]
            or row["error_code"]
            or row["revision_of_evidence_id"]
        ):
            raise G8EvidenceError("NORMAL_EVIDENCE_INVARIANT_INVALID")
        execution = _mapping(bundle.get("execution"), code="BUNDLE_EXECUTION_MISSING")
        execution_snapshot = str(execution.get("code_snapshot_sha256", ""))
        execution_head = str(execution.get("git_head", ""))
        if re.fullmatch(r"[0-9a-f]{64}", execution_snapshot) is None:
            raise G8EvidenceError("BUNDLE_CODE_SNAPSHOT_INVALID")
        if re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", execution_head) is None:
            raise G8EvidenceError("BUNDLE_GIT_HEAD_INVALID")
        execution_snapshots.add(execution_snapshot)
        execution_heads.add(execution_head)
        kind = row["evidence_kind"]
        status = row["verification_status"]
        kind_counts[kind] = kind_counts.get(kind, 0) + 1
        parsed_counts[kind] = parsed_counts.get(kind, 0) + len(parsed)
        status_counts[status] = status_counts.get(status, 0) + 1
        bundle_manifest.append(
            {
                "evidence_id": row["evidence_id"],
                "bundle_path": row["bundle_path"],
                "bundle_sha256": row["bundle_sha256"],
            }
        )
    if len(execution_snapshots) > 1 or len(execution_heads) > 1:
        raise G8EvidenceError("MULTIPLE_EXECUTION_IDENTITIES")
    return {
        "ledger_rows": len(relevant),
        "ledger_sha256": sha256_file(path),
        "kind_counts": dict(sorted(kind_counts.items())),
        "parsed_counts": dict(sorted(parsed_counts.items())),
        "status_counts": dict(sorted(status_counts.items())),
        "bundle_manifest_sha256": _sha256_json(bundle_manifest),
        "execution_code_sha256": next(iter(execution_snapshots), ""),
        "execution_git_head": next(iter(execution_heads), ""),
        "recovery_failure_preserved": recovery_failure_preserved,
    }


def _assert_acceptance(protocol: G8CaptureProtocol, verification: dict[str, object]) -> None:
    expected = protocol.document["acceptance"]
    if verification["ledger_rows"] != expected["ledger_rows"]:
        raise G8EvidenceError("ACCEPTANCE_LEDGER_ROWS_MISMATCH")
    if verification["kind_counts"] != {
        "DIVIDEND_NOTE": expected["dividend_evidence_rows"],
        "NAV_RANGE": expected["nav_evidence_rows"],
    }:
        raise G8EvidenceError("ACCEPTANCE_KIND_COUNTS_MISMATCH")
    if verification["parsed_counts"] != {
        "DIVIDEND_NOTE": expected["dividend_evidence_rows"],
        "NAV_RANGE": expected["usable_nav_rows"],
    }:
        raise G8EvidenceError("ACCEPTANCE_PARSED_COUNTS_MISMATCH")
    if verification["status_counts"] != {NORMAL_STATUS: expected["ledger_rows"]}:
        raise G8EvidenceError("ACCEPTANCE_STATUS_COUNTS_MISMATCH")
    if (
        protocol.protocol_id == RECOVERY_PROTOCOL_ID
        and verification["recovery_failure_preserved"] is not True
    ):
        raise G8EvidenceError("ACCEPTANCE_RECOVERY_FAILURE_NOT_PRESERVED")


def run_capture(collector: EvidenceCollector) -> dict[str, object]:
    results: list[CaptureResult] = []
    expected_rows = int(collector.protocol.document["nav_request"]["expected_usable_rows_per_product"])
    for product in collector.protocol.products:
        nav_spec = nav_request_spec(collector.protocol, product)
        nav_result = collector.capture(
            nav_spec,
            lambda body, product=product: parse_nav_response(
                body,
                product=product,
                capture_start=collector.protocol.capture_start,
                capture_end=collector.protocol.capture_end,
                expected_rows=expected_rows,
            ),
        )
        results.append(nav_result)
        for nav_record in nav_result.parsed_records:
            dividend_spec = dividend_request_spec(
                collector.protocol,
                product,
                nav_record,
                parent_request_id=nav_result.request_id,
            )
            upload_id = int(nav_record["upload_detail_id"])
            valuation_date = str(nav_record["valuation_date"])
            results.append(
                collector.capture(
                    dividend_spec,
                    lambda body, product=product, valuation_date=valuation_date, upload_id=upload_id: (
                        parse_dividend_response(
                            body,
                            product=product,
                            valuation_date=valuation_date,
                            upload_detail_id=upload_id,
                        )
                    ),
                )
            )
    verification = verify_evidence_ledger(
        collector.protocol,
        ledger_path=collector.ledger_path,
        project_root=collector.project_root,
    )
    _assert_acceptance(collector.protocol, verification)
    appended = sum(result.appended for result in results)
    return {
        "protocol_id": collector.protocol.protocol_id,
        "protocol_sha256": collector.protocol.sha256,
        "execution_code_sha256": collector.execution_code_sha256,
        "execution_git_head": collector.execution_git_head,
        "logical_requests": len(results),
        "http_observations": len(results) * 2,
        "appended_evidence": appended,
        "reused_evidence": len(results) - appended,
        **verification,
        "g8_status": "NOT_READY",
        "production_authorization": "none",
        "verdict": "GO_G8_2_CROSSCHECK_AND_FEE_LINEAGE_ONLY",
    }


def _build_live_client(protocol: G8CaptureProtocol) -> httpx.Client:
    return httpx.Client(
        base_url=protocol.source_origin,
        headers={
            "Accept": "application/json",
            "Accept-Encoding": "identity",
            "User-Agent": "shaiwei-g8-evidence/1",
        },
        timeout=protocol.timeout_seconds,
        trust_env=False,
        follow_redirects=False,
    )


def _print_json(value: object, *, stream: Any = sys.stdout) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True), file=stream)


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL_PATH)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        protocol = G8CaptureProtocol.load(args.protocol)
        if args.verify_only:
            verification = verify_evidence_ledger(protocol)
            _assert_acceptance(protocol, verification)
            _print_json(
                {
                    "protocol_id": protocol.protocol_id,
                    **verification,
                    "g8_status": "NOT_READY",
                    "production_authorization": "none",
                    "verdict": "GO_G8_2_CROSSCHECK_AND_FEE_LINEAGE_ONLY",
                }
            )
            return 0
        with _build_live_client(protocol) as client:
            collector = EvidenceCollector(protocol=protocol, client=client)
            _print_json(run_capture(collector))
        return 0
    except G8EvidenceError as error:
        _print_json(
            {
                "status": "FAIL_CLOSED",
                "error_code": error.code,
                "g8_status": "NOT_READY",
                "production_authorization": "none",
            },
            stream=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
