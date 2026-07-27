from copy import deepcopy

import pandas as pd
import pytest

from shaiwei.web.security_names import (
    SecurityNameCatalog,
    SecurityNameError,
    project_catalog,
)


SOURCE_CUTOFF = "2026-07-24T11:30:00+00:00"


def _catalog_document() -> dict[str, object]:
    namechange = pd.DataFrame(
        [
            {
                "ts_code": "600001.SH",
                "name": "旧简称",
                "start_date": "20100101",
                "end_date": "20200101",
            },
            {
                "ts_code": "600001.SH",
                "name": "新简称",
                "start_date": "20200102",
                "end_date": "",
            },
            {
                "ts_code": "430001.BJ",
                "name": "北交示例",
                "start_date": "20200101",
                "end_date": "",
            },
        ]
    )
    stock_basic = pd.DataFrame(
        [
            {
                "ts_code": "600001.SH",
                "name": "新简称",
                "list_date": "20100101",
                "list_status": "L",
            },
            {
                "ts_code": "T600018.SH",
                "name": "交易所测试证券",
                "list_date": "20200101",
                "list_status": "L",
            },
            {
                "ts_code": "000002.SZ",
                "name": "基础简称",
                "list_date": "19910129",
                "list_status": "L",
            },
            {
                "ts_code": "430001.BJ",
                "name": "北交示例",
                "list_date": "20200101",
                "list_status": "L",
            },
        ]
    )
    return project_catalog(
        namechange,
        stock_basic,
        source_cutoff=SOURCE_CUTOFF,
        source_identities={},
    )


def test_catalog_resolves_pit_then_explicit_current_fallback():
    document = _catalog_document()
    catalog = SecurityNameCatalog.from_document(document)

    assert catalog.resolve("600001.SH", "20200101") == {
        "security_name": "旧简称",
        "security_name_source": "NAMECHANGE_PIT",
        "security_name_status": "PASS",
    }
    assert catalog.resolve("600001.SH", "20200102")["security_name"] == "新简称"
    assert catalog.resolve("000002.SZ", "20260724") == {
        "security_name": "基础简称",
        "security_name_source": "STOCK_BASIC_CURRENT_FALLBACK",
        "security_name_status": "WARN",
    }
    assert catalog.resolve("000003.SZ", "20260724") == {
        "security_name": None,
        "security_name_source": "UNAVAILABLE",
        "security_name_status": "NOT_READY",
    }
    assert document["quality"] == {
        "history_row_count": 2,
        "history_security_count": 1,
        "fallback_security_count": 2,
        "excluded_bse_history_count": 1,
        "excluded_bse_basic_count": 1,
        "excluded_exchange_test_basic_count": 1,
    }


def test_catalog_rejects_duplicate_and_ambiguous_history():
    duplicate = pd.DataFrame(
        [
            {
                "ts_code": "600001.SH",
                "name": "同名",
                "start_date": "20200101",
                "end_date": "",
            },
            {
                "ts_code": "600001.SH",
                "name": "同名",
                "start_date": "20200101",
                "end_date": "",
            },
        ]
    )
    basics = pd.DataFrame(
        [
            {
                "ts_code": "600001.SH",
                "name": "同名",
                "list_date": "20100101",
                "list_status": "L",
            }
        ]
    )
    with pytest.raises(SecurityNameError, match="duplicate intervals"):
        project_catalog(
            duplicate,
            basics,
            source_cutoff=SOURCE_CUTOFF,
            source_identities={},
        )

    ambiguous = duplicate.copy()
    ambiguous.loc[1, "name"] = "另一简称"
    document = project_catalog(
        ambiguous,
        basics,
        source_cutoff=SOURCE_CUTOFF,
        source_identities={},
    )
    with pytest.raises(SecurityNameError, match="ambiguous"):
        SecurityNameCatalog.from_document(document).resolve("600001.SH", "20260724")


def test_catalog_document_quality_is_fail_closed():
    document = deepcopy(_catalog_document())
    document["quality"]["history_row_count"] = 99
    with pytest.raises(SecurityNameError, match="quality counts do not close"):
        SecurityNameCatalog.from_document(document)
