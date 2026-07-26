import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs

import httpx
import pytest

from shaiwei.ingest.g8_fund_evidence import (
    LEDGER_HEADER,
    EvidenceCollector,
    G8CaptureProtocol,
    G8EvidenceError,
    dividend_request_spec,
    nav_request_spec,
    parse_dividend_response,
    parse_nav_response,
    run_capture,
    verify_evidence_ledger,
)
from shaiwei.ledger import sha256_file


VALUATION_DATES = (
    "2026-07-15",
    "2026-07-16",
    "2026-07-17",
    "2026-07-20",
    "2026-07-21",
    "2026-07-22",
    "2026-07-23",
    "2026-07-24",
)


def _protocol() -> G8CaptureProtocol:
    return G8CaptureProtocol.load()


def _ledger(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(",".join(LEDGER_HEADER) + "\n", encoding="utf-8")


def _nav_document(product, *, version: int = 1, nonempty_master: bool = False) -> dict:
    rows = []
    product_index = list(_protocol().products).index(product) + 1
    for day_index, valuation_date in enumerate(VALUATION_DATES, start=1):
        master = {
            "code": product.code,
            "shortName": product.expected_name.removesuffix("A"),
            "valuationDate": valuation_date,
            "shareNetValue": "9.9" if nonempty_master and day_index == 1 else "",
            "totalNetValue": "",
            "classification": {"code": "2030-1030"},
            "fund": {"idStr": product.fund_id},
            "uploadInfoDetail": {"idStr": product_index * 1000 + day_index},
        }
        usable = {
            "code": product.code,
            "shortName": product.expected_name,
            "valuationDate": valuation_date,
            "shareNetValue": f"1.{version}{day_index:02d}",
            "totalNetValue": f"1.{version + 1}{day_index:02d}",
            "classification": {"code": "2030-1010"},
            "fund": {"idStr": product.fund_id},
            "uploadInfoDetail": {"idStr": product_index * 1000 + day_index},
        }
        rows.extend((master, usable))
    return {
        "sEcho": 1,
        "iTotalRecords": len(rows),
        "iTotalDisplayRecords": len(rows),
        "aaData": rows,
    }


def _dividend_document(code: str, name: str) -> dict:
    return {
        "fundCode": code,
        "fundName": name,
        "isFenji": "false",
        "specialPoint": {
            "fenhongjinE": "",
            "changwai": "",
            "changnei": "",
            "remark": "",
            "specialPoint": "",
        },
    }


def _response(document: dict) -> httpx.Response:
    return httpx.Response(
        200,
        content=json.dumps(document, ensure_ascii=False, sort_keys=True).encode(),
        headers={"content-type": "application/json;charset=UTF-8", "set-cookie": "unsafe=1"},
    )


class SourceFixture:
    def __init__(self) -> None:
        self.protocol = _protocol()
        self.calls = 0
        self.nav_version = 1

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.calls += 1
        if request.url.path.endswith("getPublicFundJZInfoMore.do"):
            ao_data = json.loads(request.url.params["aoData"])
            values = {item["name"]: item["value"] for item in ao_data}
            product = next(item for item in self.protocol.products if item.code == values["fundCode"])
            return _response(_nav_document(product, version=self.nav_version))
        if request.url.path.endswith("getDividendInfo.do"):
            form = parse_qs(request.content.decode("utf-8"))
            return _response(_dividend_document(form["fundCode"][0], form["fundName"][0]))
        raise AssertionError(request.url.path)


def _collector(tmp_path: Path, source: SourceFixture) -> EvidenceCollector:
    ledger_path = tmp_path / "ledger/g8_fund_evidence.csv"
    _ledger(ledger_path)
    client = httpx.Client(
        base_url="http://eid.csrc.gov.cn",
        transport=httpx.MockTransport(source),
    )
    return EvidenceCollector(
        protocol=source.protocol,
        client=client,
        project_root=tmp_path,
        data_root=tmp_path / "data/g8/fund_evidence",
        ledger_path=ledger_path,
        now=lambda: datetime(2026, 7, 26, 4, 0, tzinfo=timezone.utc),
        minimum_interval_seconds=0,
        execution_code_sha256="a" * 64,
        execution_git_head="b" * 40,
    )


def _nav_parser(protocol: G8CaptureProtocol, product):
    return lambda body: parse_nav_response(
        body,
        product=product,
        capture_start=protocol.capture_start,
        capture_end=protocol.capture_end,
        expected_rows=8,
    )


def test_nav_and_dividend_parsers_preserve_frozen_identity() -> None:
    protocol = _protocol()
    product = protocol.products[0]
    nav = parse_nav_response(
        json.dumps(_nav_document(product), ensure_ascii=False).encode(),
        product=product,
        capture_start=protocol.capture_start,
        capture_end=protocol.capture_end,
        expected_rows=8,
    )
    assert [row["valuation_date"] for row in nav] == list(VALUATION_DATES)
    assert all(row["product_code"] == product.code for row in nav)
    dividend = parse_dividend_response(
        json.dumps(_dividend_document(product.code, product.expected_name), ensure_ascii=False).encode(),
        product=product,
        valuation_date=VALUATION_DATES[0],
        upload_detail_id=int(nav[0]["upload_detail_id"]),
    )
    assert dividend[0]["remark"] == ""
    assert dividend[0]["valuation_date"] == VALUATION_DATES[0]


def test_nav_parser_rejects_nonempty_ignored_master_row() -> None:
    protocol = _protocol()
    product = protocol.products[0]
    with pytest.raises(G8EvidenceError, match="NAV_MASTER_ROW_NONEMPTY"):
        parse_nav_response(
            json.dumps(_nav_document(product, nonempty_master=True), ensure_ascii=False).encode(),
            product=product,
            capture_start=protocol.capture_start,
            capture_end=protocol.capture_end,
            expected_rows=8,
        )


def test_full_fixture_capture_is_54_rows_and_second_run_is_zero_append(tmp_path: Path) -> None:
    source = SourceFixture()
    collector = _collector(tmp_path, source)

    first = run_capture(collector)
    first_ledger_hash = sha256_file(collector.ledger_path)
    first_bundle_hashes = sorted(
        sha256_file(path) for path in collector.data_root.rglob("*.json")
    )
    second = run_capture(collector)

    assert source.calls == 216
    assert first["logical_requests"] == 54
    assert first["http_observations"] == 108
    assert first["appended_evidence"] == 54
    assert first["reused_evidence"] == 0
    assert second["appended_evidence"] == 0
    assert second["reused_evidence"] == 54
    assert sha256_file(collector.ledger_path) == first_ledger_hash
    assert sorted(sha256_file(path) for path in collector.data_root.rglob("*.json")) == first_bundle_hashes
    assert second["kind_counts"] == {"DIVIDEND_NOTE": 48, "NAV_RANGE": 6}
    assert second["parsed_counts"] == {"DIVIDEND_NOTE": 48, "NAV_RANGE": 48}
    assert second["status_counts"] == {"PRIMARY_CAPTURED_UNAUTHENTICATED": 54}

    bundle_text = next(collector.data_root.rglob("*.json")).read_text(encoding="utf-8")
    assert "set-cookie" not in bundle_text.lower()
    assert "unsafe=1" not in bundle_text


def test_double_fetch_mismatch_is_persisted_and_fails_closed(tmp_path: Path) -> None:
    source = SourceFixture()
    collector = _collector(tmp_path, source)
    product = source.protocol.products[0]
    original = source.__call__

    def mismatch(request: httpx.Request) -> httpx.Response:
        if source.calls == 1:
            source.nav_version = 2
        return original(request)

    collector.client._transport = httpx.MockTransport(mismatch)
    spec = nav_request_spec(source.protocol, product)
    with pytest.raises(G8EvidenceError, match="DOUBLE_FETCH_MISMATCH"):
        collector.capture(spec, _nav_parser(source.protocol, product))

    with collector.ledger_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 1
    assert rows[0]["verification_status"] == "QUARANTINED_DOUBLE_FETCH_MISMATCH"
    assert rows[0]["first_body_sha256"] != rows[0]["second_body_sha256"]


def test_prior_request_new_content_is_revision_quarantined(tmp_path: Path) -> None:
    source = SourceFixture()
    collector = _collector(tmp_path, source)
    product = source.protocol.products[0]
    spec = nav_request_spec(source.protocol, product)
    first = collector.capture(spec, _nav_parser(source.protocol, product))

    source.nav_version = 2
    with pytest.raises(G8EvidenceError, match="PRIOR_REQUEST_CONTENT_DIFFERS"):
        collector.capture(spec, _nav_parser(source.protocol, product))

    with collector.ledger_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 2
    assert rows[1]["verification_status"] == "QUARANTINED_REVISION"
    assert rows[1]["revision_of_evidence_id"] == first.evidence_id


def test_ledger_verifier_detects_bundle_tampering(tmp_path: Path) -> None:
    source = SourceFixture()
    collector = _collector(tmp_path, source)
    product = source.protocol.products[0]
    spec = nav_request_spec(source.protocol, product)
    captured = collector.capture(spec, _nav_parser(source.protocol, product))
    captured.bundle_path.write_text("{}\n", encoding="utf-8")

    with pytest.raises(G8EvidenceError, match="LEDGER_BUNDLE_HASH_MISMATCH"):
        verify_evidence_ledger(
            source.protocol,
            ledger_path=collector.ledger_path,
            project_root=tmp_path,
        )


def test_dividend_request_is_bound_to_nav_upload_identity() -> None:
    protocol = _protocol()
    product = protocol.products[0]
    nav_record = {
        "valuation_date": VALUATION_DATES[0],
        "upload_detail_id": 33937275,
    }
    spec = dividend_request_spec(
        protocol,
        product,
        nav_record,
        parent_request_id="f" * 64,
    )
    assert spec.form == {
        "uploadDetailId": "33937275",
        "fundName": product.expected_name,
        "fundCode": product.code,
        "thisLevel": "1",
        "thisName": product.expected_name,
        "thisCode": product.code,
    }
    assert spec.period_start == VALUATION_DATES[0]
