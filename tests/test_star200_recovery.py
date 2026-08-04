from __future__ import annotations

import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest
import yaml

from shaiwei.config import PROJECT_ROOT
from tools.official_index_lineage.contract import (
    DataGateError,
    StableCollector,
    build_plan,
    load_protocol,
    sha256_file,
)
from tools.official_index_lineage.recovery import (
    _CountingClient,
    _load_completed_collection,
    _verify_reused,
    build_collection_report,
)
from tools.official_index_lineage.recovery_contract import (
    DEFAULT_RECOVERY,
    build_effective_protocol,
    load_recovery,
    request_pair,
    target_request,
    validate_original_collection,
    write_immutable_yaml,
)

ORIGINAL = PROJECT_ROOT / "config" / "m2_star200_v1.yaml"


def _frozen_inputs() -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    config = yaml.safe_load(DEFAULT_RECOVERY.read_text(encoding="utf-8"))
    original = load_protocol(ORIGINAL)
    target = target_request(config)
    evidence, probes = [], []
    for number, request in enumerate(build_plan(original)):
        item = {
            "batch_id": f"batch-{number}",
            "source_api": f"tushare.{request.api_name}",
            "params_json": json.dumps(request.public_params, ensure_ascii=False, sort_keys=True),
            "row_count": 1,
            "content_sha256": f"{number:064x}",
            "path": f"data/raw/fake-{number}.parquet",
        }
        if request == target:
            item.update(config["original_target_batch"])
        evidence.append(item)
        probes.append(
            {
                "api_name": request.api_name,
                "params_key": request_pair(request)[1],
                "row_count": item["row_count"],
                "first_canonical_sha256": "a" * 64,
                "second_canonical_sha256": "a" * 64,
                "stable": True,
            }
        )
    report = {
        "request_count": 27,
        "request_evidence": evidence,
        "revision_probes": probes,
        "ingest_snapshot_sha256": "b" * 64,
    }
    return config, original, report


def test_recovery_schema_and_original_evidence_are_bound(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "tools.official_index_lineage.recovery_contract._verify_identity",
        lambda item, _label: item,
    )
    config = load_recovery(DEFAULT_RECOVERY)
    _, original, report = _frozen_inputs()
    plan, evidence, probes = validate_original_collection(config, original, report)
    assert len(plan) == len(evidence) == len(probes) == 27
    target = target_request(config)
    assert target.partition_name == "2026-07"
    assert evidence[request_pair(target)]["batch_id"] == "33aa80a00744"


