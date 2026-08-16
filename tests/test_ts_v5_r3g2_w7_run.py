from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from shaiwei.research.trend_swing.r3g2.contract import EffectProtocol, R3G2Error
from shaiwei.research.trend_swing.r3g2.w7_audit_run import run_audit
from shaiwei.research.trend_swing.r3g2.w7_control import ACTION, load_release_protocol
from shaiwei.research.trend_swing.r3g2.w7_lineage import W7Output, save_pass
from shaiwei.research.trend_swing.r3g2.w7_release import build_release_document
from shaiwei.research.trend_swing.r3g2.w7_run import run


COMMIT = "a" * 40
SNAPSHOT = "b" * 64
INPUTS = {
    "qlib_manifest_sha256": "62cae2f46b57020db202bee1748f072e7859e209663046747f76aaa008f605a9",
    "qlib_tree_sha256": "0532f6cd7c2c78f0936f92a986aef83a848175fe6f332274e06c7ed6e8c11778",
    "qlib_file_count": 54464,
    "calendar_sha256": "80ddefd8e3cce5137bb99f6b53dbe090de1b1bd234db1a19f31ef3ddb2bd8bdb",
    "calendar_row_count": 2557,
}


def _control_files(tmp_path: Path) -> tuple[Path, Path, dict[str, Any]]:
    protocol = EffectProtocol.load()
    release_protocol, release_protocol_sha = load_release_protocol(protocol)
    document = build_release_document(
        protocol=protocol,
        release_protocol=release_protocol,
        release_protocol_sha256=release_protocol_sha,
        created_at="2026-08-17T00:00:00+00:00",
        implementation_git_commit=COMMIT,
        origin_main_commit=COMMIT,
        code_snapshot=SNAPSHOT,
        image_id=f"sha256:{'c' * 64}",
        image_platform="linux/arm64",
        image_git_commit=COMMIT,
        image_release_manifest_sha256="d" * 64,
        image_release_manifest_file_count=100,
        inputs=INPUTS,
    )
    scope, scope_sha = document["scope"], document["release_scope_sha256"]
    release = tmp_path / "release.json"
    release.write_text(json.dumps(document, sort_keys=True) + "\n", encoding="utf-8")
    approval = tmp_path / "approval.json"
    approval.write_text(
        json.dumps(
            {
                "schema_version": "ts-v5-r3g2-w7-explicit-approval-v1",
                "release_scope_sha256": scope_sha,
                "action": ACTION,
                "approved": True,
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return release, approval, scope


def _output() -> W7Output:
    index = pd.MultiIndex.from_tuples(
        [
            (pd.Timestamp("2025-01-02"), "000001.SZ"),
            (pd.Timestamp("2025-01-03"), "000001.SZ"),
        ],
        names=["datetime", "instrument"],
    )
    return W7Output(pd.Series([0.1, 0.2], index=index, name="score"), b"model\n")


def _pass(root: Path, protocol: EffectProtocol, _provider: Path) -> dict[str, Any]:
    return save_pass(root, _output(), protocol)


def _runtime(_release: object) -> dict[str, str]:
    return {"git_commit": COMMIT, "code_snapshot_sha256": SNAPSHOT}


def test_one_shot_runner_and_separate_auditor_close_the_fixture(tmp_path: Path) -> None:
    release, approval, _scope = _control_files(tmp_path)
    lineage, audit = tmp_path / "lineage", tmp_path / "audit"
    result = run(
        release_path=release,
        approval_path=approval,
        provider_root=tmp_path / "qlib",
        output_root=lineage,
        pass_runner=_pass,
        initializer=lambda _root: None,
        input_verifier=lambda _release, _root: INPUTS,
        runtime_verifier=_runtime,
    )

    assert result["verdict"] == "PENDING_INDEPENDENT_W7_LINEAGE_AUDIT"
    report = json.loads((lineage / "report.json").read_text(encoding="utf-8"))
    assert report["strategy_effect_attempt_count"] == 0
    assert report["label_rankic_return_or_effect_read"] is False
    assert report["first_pass"]["bundle_sha256"] == report["replay"]["bundle_sha256"]

    audited = run_audit(
        release_path=release,
        approval_path=approval,
        lineage_root=lineage,
        audit_root=audit,
        runtime_verifier=_runtime,
    )
    assert audited["verdict"] == "GO_W7_SCORE_LINEAGE_DATA_ONLY"
    audit_document = json.loads((audit / "audit.json").read_text(encoding="utf-8"))
    assert audit_document["strategy_effect_attempt_count"] == 0
    assert audit_document["production_authorization"] == "none"


def test_same_release_cannot_run_twice(tmp_path: Path) -> None:
    release, approval, _scope = _control_files(tmp_path)
    kwargs = {
        "release_path": release,
        "approval_path": approval,
        "provider_root": tmp_path / "qlib",
        "output_root": tmp_path / "lineage",
        "pass_runner": _pass,
        "initializer": lambda _root: None,
        "input_verifier": lambda _release, _root: INPUTS,
        "runtime_verifier": _runtime,
    }
    run(**kwargs)
    with pytest.raises(R3G2Error, match="output exists"):
        run(**kwargs)


def test_failure_after_lineage_start_is_sealed_without_effect_attempt(tmp_path: Path) -> None:
    release, approval, _scope = _control_files(tmp_path)

    def broken(_root: Path, _protocol: EffectProtocol, _provider: Path) -> dict[str, Any]:
        raise RuntimeError("synthetic fit failure")

    output = tmp_path / "lineage"
    with pytest.raises(RuntimeError, match="synthetic fit failure"):
        run(
            release_path=release,
            approval_path=approval,
            provider_root=tmp_path / "qlib",
            output_root=output,
            pass_runner=broken,
            initializer=lambda _root: None,
            input_verifier=lambda _release, _root: INPUTS,
            runtime_verifier=_runtime,
        )
    failure = json.loads((output / "failure.json").read_text(encoding="utf-8"))
    assert failure["lineage_read_started"] is True
    assert failure["strategy_effect_attempt_count"] == 0
    assert failure["same_release_retry_authorized"] is False


def test_approval_must_match_the_exact_scope(tmp_path: Path) -> None:
    release, approval, _scope = _control_files(tmp_path)
    document = json.loads(approval.read_text(encoding="utf-8"))
    document["action"] = "DIFFERENT"
    approval.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(R3G2Error, match="explicit approval differs"):
        run(
            release_path=release,
            approval_path=approval,
            provider_root=tmp_path / "qlib",
            output_root=tmp_path / "lineage",
            pass_runner=_pass,
            initializer=lambda _root: None,
            input_verifier=lambda _release, _root: INPUTS,
            runtime_verifier=_runtime,
        )
