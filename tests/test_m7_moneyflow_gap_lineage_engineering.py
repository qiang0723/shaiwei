from __future__ import annotations

import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest
import pyarrow as pa
import pyarrow.parquet as pq
import yaml

from shaiwei.research_gates.m7_moneyflow.consumption import M7GateError
from shaiwei.research_gates.m7_moneyflow.contract import canonical_json, sha256_file
from shaiwei.research_gates.m7_moneyflow_lineage import runner
from shaiwei.research_gates.m7_moneyflow_lineage.audit_compute import recompute_lineage_core
from shaiwei.research_gates.m7_moneyflow_lineage.compute import compute_lineage_core
from shaiwei.research_gates.m7_moneyflow_lineage.contract import (
    CATEGORIES,
    LineageInputManifest,
    LineageProtocol,
)
from shaiwei.research_gates.m7_moneyflow_lineage.fixture import synthetic_inputs
from shaiwei.research_gates.m7_moneyflow_lineage.reader import _query_sources
from shaiwei.research_gates.m7_moneyflow_lineage.release import LineageRelease
from shaiwei.research_gates.m7_moneyflow_lineage.release_builder import (
    build_release_document,
)


ROOT = Path(__file__).resolve().parents[1]


def _protocol() -> LineageProtocol:
    return LineageProtocol.load(
        ROOT / "config/m7_moneyflow_gap_lineage_v1.yaml",
        project_root=ROOT,
    )


def test_lineage_all_categories_partition_and_independent_audit_match() -> None:
    protocol = _protocol()
    main = compute_lineage_core(protocol, synthetic_inputs())
    audit = recompute_lineage_core(protocol, synthetic_inputs())
    assert main == audit
    assert main["lineage_partition"]["category_counts"] == {category: 3 for category in CATEGORIES}
    assert main["dataset_and_grain"]["missing_row_count"] == 30
    assert main["lineage_partition"]["partition_delta"] == 0
    assert main["verdict"] == "NO_GO_M7_GAP_LINEAGE_INCOMPLETE"
    assert main["authority"]["adjusted_or_counterfactual_coverage_computed"] is False


def test_lineage_runner_consumes_before_loader_and_cannot_retry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    protocol = _protocol()
    manifest = SimpleNamespace(sha256="1" * 64, physical_sha256="2" * 64)
    release = SimpleNamespace(
        sha256="3" * 64,
        scope={"implementation": {"code_bundle_sha256": "4" * 64}},
    )
    approval = SimpleNamespace(sha256="5" * 64)
    calls = {"count": 0}

    def loader(*args: object, **kwargs: object) -> object:
        calls["count"] += 1
        return synthetic_inputs()

    monkeypatch.setattr(runner, "load_lineage_inputs", loader)
    report = runner.build_report(
        protocol,
        manifest,
        release,
        approval,
        input_root=tmp_path,
        claim_root=tmp_path / "claims",
    )
    assert report["pre_read_consumption"]["role"] == "runner"
    assert calls["count"] == 1
    with pytest.raises(M7GateError, match="already consumed"):
        runner.build_report(
            protocol,
            manifest,
            release,
            approval,
            input_root=tmp_path,
            claim_root=tmp_path / "claims",
        )
    assert calls["count"] == 1


def test_lineage_reader_projects_only_keys_and_status_from_synthetic_parquet(
    tmp_path: Path,
) -> None:
    rows = {
        "tushare.daily": {
            "ts_code": ["688001.SH", "000001.SZ"],
            "trade_date": ["20210104", "20210104"],
            "close": [10.0, 20.0],
        },
        "tushare.suspend_d": {
            "ts_code": ["688001.SH", "688001.SH"],
            "trade_date": ["20210104", "20210104"],
            "suspend_timing": [None, "09:30-10:30"],
            "suspend_type": ["S", "S"],
        },
        "baostock.history_k_data_plus": {
            "ts_code": ["688001.SH", "688001.SH"],
            "trade_date": ["20210104", "20210104"],
            "trade_status": ["0", "1"],
        },
    }
    sources = {}
    for source_api, values in rows.items():
        path = tmp_path / f"{source_api}.parquet"
        pq.write_table(pa.Table.from_pydict(values), path)
        metadata = pq.read_metadata(path)
        sources[source_api] = {
            "batches": [
                {
                    "bundle_relative_path": path.name,
                    "bytes": path.stat().st_size,
                    "row_count": metadata.num_rows,
                    "schema_fields": list(metadata.schema.names),
                    "content_sha256": sha256_file(path),
                }
            ]
        }
    manifest = SimpleNamespace(document={"sources": sources})
    membership = synthetic_inputs().membership.loc[lambda frame: frame["ts_code"].eq("688001.SH")]
    daily, suspend, independent, evidence = _query_sources(
        manifest,
        input_root=tmp_path,
        membership=membership,
        start="20210104",
        end="20210104",
    )
    assert daily.to_dict("records") == [{"ts_code": "688001.SH", "trade_date": "20210104"}]
    assert suspend[["primary_full_day", "primary_intraday"]].iloc[0].tolist() == [1, 1]
    assert independent[["independent_nontrading", "independent_trading"]].iloc[0].tolist() == [1, 1]
    assert evidence["numeric_daily_value_columns_read"] == 0


