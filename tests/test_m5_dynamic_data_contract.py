from __future__ import annotations

import copy
from pathlib import Path

import pytest

from shaiwei.research_gates.m5_dynamic.contract import (
    API_FIELDS,
    MEMBERSHIP_CODE_FIELDS,
    PROTOCOL_SCOPE_SHA256,
    REQUIRED_APIS,
    InputManifest,
    M5DataProtocol,
    M5GateError,
    canonical_json,
    sha256_json,
)


ROOT = Path(__file__).parents[1]


def _protocol() -> M5DataProtocol:
    return M5DataProtocol.load(
        ROOT / "config/m5_dynamic_fundamental_cross_pool_v1.yaml",
        build_path=ROOT / "config/m5_dynamic_fundamental_data_gate_build_v1.yaml",
        project_root=ROOT,
    )


def _manifest(protocol: M5DataProtocol) -> dict:
    sources = []
    for index, api in enumerate(REQUIRED_APIS):
        batches = [
            {
                "batch_id": f"fixture-{index + 1}",
                "batch_identity_sha256": f"{index + 1:064x}",
                "relative_path": f"data/raw/{api.replace('.', '/')}/batch.parquet",
                "content_sha256": f"{index + 101:064x}",
                "request_params_sha256": f"{index + 201:064x}",
                "row_count": 10,
                "bytes": 1024,
                "schema_fields": list(API_FIELDS[api]),
                "ingest_time": "2026-08-05T10:00:00+08:00",
            }
        ]
        sources.append(
            {
                "source_api": api,
                "selection_sha256": sha256_json(batches),
                "batches": batches,
            }
        )
    return {
        "schema_version": "m5-data-input-v1",
        "created_at": "2026-08-05T20:00:00+08:00",
        "protocol_scope_sha256": PROTOCOL_SCOPE_SHA256,
        "protocol_sha256": protocol.sha256,
        "semantic_rows_read": False,
        "ledger_selection_scope": list(REQUIRED_APIS),
        "sources": sources,
        "memberships": [
            {
                "universe_id": universe.universe_id,
                "relative_path": universe.membership_relative_path,
                "content_sha256": universe.membership_sha256,
                "row_count": 10,
                "bytes": 1024,
                "schema_fields": (
                    ["trade_date", MEMBERSHIP_CODE_FIELDS[universe.universe_id]]
                    if universe.filter_column is None
                    else [
                        "trade_date",
                        "formation_date",
                        universe.filter_column,
                        "ts_code",
                    ]
                ),
                "filter": (
                    None
                    if universe.filter_column is None
                    else {"column": universe.filter_column, "value": universe.filter_value}
                ),
            }
            for universe in protocol.universes
        ],
    }


def _write(tmp_path: Path, document: dict) -> Path:
    path = tmp_path / "manifest.json"
    path.write_text(canonical_json(document) + "\n", encoding="utf-8")
    return path


def test_protocol_loads_eight_candidate_specific_definitions() -> None:
    protocol = _protocol()

    assert len(protocol.candidates) == 8
    assert len(protocol.universes) == 3
    assert len(protocol.candidate_ids) * len(protocol.universe_ids) == 24
    external = next(
        candidate
        for candidate in protocol.candidates
        if candidate.candidate_id == "m5_external_financing_dependence_v1"
    )
    assert external.inputs == (
        "cashflow.n_cash_flows_fnc_act_t",
        "balancesheet.total_assets_t",
        "balancesheet.total_assets_p",
    )
    assert "cashflow.n_cash_flows_fnc_act_p" not in external.inputs


def test_input_manifest_accepts_only_seven_exact_metadata_sources(tmp_path: Path) -> None:
    protocol = _protocol()
    loaded = InputManifest.load(_write(tmp_path, _manifest(protocol)), protocol)

    assert loaded.document["semantic_rows_read"] is False
    assert {item["source_api"] for item in loaded.document["sources"]} == set(REQUIRED_APIS)
    assert len(loaded.sha256) == 64


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda doc: doc["sources"].pop(), "seven source APIs"),
        (
            lambda doc: doc["sources"][0].update({"source_api": "tushare.daily"}),
            "seven source APIs",
        ),
        (
            lambda doc: doc["sources"][0]["batches"][0].update(
                {"relative_path": "../labels.parquet"}
            ),
            "selection hash differs",
        ),
        (
            lambda doc: doc["sources"][1]["batches"][0].update(
                {"schema_fields": ["ts_code"]}
            ),
            "selection hash differs",
        ),
        (
            lambda doc: doc.update({"semantic_rows_read": True}),
            "must not read semantic rows",
        ),
    ],
)
def test_input_manifest_fails_closed_on_scope_or_allowlist_drift(
    tmp_path: Path, mutation, message: str
) -> None:
    protocol = _protocol()
    document = copy.deepcopy(_manifest(protocol))
    mutation(document)

    with pytest.raises(M5GateError, match=message):
        InputManifest.load(_write(tmp_path, document), protocol)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("relative_path", "../labels.parquet", "safe project-relative"),
        ("schema_fields", ["ts_code"], "lacks an allowlisted field"),
    ],
)
def test_input_manifest_rejects_rehashed_forbidden_batch_metadata(
    tmp_path: Path, field: str, value, message: str
) -> None:
    protocol = _protocol()
    document = _manifest(protocol)
    source = document["sources"][1]
    source["batches"][0][field] = value
    source["selection_sha256"] = sha256_json(source["batches"])

    with pytest.raises(M5GateError, match=message):
        InputManifest.load(_write(tmp_path, document), protocol)
