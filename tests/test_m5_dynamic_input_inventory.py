from __future__ import annotations

import csv
import dataclasses
import json
from pathlib import Path

import pandas as pd
import pytest

from shaiwei.research_gates.m5_dynamic import input_inventory
from shaiwei.research_gates.m5_dynamic.contract import (
    API_FIELDS,
    REQUIRED_APIS,
    InputManifest,
    M5DataProtocol,
    Universe,
    canonical_json,
    sha256_file,
)
from shaiwei.research_gates.m5_dynamic.input_inventory import (
    LEDGER_COLUMNS,
    build_input_manifest,
)
from shaiwei.research_gates.m5_dynamic.source_reader import load_allowed_inputs


ROOT = Path(__file__).parents[1]
CREATED_AT = "2026-08-05T20:00:00+08:00"
LEDGER_FIELD_ORDER = (
    "batch_id",
    "ingest_time",
    "source_api",
    "params_json",
    "row_count",
    "parquet_path",
    "content_sha256",
    "operator",
)


def _base_protocol() -> M5DataProtocol:
    return M5DataProtocol.load(
        ROOT / "config/m5_dynamic_fundamental_cross_pool_v1.yaml",
        build_path=ROOT / "config/m5_dynamic_fundamental_data_gate_build_v1.yaml",
        project_root=ROOT,
    )


def _write_parquet(path: Path, fields: tuple[str, ...], marker: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    values = {
        field: [
            float(marker)
            if field
            not in {
                "exchange",
                "cal_date",
                "is_open",
                "ts_code",
                "f_ann_date",
                "end_date",
                "report_type",
                "update_flag",
            }
            else str(marker)
        ]
        for field in fields
    }
    pd.DataFrame(values).to_parquet(path, index=False)


def _membership_protocol(tmp_path: Path) -> M5DataProtocol:
    protocol = _base_protocol()
    star_path = tmp_path / "data/membership/star50.parquet"
    custom_path = tmp_path / "data/membership/custom.parquet"
    star_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {"trade_date": ["20210201"], "code": ["990001.SH"]}
    ).to_parquet(star_path, index=False)
    pd.DataFrame(
        {
            "trade_date": ["20210201", "20210201"],
            "formation_date": ["20210129", "20210129"],
            "universe_id": [
                "star-board-midcap-pit-v1",
                "star-board-smallcap-pit-v1",
            ],
            "ts_code": ["990002.SH", "990003.SH"],
        }
    ).to_parquet(custom_path, index=False)
    universes = (
        Universe(
            universe_id=protocol.universes[0].universe_id,
            membership_relative_path=star_path.relative_to(tmp_path).as_posix(),
            membership_sha256=sha256_file(star_path),
            filter_column=None,
            filter_value=None,
        ),
        *(
            Universe(
                universe_id=item.universe_id,
                membership_relative_path=custom_path.relative_to(tmp_path).as_posix(),
                membership_sha256=sha256_file(custom_path),
                filter_column=item.filter_column,
                filter_value=item.filter_value,
            )
            for item in protocol.universes[1:]
        ),
    )
    return dataclasses.replace(protocol, universes=universes)


def _batch_row(tmp_path: Path, api: str, index: int, *, revision: int = 1) -> dict[str, str]:
    path = tmp_path / f"data/raw/{index:02d}-{revision}.parquet"
    _write_parquet(path, API_FIELDS[api], marker=index * 10 + revision)
    return {
        "batch_id": f"fixture-{index}-{revision}",
        "ingest_time": f"2026-08-05T{10 + revision:02d}:{index:02d}:00+08:00",
        "source_api": api,
        "params_json": canonical_json({"partition": index}),
        "row_count": "1",
        "parquet_path": path.relative_to(tmp_path).as_posix(),
        "content_sha256": sha256_file(path),
        "operator": "synthetic-fixture",
    }


def _write_ledger(path: Path, rows: list[dict[str, str]]) -> None:
    assert set(LEDGER_FIELD_ORDER) == LEDGER_COLUMNS
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=LEDGER_FIELD_ORDER)
        writer.writeheader()
        writer.writerows(rows)