def test_recovery_rejects_schema_drift_before_external_work(tmp_path: Path) -> None:
    payload = yaml.safe_load(DEFAULT_RECOVERY.read_text(encoding="utf-8"))
    payload["unexpected"] = True
    path = tmp_path / "bad.yaml"
    path.write_text(yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8")
    with pytest.raises(DataGateError, match="schema drift"):
        load_recovery(path)


def test_recovery_rejects_path_escape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = yaml.safe_load(DEFAULT_RECOVERY.read_text(encoding="utf-8"))
    payload["outputs"]["root"] = "../escape"
    path = tmp_path / "bad.yaml"
    path.write_text(yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8")
    monkeypatch.setattr(
        "tools.official_index_lineage.recovery_contract._verify_identity",
        lambda item, _label: item,
    )
    with pytest.raises(DataGateError, match="output identity drift"):
        load_recovery(path)


def test_effective_protocol_changes_only_recovery_identity_and_paths(tmp_path: Path) -> None:
    config, original, _ = _frozen_inputs()
    frozen_original = copy.deepcopy(original)
    effective = build_effective_protocol(config, original)
    assert original == frozen_original
    assert effective["identity"]["index_code"] == "000699.SH"
    assert effective["tushare_source_contract"] == original["tushare_source_contract"]
    assert effective["quality_gate"] == original["quality_gate"]
    assert effective["identity"]["raw_source_root"].endswith(
        "m2-star200-data-recovery-v2/official_sources"
    )
    assert effective["official_source_policy"]["discovery_end_date"] == "2026-08-04"
    path = tmp_path / "effective.yaml"
    assert write_immutable_yaml(path, effective) is True
    assert write_immutable_yaml(path, effective) is False


def test_reused_evidence_drift_fails_closed() -> None:
    config, original, report = _frozen_inputs()
    plan, evidence, _ = validate_original_collection(config, original, report)
    current = [copy.deepcopy(evidence[request_pair(request)]) for request in plan]
    non_target = next(item for item in plan if item != target_request(config))
    current[plan.index(non_target)]["content_sha256"] = "f" * 64
    with pytest.raises(DataGateError, match="reused evidence drift"):
        _verify_reused(plan, evidence, current, target_request(config))


def test_collection_report_replaces_only_target(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config, original, report = _frozen_inputs()
    plan, evidence, probes = validate_original_collection(config, original, report)
    target = target_request(config)
    current = [copy.deepcopy(evidence[request_pair(request)]) for request in plan]
    refreshed = copy.deepcopy(current[plan.index(target)])
    refreshed.update(batch_id="new-batch", content_sha256="1" * 64, row_count=200)
    current[plan.index(target)] = refreshed
    monkeypatch.setattr(
        "tools.official_index_lineage.recovery._current_evidence", lambda _plan: current
    )
    monkeypatch.setattr(
        "tools.official_index_lineage.recovery.ingest_snapshot_sha256", lambda: "2" * 64
    )
    monkeypatch.setattr(
        "tools.official_index_lineage.recovery.sha256_file", lambda _path: "4" * 64
    )
    effective_path = tmp_path / "effective.yaml"
    write_immutable_yaml(effective_path, build_effective_protocol(config, original))
    refresh = {
        "refreshed_target_evidence": refreshed,
        "probe": {
            **probes[request_pair(target)],
            "row_count": 200,
            "first_canonical_sha256": "3" * 64,
            "second_canonical_sha256": "3" * 64,
        },
    }
    payload = build_collection_report(
        config, effective_path, report, plan, evidence, probes, refresh
    )
    assert payload["reused_request_count"] == 26
    assert payload["refresh_query_count"] == 2
    assert payload["original_target_evidence"]["batch_id"] == "33aa80a00744"
    assert payload["refreshed_target_evidence"]["batch_id"] == "new-batch"


def test_completed_collection_reuses_without_provider(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config, original, report = _frozen_inputs()
    plan, evidence, _ = validate_original_collection(config, original, report)
    effective_path = tmp_path / "effective.yaml"
    write_immutable_yaml(effective_path, build_effective_protocol(config, original))
    current = [copy.deepcopy(evidence[request_pair(request)]) for request in plan]
    target = target_request(config)
    refreshed = current[plan.index(target)]
    refreshed["batch_id"] = "new-batch"
    payload = {
        "protocol_config_sha256": sha256_file(effective_path),
        "request_evidence": current,
        "reused_request_count": 26,
        "refreshed_request_count": 1,
        "refresh_query_count": 2,
        "revision_mismatch_count": 0,
        "original_target_evidence": evidence[request_pair(target)],
        "refreshed_target_evidence": refreshed,
    }
    collection_path = tmp_path / "collection.json"
    collection_path.write_text(json.dumps(payload), encoding="utf-8")
    probe_path = tmp_path / "target_refresh_probe.json"
    probe_path.write_text(
        json.dumps({"query_count": 2, "refreshed_target_evidence": refreshed}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "tools.official_index_lineage.recovery._current_evidence",
        lambda _plan: payload["request_evidence"],
    )
    assert _load_completed_collection(
        collection_path, effective_path, plan, evidence, target, probe_path
    ) == payload


def test_counting_client_never_allows_a_third_query() -> None:
    class Client:
        def query(self, api_name: str, **kwargs: object):  # noqa: ANN202
            return None

    client = _CountingClient(Client(), maximum=2)
    client.query("index_weight")
    client.query("index_weight")
    with pytest.raises(DataGateError, match="exceeded"):
        client.query("index_weight")


def test_stable_collector_rejects_bse_and_double_query_mismatch() -> None:
    request = target_request(_frozen_inputs()[0])
    bse = pd.DataFrame(
        [{"index_code": "000699.SH", "con_code": "920001.BJ", "trade_date": "20260731", "weight": 1.0}]
    )
    first = pd.DataFrame(
        [{"index_code": "000699.SH", "con_code": "688001.SH", "trade_date": "20260731", "weight": 1.0}]
    )

    class Client:
        def __init__(self, frames: tuple[pd.DataFrame, ...]) -> None:
            self.frames = iter(frames)

        def query(self, api_name: str, **kwargs: object) -> pd.DataFrame:
            return next(self.frames)

    class Writer:
        def write(self, **kwargs: object):  # noqa: ANN202
            raise AssertionError("invalid responses must not be committed")

    settings = SimpleNamespace(
        ingest=SimpleNamespace(
            max_attempts=1,
            min_request_interval_seconds=0,
            retry_base_seconds=0,
            source_row_limit=6000,
        )
    )
    with pytest.raises(DataGateError, match="forbidden .BJ"):
        StableCollector(
            client=Client((bse,)), writer=Writer(), settings=settings, operator="fixture"
        ).collect(request)
    with pytest.raises(DataGateError, match="revision mismatch"):
        StableCollector(
            client=Client((first, first.assign(weight=2.0))),
            writer=Writer(),
            settings=settings,
            operator="fixture",
        ).collect(request)
