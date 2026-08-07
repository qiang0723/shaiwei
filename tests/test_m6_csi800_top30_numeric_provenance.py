from __future__ import annotations

import copy
import json
from pathlib import Path

import pandas as pd
import pytest
import yaml

from shaiwei.research.top30_diagnostic.exact import DiagnosticError, canonical_sha256, exact_rows
from shaiwei.research.top30_provenance.audit import audit
from shaiwei.research.top30_provenance.classification import classify
from shaiwei.research.top30_provenance.collector import collect
from shaiwei.research.top30_provenance.contract import Protocol, tree_identity
from shaiwei.research.top30_provenance.topology import compare_rows, ulp_distance


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n")


def test_protocol_preserves_zero_backtest_and_no_retry() -> None:
    protocol = Protocol.load()
    authority = protocol.document["authority"]
    execution = protocol.document["execution_contract"]
    assert authority["top30_backtest_authorized"] is False
    assert authority["top20_read_or_backtest_authorized"] is False
    assert authority["qlib_provider_mount_or_read_authorized"] is False
    assert execution["total_top30_backtest_count"] == 0
    assert execution["top20_backtest_count"] == 0
    assert execution["same_scope_retry_authorized"] is False


def test_ulp_and_classification_contract() -> None:
    adjacent = float.fromhex("0x1.0000000000001p+0")
    assert ulp_distance(1.0, adjacent) == 1
    assert classify({
        "unique_cause_proven": True,
        "competing_explanation_count": 0,
        "canonical_producer_identity_complete": True,
        "input_identity_pass": True,
    }) == "ROOT_CAUSE_IDENTIFIED"
    assert classify({
        "unique_cause_proven": False,
        "competing_explanation_count": 2,
        "canonical_producer_identity_complete": True,
        "input_identity_pass": True,
    }) == "PRODUCER_ENVIRONMENT_IDENTIFIED_NOT_CAUSALLY_PROVEN"
    assert classify({"canonical_producer_identity_complete": False}) == "PROVENANCE_GAP_CONFIRMED"


def test_topology_counts_fields_and_direction() -> None:
    base = {
        "date": "2020-01-01",
        "gross_return": 1.0.hex(),
        "benchmark_return": 0.0.hex(),
        "recorded_cost": 0.0.hex(),
        "turnover": 0.0.hex(),
    }
    actual = {**base, "gross_return": float.fromhex("0x1.0000000000001p+0").hex()}
    result = compare_rows([base], [actual])
    assert result["mismatch_by_field"] == {"gross_return": 1}
    assert result["ulp"]["one_ulp_count"] == 1
    assert result["difference_direction"] == {"positive": 1}