def _fixture(tmp_path: Path) -> tuple[M5DataProtocol, Path, list[dict[str, str]]]:
    protocol = _membership_protocol(tmp_path)
    rows = [_batch_row(tmp_path, api, index) for index, api in enumerate(REQUIRED_APIS)]
    ledger = tmp_path / "ledger/ingest_batches.csv"
    _write_ledger(ledger, rows)
    return protocol, ledger, rows


def test_metadata_inventory_is_loadable_and_does_not_scan_semantic_rows(tmp_path: Path) -> None:
    protocol, ledger, _ = _fixture(tmp_path)

    document = build_input_manifest(
        protocol,
        project_root=tmp_path,
        ledger_path=ledger,
        created_at=CREATED_AT,
    )
    path = tmp_path / "input-manifest.json"
    path.write_text(canonical_json(document) + "\n", encoding="utf-8")
    loaded = InputManifest.load(path, protocol)

    assert document["semantic_rows_read"] is False
    assert document["ledger_selection_scope"] == list(REQUIRED_APIS)
    assert len(loaded.document["sources"]) == 7
    assert len(loaded.document["memberships"]) == 3
    _, memberships, _ = load_allowed_inputs(protocol, loaded, input_root=tmp_path)
    assert memberships["star50-official-pit-v2"]["ts_code"].tolist() == ["990001.SH"]


def test_unrelated_ledger_append_does_not_change_inventory(tmp_path: Path) -> None:
    protocol, ledger, rows = _fixture(tmp_path)
    before = build_input_manifest(
        protocol, project_root=tmp_path, ledger_path=ledger, created_at=CREATED_AT
    )
    rows.append(
        {
            "batch_id": "unrelated-daily",
            "ingest_time": "2026-08-05T23:00:00+08:00",
            "source_api": "tushare.daily",
            "params_json": json.dumps({"trade_date": "20260805"}),
            "row_count": "999",
            "parquet_path": "not-read.parquet",
            "content_sha256": "0" * 64,
            "operator": "synthetic-fixture",
        }
    )
    _write_ledger(ledger, rows)

    after = build_input_manifest(
        protocol, project_root=tmp_path, ledger_path=ledger, created_at=CREATED_AT
    )

    assert before == after


def test_new_relevant_revision_changes_inventory_identity(tmp_path: Path) -> None:
    protocol, ledger, rows = _fixture(tmp_path)
    before = build_input_manifest(
        protocol, project_root=tmp_path, ledger_path=ledger, created_at=CREATED_AT
    )
    rows.append(_batch_row(tmp_path, REQUIRED_APIS[1], 1, revision=2))
    _write_ledger(ledger, rows)

    after = build_input_manifest(
        protocol, project_root=tmp_path, ledger_path=ledger, created_at=CREATED_AT
    )

    assert before != after
    before_source = next(item for item in before["sources"] if item["source_api"] == REQUIRED_APIS[1])
    after_source = next(item for item in after["sources"] if item["source_api"] == REQUIRED_APIS[1])
    assert before_source["selection_sha256"] != after_source["selection_sha256"]


def test_inventory_fails_if_relevant_selection_changes_mid_build(
    tmp_path: Path, monkeypatch
) -> None:
    protocol, ledger, _ = _fixture(tmp_path)
    original = input_inventory._latest_rows
    calls = 0

    def changing_selection(path: Path):
        nonlocal calls
        calls += 1
        selected = original(path)
        if calls == 2:
            selected[REQUIRED_APIS[0]][0]["batch_id"] = "concurrent-revision"
        return selected

    monkeypatch.setattr(input_inventory, "_latest_rows", changing_selection)

    with pytest.raises(
        input_inventory.M5GateError,
        match="selection changed while inventory was built",
    ):
        build_input_manifest(
            protocol,
            project_root=tmp_path,
            ledger_path=ledger,
            created_at=CREATED_AT,
        )
