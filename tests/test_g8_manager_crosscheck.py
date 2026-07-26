import json
from pathlib import Path

import httpx
import pytest

from shaiwei.ingest.g8_manager_crosscheck import (
    ManagerEvidenceError,
    Product,
    Protocol,
    RequestSpec,
    _observation,
    _normalized_comparison,
    parse_gthtzg_nav,
    parse_html_nav,
)


DATES = (
    "2026-07-15",
    "2026-07-16",
    "2026-07-17",
    "2026-07-20",
    "2026-07-21",
    "2026-07-22",
    "2026-07-23",
    "2026-07-24",
)
PRODUCT = Product(
    code="016276",
    expected_name="招商中证800指数增强A",
    allowed_hosts=frozenset({"manager.example"}),
    document={},
)


def _html_rows(*, drop_last: bool = False, duplicate: bool = False) -> bytes:
    rows = list(DATES[:-1] if drop_last else DATES)
    if duplicate:
        rows.append(DATES[0])
    rendered = "".join(
        f"<tr><td>{day}</td><td>1.{index:04d}</td><td>2.{index:04d}</td></tr>"
        for index, day in enumerate(rows)
    )
    return f"<html>招商中证800指数增强A 016276<table>{rendered}</table></html>".encode()


def test_protocol_loads_frozen_repository_identity() -> None:
    protocol = Protocol.load(Path("config/g8_fund_manager_crosscheck_v1.yaml"))
    assert tuple(product.code for product in protocol.products) == (
        "016276",
        "017985",
        "022513",
        "022461",
        "022485",
        "022467",
    )
    assert protocol.required_dates == DATES


def test_html_parser_requires_exact_identity_dates_and_uniqueness() -> None:
    records = parse_html_nav(
        _html_rows(), parser="cmfchina_html_utf8", product=PRODUCT, required_dates=DATES
    )
    assert len(records) == 8
    assert records[0]["valuation_date"] == DATES[0]

    with pytest.raises(ManagerEvidenceError, match="MANAGER_NAV_REQUIRED_DATE_MISSING"):
        parse_html_nav(
            _html_rows(drop_last=True),
            parser="cmfchina_html_utf8",
            product=PRODUCT,
            required_dates=DATES,
        )
    with pytest.raises(ManagerEvidenceError, match="MANAGER_NAV_DUPLICATE_DATE"):
        parse_html_nav(
            _html_rows(duplicate=True),
            parser="cmfchina_html_utf8",
            product=PRODUCT,
            required_dates=DATES,
        )


def test_gthtzg_json_parser_and_timestamp_only_normalization() -> None:
    product = Product(
        code="022467",
        expected_name="国泰海通中证A500指数增强A",
        allowed_hosts=frozenset({"www.gthtzg.com"}),
        document={},
    )
    root = {
        "success": True,
        "code": 0,
        "result": {
            "records": [
                {
                    "fundCode": "022467",
                    "releaseDate": day,
                    "netValue": f"1.{index:04d}",
                    "totalNetValue": f"2.{index:04d}",
                }
                for index, day in enumerate(DATES)
            ]
        },
        "timestamp": 1,
    }
    first = json.dumps(root).encode()
    root["timestamp"] = 2
    second = json.dumps(root).encode()
    assert _normalized_comparison(first, "gthtzg_json_nav") == _normalized_comparison(
        second, "gthtzg_json_nav"
    )
    assert len(parse_gthtzg_nav(first, product=product, required_dates=DATES)) == 8
    root["result"]["records"][0]["netValue"] = "9.9999"
    assert _normalized_comparison(first, "gthtzg_json_nav") != _normalized_comparison(
        json.dumps(root).encode(), "gthtzg_json_nav"
    )


def test_request_identity_changes_with_role_or_payload() -> None:
    base = RequestSpec(
        product=PRODUCT,
        role="nav_request",
        method="POST",
        url="https://manager.example/nav",
        headers={"User-Agent": "fixture"},
        json_body={"fundCode": "016276"},
        parser="gthtzg_json_nav",
    )
    changed = RequestSpec(
        product=PRODUCT,
        role="current_fee_request",
        method="POST",
        url="https://manager.example/nav",
        headers={"User-Agent": "fixture"},
        json_body={"fundCode": "016276"},
        parser="gthtzg_json_nav",
    )
    assert base.request_id != changed.request_id


def test_httpx_tls_error_class_is_not_a_value(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*args: object, **kwargs: object) -> None:
        raise httpx.ConnectError("fixture")

    monkeypatch.setattr(httpx.Client, "request", fail)
    spec = RequestSpec(
        product=PRODUCT,
        role="nav_request",
        method="GET",
        url="https://manager.example/nav",
        headers={"User-Agent": "fixture"},
        json_body=None,
        parser="cmfchina_html_utf8",
    )
    observation = _observation(httpx.Client(), spec)
    assert observation.http_status == 0
    assert observation.body == b""
    assert observation.error_class == "ConnectError"