def _fixture(tmp_path: Path) -> dict[str, Path]:
    protocol = Protocol.load()
    protocol_path = tmp_path / "protocol.yaml"
    protocol_path.write_text(yaml.safe_dump(protocol.document, sort_keys=False))
    canonical_path = tmp_path / "canonical.parquet"
    frame = pd.DataFrame({
        "datetime": pd.to_datetime(["2020-01-01", "2020-01-02"]),
        "gross_return": [0.01, 0.02],
        "benchmark_return": [0.001, 0.002],
        "recorded_cost": [0.0001, 0.0002],
        "turnover": [0.1, 0.2],
    })
    frame.to_parquet(canonical_path, index=False)
    canonical = exact_rows(frame.set_index("datetime"))
    changed = copy.deepcopy(canonical)
    changed[0]["gross_return"] = float.fromhex("0x1.47ae147ae147cp-7").hex()
    r2 = tmp_path / "r2"
    original_bundle = {
        "canonical_rows": canonical,
        "adapters": {"original_execution": {
            "replay_1": {"rows": changed}, "replay_2": {"rows": changed}
        }},
    }
    current_bundle = {
        "canonical_rows": canonical,
        "adapters": {
            "original_execution": {"replay_1": {"rows": changed}, "replay_2": {"rows": changed}},
            "new_execution": {"replay_1": {"rows": changed}, "replay_2": {"rows": changed}},
        },
    }
    _write(r2 / "original/bundle.json", original_bundle)
    _write(r2 / "current/bundle.json", current_bundle)
    _write(r2 / "audit/audit.json", {"diagnostics": {"cross_lane_exact_equal": {
        "original_vs_canonical": False,
        "failed_original_vs_canonical": False,
        "failed_new_vs_canonical": False,
        "original_vs_failed_original": True,
        "failed_original_vs_failed_new": True,
        "original_vs_failed_new": True,
    }}})
    scope = {
        "scope_kind": "TOP30_NUMERIC_PROVENANCE_READ_ONLY_EXECUTION",
        "protocol_sha256": protocol_path_sha(protocol_path),
        "authority": {
            "execution_authorized": True,
            "top30_backtest_authorized": False,
            "top20_read_or_backtest_authorized": False,
            "qlib_read_authorized": False,
            "model_fit_authorized": False,
            "prediction_generation_authorized": False,
            "external_network_authorized": False,
        },
        "inputs": {
            "canonical_report": {"sha256": file_sha(canonical_path), "size": canonical_path.stat().st_size},
            "r2_diagnostic_tree": tree_identity(r2),
        },
        "images": {
            "original": {"git_commit": "a" * 40, "base_image_id": "sha256:" + "1" * 64},
            "failed": {"git_commit": "b" * 40, "base_image_id": "sha256:" + "2" * 64},
        },
    }
    scope_path = tmp_path / "scope.json"
    scope_sha = canonical_sha256(scope)
    _write(scope_path, {
        "schema_version": "m6-top30-numeric-provenance-release-scope-v1",
        "provenance_scope_sha256": scope_sha,
        "scope": scope,
    })
    probes = tmp_path / "probes"
    common_probe = {
        "schema_version": "m6-top30-numeric-provenance-image-probe-v1",
        "provenance_scope_sha256": scope_sha,
        "python": {"version": "3.11"},
        "platform": {"machine": "aarch64"},
        "distributions": {"numpy": "1.26.4"},
        "numpy_build": {},
        "thread_environment_names_present": ["OMP_NUM_THREADS"],
        "source_identity": {"effect_execution.py": {"present": True, "sha256": "c" * 64}},
        "top30_backtest_count": 0,
        "top20_backtest_count": 0,
    }
    for role, commit, base in (("original", "a" * 40, "1" * 64), ("failed", "b" * 40, "2" * 64)):
        _write(probes / f"{role}.json", {
            **common_probe,
            "runtime_identity": {"role": role, "git_commit": commit, "base_image_id": "sha256:" + base},
        })
    original_release = tmp_path / "original-release.json"
    _write(original_release, {"scope": {
        "image": {
            "image_id": "sha256:" + "1" * 64,
            "git_commit": "a" * 40,
            "code_snapshot_sha256": "d" * 64,
            "release_manifest_sha256": "e" * 64,
            "platform": "linux/arm64",
        },
        "inputs": {"qlib_tree_sha256": "q" * 64},
    }})
    failed_release = tmp_path / "failed-release.json"
    _write(failed_release, {"scope": {"inputs": {"qlib": {"qlib_tree_sha256": "q" * 64}}}})
    canonical_compose = tmp_path / "canonical-compose.yaml"
    diagnostic_compose = tmp_path / "diagnostic-compose.yaml"
    canonical_compose.write_text(_compose("m6-effect-runner", 6, "6"))
    diagnostic_compose.write_text(_compose("m6-top30-diagnostic-recovery-original", 2, "1"))
    return {
        "protocol_path": protocol_path,
        "release_path": scope_path,
        "canonical_path": canonical_path,
        "r2_root": r2,
        "original_probe_path": probes / "original.json",
        "failed_probe_path": probes / "failed.json",
        "original_release_path": original_release,
        "failed_release_path": failed_release,
        "canonical_compose_path": canonical_compose,
        "diagnostic_compose_path": diagnostic_compose,
        "output_root": tmp_path / "collector",
    }


def _compose(service: str, cpus: int, threads: str) -> str:
    return yaml.safe_dump({"services": {service: {
        "image": "fixture",
        "command": ["python", service],
        "cpus": cpus,
        "mem_limit": "1g",
        "pids_limit": 64,
        "environment": {name: threads for name in (
            "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"
        )},
        "network_mode": "none",
        "read_only": True,
    }}})


def file_sha(path: Path) -> str:
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest()


def protocol_path_sha(path: Path) -> str:
    return file_sha(path)


def test_collector_and_independent_audit(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    result = collect(**paths)
    assert result["classification"] == "PRODUCER_ENVIRONMENT_IDENTIFIED_NOT_CAUSALLY_PROVEN"
    audit_paths = {
        key: paths[key]
        for key in (
            "protocol_path", "release_path", "canonical_path", "r2_root",
            "original_probe_path", "failed_probe_path",
        )
    }
    audited = audit(
        **audit_paths,
        collector_root=paths["output_root"],
        audit_root=tmp_path / "audit",
    )
    assert audited["classification"] == result["classification"]


def test_collector_fails_closed_on_probe_identity(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    probe = json.loads(paths["original_probe_path"].read_text())
    probe["runtime_identity"]["base_image_id"] = "sha256:" + "9" * 64
    _write(paths["original_probe_path"], probe)
    with pytest.raises(DiagnosticError, match="image probe differs"):
        collect(**paths)