def test_lineage_release_is_non_executable_and_binds_role_specific_mounts(
    tmp_path: Path,
) -> None:
    protocol = _protocol()
    manifest = SimpleNamespace(sha256="1" * 64, physical_sha256="2" * 64)
    implementation = {
        "git_commit": "a" * 40,
        "origin_main_commit": "a" * 40,
        "commit_pushed_before_scope": True,
        "code_bundle_sha256": "3" * 64,
        "requirements_lock_sha256": "4" * 64,
        "dockerfile_sha256": "5" * 64,
        "compose_sha256": "6" * 64,
        "auditor_code_sha256": "7" * 64,
        "approval_builder_sha256": "8" * 64,
    }
    document = build_release_document(
        protocol,
        manifest,
        created_at="2026-08-09T00:30:00+08:00",
        implementation=implementation,
        image_id="sha256:" + "9" * 64,
        repo_digest="shaiwei:m7@sha256:" + "a" * 64,
        platform="linux/arm64",
    )
    path = tmp_path / "release.json"
    path.write_text(canonical_json(document) + "\n", encoding="utf-8")
    release = LineageRelease.load(path, protocol, manifest)
    assert release.scope["authority"]["execution_authorized"] is False
    mounts = release.scope["container"]["mounts"]
    assert {item["role"] for item in mounts} == {"runner", "auditor"}
    assert (
        next(item for item in mounts if item["role"] == "auditor" and item["target"] == "/outputs")["mode"]
        == "ro"
    )


def test_lineage_docker_contract_is_isolated_and_narrow() -> None:
    compose = yaml.safe_load((ROOT / "compose.m7-moneyflow-gap-lineage.yaml").read_text(encoding="utf-8"))
    for service in compose["services"].values():
        assert service["network_mode"] == "none"
        assert service["read_only"] is True
        assert service["user"] == "65532:65532"
        assert service["cap_drop"] == ["ALL"]
        assert service["security_opt"] == ["no-new-privileges:true"]
    serialized = json.dumps(compose)
    for forbidden in ("/workspace", ".env", ".git", "docker.sock"):
        assert forbidden not in serialized


def test_lineage_metadata_summary_matches_untracked_full_manifest() -> None:
    protocol = _protocol()
    full_path = ROOT / "data/control/m7-lineage/input-manifest-v1.json"
    if not full_path.is_file():
        pytest.skip("local metadata-only lineage manifest is intentionally Git-ignored")
    manifest = LineageInputManifest.load(full_path, protocol)
    summary = json.loads(
        (ROOT / "config/m7_moneyflow_gap_lineage_input_manifest_v1.json").read_text(encoding="utf-8")
    )
    assert summary["full_manifest"]["canonical_sha256"] == manifest.sha256
    assert summary["full_manifest"]["physical_sha256"] == manifest.physical_sha256
    assert summary["full_manifest"]["bytes"] == full_path.stat().st_size
    assert summary["full_manifest"]["semantic_rows_read"] is False
    for source_api, item in summary["sources"].items():
        full = manifest.document["sources"][source_api]
        for field in (
            "projected_columns",
            "selected_batch_count",
            "selected_row_count",
            "selected_bytes",
            "catalog_sha256",
        ):
            assert item[field] == full[field]
    assert re.search(r'"[0-9]{6}\.(?:SH|SZ|BJ)"', full_path.read_text(encoding="utf-8")) is None


def test_lineage_modules_stay_below_architecture_soft_limit() -> None:
    package = ROOT / "src/shaiwei/research_gates/m7_moneyflow_lineage"
    assert {path.name: len(path.read_text(encoding="utf-8").splitlines()) for path in package.glob("*.py")}
    assert max(len(path.read_text(encoding="utf-8").splitlines()) for path in package.glob("*.py")) <= 400
