"""G8-2 official-manager HTTPS evidence capture and fail-closed crosscheck.

The module cannot construct total returns or evaluate G8. Raw values remain in
Git-ignored evidence bundles; the tracked ledger contains identities and hashes.
"""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import html
import json
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
import yaml

from shaiwei.evaluation.g8 import comparator_codes
from shaiwei.ledger import append_g8_manager_evidence, sha256_file


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PROTOCOL = PROJECT_ROOT / "config/g8_fund_manager_crosscheck_v1.yaml"
PROTOCOL_ID = "g8-fund-manager-crosscheck-v1"
BUNDLE_SCHEMA = "g8-manager-evidence-bundle-v1"
RECOVERY_PROTOCOL_ID = "g8-fund-primary-capture-recovery-v1"
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DECIMAL_PATTERN = re.compile(r"^[+-]?\d+(?:\.\d+)?$")


class ManagerEvidenceError(RuntimeError):
    """Stable fail-closed error that is safe for a tracked ledger."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        super().__init__(f"{code}: {detail}" if detail else code)


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_json(value: object) -> str:
    return _sha256_bytes(_canonical_json(value).encode("utf-8"))


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _decimal(value: object) -> Decimal:
    try:
        parsed = Decimal(str(value).strip())
    except (InvalidOperation, ValueError) as error:
        raise ManagerEvidenceError("DECIMAL_INVALID") from error
    if not parsed.is_finite():
        raise ManagerEvidenceError("DECIMAL_INVALID")
    return parsed


def _safe_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError as error:
        raise ManagerEvidenceError("ARTIFACT_OUTSIDE_PROJECT") from error


@dataclass(frozen=True)
class Product:
    code: str
    expected_name: str
    allowed_hosts: frozenset[str]
    document: dict[str, Any]


@dataclass(frozen=True)
class Protocol:
    path: Path
    document: dict[str, Any]
    sha256: str
    products: tuple[Product, ...]
    required_dates: tuple[str, ...]
    data_root: Path
    ledger_path: Path

    @classmethod
    def load(cls, path: Path = DEFAULT_PROTOCOL) -> "Protocol":
        try:
            document = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as error:
            raise ManagerEvidenceError("PROTOCOL_UNREADABLE") from error
        if not isinstance(document, dict):
            raise ManagerEvidenceError("PROTOCOL_INVALID")
        if (
            document.get("protocol_id") != PROTOCOL_ID
            or document.get("status") != "RESULT_BEFORE_EXECUTION_FROZEN"
            or document.get("execution_authorized") is not True
            or document.get("production_authorization") != "none"
        ):
            raise ManagerEvidenceError("PROTOCOL_NOT_AUTHORIZED")

        binding = document.get("primary_capture_binding", {})
        primary_path = PROJECT_ROOT / str(binding.get("protocol_path", ""))
        ledger_path = PROJECT_ROOT / str(binding.get("ledger_path", ""))
        if (
            not primary_path.is_file()
            or binding.get("protocol_sha256") != sha256_file(primary_path)
            or not ledger_path.is_file()
            or binding.get("ledger_sha256") != sha256_file(ledger_path)
            or binding.get("prior_verdict") != "GO_G8_2_CROSSCHECK_AND_FEE_LINEAGE_ONLY"
        ):
            raise ManagerEvidenceError("PRIMARY_BINDING_MISMATCH")

        scope = document.get("scope", {})
        forbidden = (
            "strategy_results_access",
            "g8_evaluation",
            "total_return_construction",
            "dividend_total_return_construction",
            "scheduler_integration",
            "web_changes",
            "production_writes",
        )
        if any(scope.get(key) is not False for key in forbidden):
            raise ManagerEvidenceError("SCOPE_EXPANSION_FORBIDDEN")
        if (
            scope.get("official_manager_https_crosscheck") is not True
            or scope.get("effective_dated_subscription_redemption_fee_lineage") is not True
        ):
            raise ManagerEvidenceError("SCOPE_INCOMPLETE")

        raw_products = document.get("products")
        if not isinstance(raw_products, list):
            raise ManagerEvidenceError("PRODUCTS_INVALID")
        products: list[Product] = []
        for raw in raw_products:
            if not isinstance(raw, dict):
                raise ManagerEvidenceError("PRODUCT_INVALID")
            product = Product(
                code=str(raw.get("code", "")),
                expected_name=str(raw.get("expected_name", "")),
                allowed_hosts=frozenset(str(host) for host in raw.get("allowed_hosts", [])),
                document=raw,
            )
            if not product.expected_name or not product.allowed_hosts:
                raise ManagerEvidenceError("PRODUCT_INVALID")
            for role in ("nav_request", "current_fee_request", "legal_document_discovery"):
                request = raw.get(role)
                if not isinstance(request, dict):
                    raise ManagerEvidenceError("REQUEST_INVALID")
                parsed = urlparse(str(request.get("url", "")))
                if parsed.scheme != "https" or parsed.hostname not in product.allowed_hosts:
                    raise ManagerEvidenceError("REQUEST_HOST_INVALID")
            products.append(product)
        if tuple(product.code for product in products) != comparator_codes():
            raise ManagerEvidenceError("PRODUCT_ORDER_MISMATCH")

        required_dates = tuple(str(value) for value in document["nav_crosscheck"]["required_dates"])
        if len(required_dates) != 8 or len(set(required_dates)) != 8:
            raise ManagerEvidenceError("REQUIRED_DATES_INVALID")
        storage = document.get("storage", {})
        data_root = PROJECT_ROOT / str(storage.get("data_root", ""))
        manager_ledger = PROJECT_ROOT / str(storage.get("ledger_path", ""))
        if data_root != PROJECT_ROOT / "data/g8/manager_evidence":
            raise ManagerEvidenceError("DATA_ROOT_INVALID")
        if manager_ledger != PROJECT_ROOT / "ledger/g8_manager_evidence.csv":
            raise ManagerEvidenceError("LEDGER_PATH_INVALID")
        return cls(
            path=path,
            document=document,
            sha256=sha256_file(path),
            products=tuple(products),
            required_dates=required_dates,
            data_root=data_root,
            ledger_path=manager_ledger,
        )


@dataclass(frozen=True)
class RequestSpec:
    product: Product
    role: str
    method: str
    url: str
    headers: dict[str, str]
    json_body: dict[str, object] | None
    parser: str

    @property
    def request_id(self) -> str:
        return _sha256_json(
            {
                "protocol_id": PROTOCOL_ID,
                "product_code": self.product.code,
                "role": self.role,
                "method": self.method,
                "url": self.url,
                "headers": self.headers,
                "json": self.json_body,
                "parser": self.parser,
            }
        )


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


def request_specs(protocol: Protocol) -> tuple[RequestSpec, ...]:
    specs: list[RequestSpec] = []
    user_agent = str(protocol.document["transport"]["user_agent"])
    for product in protocol.products:
        roles = ["nav_request"]
        if "identity_request" in product.document:
            roles.append("identity_request")
        roles.extend(("current_fee_request", "legal_document_discovery"))
        for role in roles:
            raw = product.document[role]
            headers = {"User-Agent": user_agent, **dict(raw.get("headers", {}))}
            json_body = raw.get("json")
            specs.append(
                RequestSpec(
                    product=product,
                    role=role,
                    method=str(raw["method"]).upper(),
                    url=str(raw["url"]),
                    headers=headers,
                    json_body=dict(json_body) if isinstance(json_body, dict) else None,
                    parser=str(raw.get("parser", "document_discovery")),
                )
            )
    return tuple(specs)


def _clean_cell(value: str) -> str:
    without_tags = re.sub(r"<[^>]+>", "", value)
    return re.sub(r"\s+", "", html.unescape(without_tags)).strip()


def _decode_html(body: bytes, parser: str) -> str:
    encoding = "gb18030" if parser == "chinaamc_html_gb18030" else "utf-8"
    try:
        return body.decode(encoding)
    except UnicodeDecodeError as error:
        raise ManagerEvidenceError("HTML_ENCODING_INVALID") from error


def parse_html_nav(
    body: bytes,
    *,
    parser: str,
    product: Product,
    required_dates: tuple[str, ...],
) -> tuple[dict[str, str], ...]:
    text = _decode_html(body, parser)
    compact = re.sub(r"\s+", "", html.unescape(re.sub(r"<[^>]+>", "", text)))
    if product.code not in compact or product.expected_name not in compact:
        raise ManagerEvidenceError("MANAGER_PRODUCT_IDENTITY_MISMATCH")
    records: list[dict[str, str]] = []
    for row in re.findall(r"<tr\b[^>]*>(.*?)</tr>", text, flags=re.IGNORECASE | re.DOTALL):
        cells = [
            _clean_cell(cell)
            for cell in re.findall(
                r"<td\b[^>]*>(.*?)</td>", row, flags=re.IGNORECASE | re.DOTALL
            )
        ]
        date_indexes = [index for index, value in enumerate(cells) if DATE_PATTERN.fullmatch(value)]
        if len(date_indexes) != 1:
            continue
        index = date_indexes[0]
        if cells[index] not in required_dates or len(cells) <= index + 2:
            continue
        unit, cumulative = cells[index + 1], cells[index + 2]
        if DECIMAL_PATTERN.fullmatch(unit) is None or DECIMAL_PATTERN.fullmatch(cumulative) is None:
            raise ManagerEvidenceError("MANAGER_NAV_VALUE_INVALID")
        records.append(
            {
                "product_code": product.code,
                "valuation_date": cells[index],
                "unit_nav": str(_decimal(unit)),
                "cumulative_nav": str(_decimal(cumulative)),
            }
        )
    return _validate_nav_records(records, product=product, required_dates=required_dates)


def parse_gthtzg_nav(
    body: bytes, *, product: Product, required_dates: tuple[str, ...]
) -> tuple[dict[str, str], ...]:
    try:
        root = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ManagerEvidenceError("MANAGER_JSON_INVALID") from error
    if not isinstance(root, dict) or root.get("success") is not True or root.get("code") != 0:
        raise ManagerEvidenceError("MANAGER_API_FAILED")
    result = root.get("result")
    rows = result.get("records") if isinstance(result, dict) else None
    if not isinstance(rows, list):
        raise ManagerEvidenceError("MANAGER_NAV_ROWS_MISSING")
    records: list[dict[str, str]] = []
    for row in rows:
        if not isinstance(row, dict) or str(row.get("fundCode", "")) != product.code:
            raise ManagerEvidenceError("MANAGER_PRODUCT_IDENTITY_MISMATCH")
        valuation_date = str(row.get("releaseDate", ""))
        if valuation_date not in required_dates:
            continue
        records.append(
            {
                "product_code": product.code,
                "valuation_date": valuation_date,
                "unit_nav": str(_decimal(row.get("netValue"))),
                "cumulative_nav": str(_decimal(row.get("totalNetValue"))),
            }
        )
    return _validate_nav_records(records, product=product, required_dates=required_dates)


def _validate_nav_records(
    records: list[dict[str, str]], *, product: Product, required_dates: tuple[str, ...]
) -> tuple[dict[str, str], ...]:
    dates = [record["valuation_date"] for record in records]
    if len(dates) != len(set(dates)):
        raise ManagerEvidenceError("MANAGER_NAV_DUPLICATE_DATE")
    if set(dates) != set(required_dates):
        raise ManagerEvidenceError("MANAGER_NAV_REQUIRED_DATE_MISSING")
    return tuple(sorted(records, key=lambda record: record["valuation_date"]))


def _parse_identity(body: bytes, *, product: Product) -> tuple[dict[str, str], ...]:
    try:
        root = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ManagerEvidenceError("MANAGER_JSON_INVALID") from error
    result = root.get("result") if isinstance(root, dict) else None
    if (
        not isinstance(result, dict)
        or root.get("success") is not True
        or str(result.get("fundCode", "")) != product.code
        or str(result.get("fundName", "")) != product.expected_name
    ):
        raise ManagerEvidenceError("MANAGER_PRODUCT_IDENTITY_MISMATCH")
    return ({"product_code": product.code, "identity": "MATCH"},)


def _parse_current_fee(spec: RequestSpec, body: bytes) -> tuple[dict[str, str], ...]:
    if spec.parser.startswith("gthtzg_json"):
        try:
            root = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise ManagerEvidenceError("MANAGER_JSON_INVALID") from error
        if not isinstance(root, dict) or root.get("success") is not True or root.get("code") != 0:
            raise ManagerEvidenceError("CURRENT_FEE_SOURCE_FAILED")
        rendered = _canonical_json(root.get("result"))
    else:
        rendered = _decode_html(body, spec.parser)
    compact = re.sub(r"\s+", "", html.unescape(re.sub(r"<[^>]+>", "", rendered)))
    if spec.product.code not in compact or spec.product.expected_name not in compact:
        raise ManagerEvidenceError("CURRENT_FEE_IDENTITY_MISMATCH")
    if "申购" not in compact or "赎回" not in compact:
        raise ManagerEvidenceError("CURRENT_FEE_TABLE_MISSING")
    return (
        {"product_code": spec.product.code, "fee_type": "subscription", "status": "PRESENT"},
        {"product_code": spec.product.code, "fee_type": "redemption", "status": "PRESENT"},
    )


def _parse_discovery(spec: RequestSpec, body: bytes) -> tuple[dict[str, str], ...]:
    if spec.parser.startswith("gthtzg_json") or body.lstrip().startswith(b"{"):
        try:
            rendered = _canonical_json(json.loads(body))
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise ManagerEvidenceError("DISCOVERY_JSON_INVALID") from error
    else:
        rendered = _decode_html(body, spec.parser)
    compact = re.sub(r"\s+", "", html.unescape(re.sub(r"<[^>]+>", "", rendered)))
    if spec.product.code not in compact and spec.product.expected_name not in compact:
        raise ManagerEvidenceError("DISCOVERY_PRODUCT_IDENTITY_MISSING")
    markers = ("基金合同", "招募说明书", "产品资料概要")
    present = tuple(marker for marker in markers if marker in compact)
    if not present:
        raise ManagerEvidenceError("LEGAL_DOCUMENT_INDEX_MISSING")
    return tuple({"document_kind": marker, "status": "DISCOVERED_ONLY"} for marker in present)


def _parse(spec: RequestSpec, body: bytes, required_dates: tuple[str, ...]) -> tuple[dict[str, str], ...]:
    if spec.role == "nav_request":
        if spec.parser == "gthtzg_json_nav":
            return parse_gthtzg_nav(body, product=spec.product, required_dates=required_dates)
        return parse_html_nav(
            body,
            parser=spec.parser,
            product=spec.product,
            required_dates=required_dates,
        )
    if spec.role == "identity_request":
        return _parse_identity(body, product=spec.product)
    if spec.role == "current_fee_request":
        return _parse_current_fee(spec, body)
    return _parse_discovery(spec, body)


def _normalized_comparison(body: bytes, parser: str) -> bytes:
    if not parser.startswith("gthtzg_json"):
        return body
    try:
        root = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ManagerEvidenceError("MANAGER_JSON_INVALID") from error
    if not isinstance(root, dict):
        raise ManagerEvidenceError("MANAGER_JSON_INVALID")
    root = dict(root)
    root.pop("timestamp", None)
    return _canonical_json(root).encode("utf-8")


def _observation(client: httpx.Client, spec: RequestSpec) -> Observation:
    try:
        response = client.request(
            spec.method,
            spec.url,
            headers=spec.headers,
            json=spec.json_body,
        )
        redirect_urls = [item.request.url for item in response.history] + [response.url]
        if len(response.history) > 3 or any(
            urlparse(str(url)).hostname not in spec.product.allowed_hosts for url in redirect_urls
        ):
            return Observation(_utc_now(), 0, (), b"", "RedirectPolicyError")
        safe_headers = tuple(
            sorted(
                (key.lower(), value)
                for key, value in response.headers.items()
                if key.lower()
                in {
                    "date",
                    "content-type",
                    "content-length",
                    "last-modified",
                    "etag",
                    "server",
                    "cache-control",
                }
            )
        )
        return Observation(_utc_now(), response.status_code, safe_headers, response.content, "")
    except httpx.HTTPError as error:
        return Observation(_utc_now(), 0, (), b"", type(error).__name__)


def _ledger_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _load_existing(protocol: Protocol, spec: RequestSpec) -> dict[str, Any] | None:
    matches = [row for row in _ledger_rows(protocol.ledger_path) if row["request_id"] == spec.request_id]
    if not matches:
        return None
    if len(matches) != 1:
        raise ManagerEvidenceError("LEDGER_REQUEST_DUPLICATE")
    row = matches[0]
    path = PROJECT_ROOT / row["bundle_path"]
    if not path.is_file() or sha256_file(path) != row["bundle_sha256"]:
        raise ManagerEvidenceError("EXISTING_BUNDLE_HASH_MISMATCH")
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("request_id") != spec.request_id:
        raise ManagerEvidenceError("EXISTING_BUNDLE_IDENTITY_MISMATCH")
    return document


def _persist_bundle(protocol: Protocol, spec: RequestSpec, document: dict[str, Any]) -> tuple[Path, str]:
    path = protocol.data_root / "bundles" / spec.role / spec.product.code / f"{document['evidence_id']}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (_canonical_json(document) + "\n").encode("utf-8")
    if path.exists():
        if path.read_bytes() != payload:
            raise ManagerEvidenceError("BUNDLE_OVERWRITE_FORBIDDEN")
    else:
        with path.open("xb") as handle:
            handle.write(payload)
            handle.flush()
    return path, _sha256_bytes(payload)


def capture_one(protocol: Protocol, client: httpx.Client, spec: RequestSpec) -> tuple[dict[str, Any], bool]:
    existing = _load_existing(protocol, spec)
    if existing is not None:
        return existing, False

    minimum_interval = float(protocol.document["transport"]["minimum_request_start_interval_seconds"])
    first = _observation(client, spec)
    time.sleep(minimum_interval)
    second = _observation(client, spec)
    observations = (first, second)
    status = "CAPTURED"
    error_code = ""
    parsed: tuple[dict[str, str], ...] = ()
    try:
        if any(observation.http_status != 200 for observation in observations):
            raise ManagerEvidenceError("HTTPS_REQUEST_FAILED")
        if _normalized_comparison(first.body, spec.parser) != _normalized_comparison(
            second.body, spec.parser
        ):
            raise ManagerEvidenceError("DOUBLE_FETCH_MISMATCH")
        parsed = _parse(spec, first.body, protocol.required_dates)
        status = {
            "nav_request": "MANAGER_NAV_CAPTURED",
            "identity_request": "MANAGER_IDENTITY_CAPTURED",
            "current_fee_request": "CURRENT_FEE_CAPTURED_NOT_LINEAGE",
            "legal_document_discovery": "LEGAL_INDEX_CAPTURED_NOT_LINEAGE",
        }[spec.role]
    except ManagerEvidenceError as error:
        status = "QUARANTINED"
        error_code = error.code

    evidence_id = _sha256_json(
        {
            "request_id": spec.request_id,
            "statuses": [observation.http_status for observation in observations],
            "body_sha256": [observation.body_sha256 for observation in observations],
            "error_class": [observation.error_class for observation in observations],
            "verification_status": status,
            "error_code": error_code,
        }
    )
    document: dict[str, Any] = {
        "schema_version": BUNDLE_SCHEMA,
        "protocol_id": PROTOCOL_ID,
        "protocol_sha256": protocol.sha256,
        "request_id": spec.request_id,
        "evidence_id": evidence_id,
        "request": {
            "product_code": spec.product.code,
            "role": spec.role,
            "method": spec.method,
            "url": spec.url,
            "headers": spec.headers,
            "json": spec.json_body,
            "parser": spec.parser,
        },
        "observations": [observation.as_document() for observation in observations],
        "parsed_records": list(parsed),
        "verification_status": status,
        "error_code": error_code,
    }
    bundle_path, bundle_sha256 = _persist_bundle(protocol, spec, document)
    row = {
        "evidence_id": evidence_id,
        "protocol_id": PROTOCOL_ID,
        "request_id": spec.request_id,
        "evidence_kind": spec.role,
        "product_code": spec.product.code,
        "captured_at": first.received_at,
        "first_http_status": first.http_status,
        "second_http_status": second.http_status,
        "first_body_sha256": first.body_sha256,
        "second_body_sha256": second.body_sha256,
        "bundle_path": _safe_relative(bundle_path),
        "bundle_sha256": bundle_sha256,
        "parsed_row_count": len(parsed),
        "source_transport": "HTTPS_TLS_VERIFIED",
        "verification_status": status,
        "error_code": error_code,
        "operator": "g8-manager-crosscheck",
    }
    append_g8_manager_evidence(path=protocol.ledger_path, **row)
    return document, True


def load_primary_nav(protocol: Protocol) -> dict[str, dict[str, dict[str, Decimal]]]:
    binding = protocol.document["primary_capture_binding"]
    primary_ledger = PROJECT_ROOT / binding["ledger_path"]
    rows = _ledger_rows(primary_ledger)
    selected = [
        row
        for row in rows
        if row["protocol_id"] == RECOVERY_PROTOCOL_ID
        and row["evidence_kind"] == "NAV_RANGE"
        and row["verification_status"] == "PRIMARY_CAPTURED_UNAUTHENTICATED"
    ]
    if len(selected) != 6:
        raise ManagerEvidenceError("PRIMARY_NAV_EVIDENCE_COUNT_INVALID")
    result: dict[str, dict[str, dict[str, Decimal]]] = {}
    for row in selected:
        path = PROJECT_ROOT / row["bundle_path"]
        if not path.is_file() or sha256_file(path) != row["bundle_sha256"]:
            raise ManagerEvidenceError("PRIMARY_BUNDLE_HASH_MISMATCH")
        bundle = json.loads(path.read_text(encoding="utf-8"))
        records = bundle.get("parsed_records")
        if not isinstance(records, list) or len(records) != 8:
            raise ManagerEvidenceError("PRIMARY_NAV_RECORDS_INVALID")
        code = row["product_code"]
        result[code] = {
            str(record["valuation_date"]): {
                "unit_nav": _decimal(record["share_net_value"]),
                "cumulative_nav": _decimal(record["total_net_value"]),
            }
            for record in records
        }
    return result


def build_report(protocol: Protocol, bundles: dict[str, dict[str, Any]]) -> dict[str, Any]:
    primary = load_primary_nav(protocol)
    products: list[dict[str, object]] = []
    for product in protocol.products:
        product_bundles = {
            role: bundle
            for key, bundle in bundles.items()
            for role in [key.split(":", 1)[1]]
            if key.startswith(f"{product.code}:")
        }
        nav = product_bundles.get("nav_request", {})
        identity = product_bundles.get("identity_request", nav)
        manager_records = nav.get("parsed_records", []) if isinstance(nav, dict) else []
        exact_match = len(manager_records) == len(protocol.required_dates)
        mismatches: list[str] = []
        if exact_match:
            for record in manager_records:
                day = str(record["valuation_date"])
                expected = primary.get(product.code, {}).get(day)
                if expected is None or (
                    _decimal(record["unit_nav"]) != expected["unit_nav"]
                    or _decimal(record["cumulative_nav"]) != expected["cumulative_nav"]
                ):
                    mismatches.append(day)
            exact_match = not mismatches
        identity_pass = str(identity.get("verification_status", "")).startswith("MANAGER_")
        current_fee_pass = (
            product_bundles.get("current_fee_request", {}).get("verification_status")
            == "CURRENT_FEE_CAPTURED_NOT_LINEAGE"
        )
        legal_index_pass = (
            product_bundles.get("legal_document_discovery", {}).get("verification_status")
            == "LEGAL_INDEX_CAPTURED_NOT_LINEAGE"
        )
        products.append(
            {
                "product_code": product.code,
                "authenticated_https_identity": identity_pass,
                "manager_nav_rows": len(manager_records),
                "exact_eight_date_nav_match": exact_match,
                "mismatch_dates": mismatches,
                "current_fee_crosscheck": current_fee_pass,
                "legal_document_index_captured": legal_index_pass,
                "complete_effective_dated_fee_lineage": False,
                "fee_lineage_reason": "LEGAL_DOCUMENTS_NOT_DOWNLOADED_OR_EFFECTIVE_DATES_NOT_PROVEN",
            }
        )
    counts = {
        "products": len(products),
        "authenticated_https_identity": sum(
            bool(item["authenticated_https_identity"]) for item in products
        ),
        "exact_eight_date_nav_match": sum(bool(item["exact_eight_date_nav_match"]) for item in products),
        "current_fee_crosscheck": sum(bool(item["current_fee_crosscheck"]) for item in products),
        "legal_document_index_captured": sum(
            bool(item["legal_document_index_captured"]) for item in products
        ),
        "complete_effective_dated_fee_lineage": 0,
    }
    all_pass = all(
        item["authenticated_https_identity"]
        and item["exact_eight_date_nav_match"]
        and item["complete_effective_dated_fee_lineage"]
        for item in products
    )
    captured_times = [
        str(observation["received_at"])
        for bundle in bundles.values()
        for observation in bundle.get("observations", [])
        if isinstance(observation, dict) and observation.get("received_at")
    ]
    return {
        "schema_version": "g8-manager-crosscheck-report-v1",
        "protocol_id": PROTOCOL_ID,
        "protocol_sha256": protocol.sha256,
        "evidence_cutoff_at": max(captured_times),
        "products": products,
        "counts": counts,
        "official_manager_https_crosscheck_complete": counts["authenticated_https_identity"] == 6
        and counts["exact_eight_date_nav_match"] == 6,
        "effective_dated_fee_lineage_complete": False,
        "g8_2_verdict": "GO_G8_3_TOTAL_RETURN_CONSTRUCTION_PROTOCOL_ONLY"
        if all_pass
        else "NO_GO_G8_2",
        "g8_status": "NOT_READY",
        "production_authorization": "none",
        "strategy_results_accessed": False,
        "total_returns_constructed": False,
        "g8_evaluated": False,
    }


def _write_immutable(path: Path, document: object) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (_canonical_json(document) + "\n").encode("utf-8")
    if path.exists():
        if path.read_bytes() != payload:
            raise ManagerEvidenceError("IMMUTABLE_ARTIFACT_CONFLICT")
    else:
        with path.open("xb") as handle:
            handle.write(payload)
    return _sha256_bytes(payload)


def run(protocol: Protocol, *, verify_only: bool = False) -> dict[str, object]:
    specs = request_specs(protocol)
    bundles: dict[str, dict[str, Any]] = {}
    appended = 0
    reused = 0
    if verify_only:
        for spec in specs:
            bundle = _load_existing(protocol, spec)
            if bundle is None:
                raise ManagerEvidenceError("EXPECTED_BUNDLE_MISSING")
            bundles[f"{spec.product.code}:{spec.role}"] = bundle
            reused += 1
    else:
        timeout = float(protocol.document["transport"]["request_timeout_seconds"])
        with httpx.Client(timeout=timeout, verify=True, follow_redirects=True, trust_env=True) as client:
            for spec in specs:
                bundle, was_appended = capture_one(protocol, client, spec)
                bundles[f"{spec.product.code}:{spec.role}"] = bundle
                appended += int(was_appended)
                reused += int(not was_appended)

    report = build_report(protocol, bundles)
    manifest_entries = []
    for row in _ledger_rows(protocol.ledger_path):
        path = PROJECT_ROOT / row["bundle_path"]
        if not path.is_file() or sha256_file(path) != row["bundle_sha256"]:
            raise ManagerEvidenceError("MANIFEST_BUNDLE_HASH_MISMATCH")
        manifest_entries.append(
            {
                "evidence_id": row["evidence_id"],
                "bundle_path": row["bundle_path"],
                "bundle_sha256": row["bundle_sha256"],
            }
        )
    manifest = {
        "schema_version": "g8-manager-crosscheck-manifest-v1",
        "protocol_id": PROTOCOL_ID,
        "protocol_sha256": protocol.sha256,
        "entries": manifest_entries,
    }
    report_path = PROJECT_ROOT / protocol.document["storage"]["report_path"]
    manifest_path = PROJECT_ROOT / protocol.document["storage"]["manifest_path"]
    report_sha256 = _write_immutable(report_path, report)
    manifest_sha256 = _write_immutable(manifest_path, manifest)
    return {
        "protocol_id": PROTOCOL_ID,
        "logical_requests": len(specs),
        "appended": appended,
        "reused": reused,
        "ledger_rows": len(_ledger_rows(protocol.ledger_path)),
        "report_sha256": report_sha256,
        "manifest_sha256": manifest_sha256,
        "g8_2_verdict": report["g8_2_verdict"],
        "g8_status": report["g8_status"],
        "production_authorization": "none",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--verify-only", action="store_true")
    arguments = parser.parse_args(argv)
    try:
        summary = run(Protocol.load(arguments.protocol), verify_only=arguments.verify_only)
    except (ManagerEvidenceError, OSError, ValueError, json.JSONDecodeError) as error:
        code = getattr(error, "code", type(error).__name__)
        print(_canonical_json({"status": "FAIL", "error_code": code}), file=sys.stderr)
        return 1
    print(_canonical_json(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
