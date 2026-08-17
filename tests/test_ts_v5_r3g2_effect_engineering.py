from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
import yaml

from shaiwei.provenance import (
    CONTROLLED_FILES,
    code_snapshot_sha256,
    git_head,
    write_release_manifest,
)
from shaiwei.research.trend_swing.r3g2.contract import EffectProtocol, R3G2Error
from shaiwei.research.trend_swing.r3g2.effect_audit import audit
from shaiwei.research.trend_swing.r3g2.effect_control import (
    ACTION,
    ReleaseProtocol,
    canonical_sha256,
    expected_approval,
    expected_scope_authority,
)
from shaiwei.research.trend_swing.r3g2.effect_execution import simulate
from shaiwei.research.trend_swing.r3g2.effect_fees import fees, opening_legal
from shaiwei.research.trend_swing.r3g2.effect_fixture import SyntheticAdapter, _partition
from shaiwei.research.trend_swing.r3g2.effect_inputs import (
    _normalize_prediction,
    _tushare_code,
)
from shaiwei.research.trend_swing.r3g2.effect_models import scenario
from shaiwei.research.trend_swing.r3g2.effect_release import (
    AUDITOR_COMMAND,
    RUNNER_COMMAND,
    _mounts,
    build_release_document,
)
from shaiwei.research.trend_swing.r3g2.effect_run import execute_pass, run


ROOT = Path(__file__).parents[1]


def _scope(preflight: dict, manifest_sha256: str) -> dict:
    protocol, release = EffectProtocol.load(), ReleaseProtocol.load()
    head, snapshot = git_head(), code_snapshot_sha256()
    scope = {
        "scope_kind": "REAL_EFFECT_RELEASE_READY_NOT_EXECUTION_APPROVAL",
        "effect_protocol_sha256": protocol.sha256,
        "release_protocol_sha256": release.sha256,
        "authority": expected_scope_authority(),
        "execution": {
            "approval_action": ACTION,
            "strategy_effect_attempt_count": 3,
            "same_release_retry_authorized": False,
        },
        "container": {
            "network_mode": "none",
            "read_only_root": True,
            "env_file_mounted": False,
            "docker_socket_mounted": False,
            "production_ledger_mounted": False,
            "frozen_research_lineage_ledgers_mounted": True,
            "full_project_root_mounted": False,
            "runner": {"command": RUNNER_COMMAND},
            "auditor": {"command": AUDITOR_COMMAND},
        },
        "implementation": {
            "git_commit": head,
            "origin_main_commit": head,
            "code_snapshot_sha256": snapshot,
        },
        "image": {
            "reference": "shaiwei:ts-v5-r3g2-effect-release-v1",
            "git_commit": head,
            "release_manifest_sha256": manifest_sha256,
        },
        "inputs": {"pre_effect_preflight_sha256": canonical_sha256(preflight)},
        "outputs": {
            "effect_root": "data/research/trend_swing/ts-v5-r3g2-effect-v1",
            "audit_root": "data/research/trend_swing/ts-v5-r3g2-effect-v1-audit",
            "empty_at_scope_freeze": True,
            "approval_file_exists_at_scope_freeze": False,
        },
    }
    return {
        "schema_version": "ts-v5-r3g2-effect-release-scope-v1",
        "release_scope_sha256": canonical_sha256(scope),
        "scope": scope,
    }


def _control(tmp_path: Path) -> tuple[Path, Path, Path, SyntheticAdapter]:
    protocol = EffectProtocol.load()
    adapter = SyntheticAdapter(protocol, tmp_path / "tmp")
    manifest = tmp_path / "release-manifest.json"
    write_release_manifest(manifest, root=ROOT)
    import hashlib

    document = _scope(adapter.preflight(), hashlib.sha256(manifest.read_bytes()).hexdigest())
    release = tmp_path / "release.json"
    release.write_text(json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n")
    approval = tmp_path / "approval.json"
    approval.write_text(
        json.dumps(
            expected_approval(document["release_scope_sha256"]),
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )
    return release, approval, manifest, adapter


def test_synthetic_positive_pass_opens_holdout_and_replays_exactly(tmp_path: Path) -> None:
    protocol = EffectProtocol.load()
    adapter = SyntheticAdapter(protocol, tmp_path / "tmp")
    first = execute_pass(tmp_path / "first", protocol, adapter)
    replay = execute_pass(tmp_path / "replay", protocol, adapter)

    assert first["verdict"] == "GO_TS_V5_R3G2_HISTORICAL_REVIEW_ONLY"
    assert first["holdout_outcomes_opened"] is True
    assert first["bundle_sha256"] == replay["bundle_sha256"]
    assert adapter.holdout_load_count == 2


def test_discovery_reject_physically_keeps_holdout_unread(tmp_path: Path) -> None:
    protocol = EffectProtocol.load()
    adapter = SyntheticAdapter(protocol, tmp_path / "tmp", losing_discovery=True)
    result = execute_pass(tmp_path / "pass", protocol, adapter)

    assert result["verdict"] == "REJECT_TS_V5_R3G2_DISCOVERY"
    assert result["holdout_outcomes_opened"] is False
    assert adapter.holdout_load_count == 0
    assert not (tmp_path / "pass/holdout").exists()


def test_second_batch_t_plus_one_and_position_exit_clock_are_lot_aware() -> None:
    protocol = EffectProtocol.load()
    prepared = _partition(protocol, "holdout")
    point = protocol.selected_point_hashes[0]
    event = prepared.events.loc[prepared.events["point_hash"].eq(point)].iloc[[0]].copy()
    code = str(event.iloc[0]["ts_code"])
    bars = prepared.bars.loc[prepared.bars["ts_code"].eq(code)].copy()
    result = simulate(
        events=event,
        bars=bars,
        benchmark=prepared.benchmark,
        calendar=prepared.calendar,
        current=scenario("base_1x"),
    )
    trades = pd.DataFrame(result.trade_rows)
    buys = trades.loc[trades["side"].eq("BUY")].sort_values("trade_date")
    sells = trades.loc[trades["side"].eq("SELL")].sort_values("trade_date")

    assert buys["batch"].tolist() == [1, 2]
    assert sells.iloc[0]["trade_date"] == buys.iloc[1]["trade_date"]
    assert sells.iloc[0]["closed_trade"] is False or not bool(sells.iloc[0]["closed_trade"])
    assert sells.iloc[-1]["trade_date"] > buys.iloc[1]["trade_date"]
    assert bool(sells.iloc[-1]["closed_trade"]) is True
    assert float(buys["gross_notional"].sum()) <= 25_000.0


def test_limit_schedule_and_fee_stress_are_explicit() -> None:
    row = {
        "ts_code": "300001.SZ",
        "trade_date": "20200821",
        "raw_open": 11.0,
        "prior_raw_close": 10.0,
        "volume_shares": 1_000.0,
        "security_eligible": True,
        "listing_session_age": 100,
    }
    assert opening_legal(row, "BUY") is False
    row["trade_date"] = "20200824"
    assert opening_legal(row, "BUY") is True
    base = fees(100_000.0, "SELL", "20240102", scenario("base_1x"))
    stressed = fees(100_000.0, "SELL", "20240102", scenario("all_costs_2x"))
    assert stressed == pytest.approx(2 * base)


def test_qlib_instrument_codes_map_explicitly_to_tushare_keys() -> None:
    assert _tushare_code("SH600000") == "600000.SH"
    assert _tushare_code("SZ000001") == "000001.SZ"
    assert _tushare_code("688001.SH") == "688001.SH"
    with pytest.raises(R3G2Error, match="code format"):
        _tushare_code("BJ430001")


def test_nonfinite_score_values_fail_closed() -> None:
    frame = pd.DataFrame(
        {"datetime": ["2025-01-02"], "instrument": ["SH600000"], "score": [float("inf")]}
    )
    with pytest.raises(R3G2Error, match="nonfinite"):
        _normalize_prediction(frame, include_values=True)


def test_one_shot_runner_and_independent_auditor_close_synthetic_scope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    release, approval, manifest, _ = _control(tmp_path)
    monkeypatch.setenv("SHAIWEI_RELEASE_GIT_HEAD", git_head())
    monkeypatch.setenv("SHAIWEI_RELEASE_MANIFEST", str(manifest))
    result = run(
        release_path=release,
        approval_path=approval,
        output_root=tmp_path / "effect",
        temporary_root=tmp_path / "tmp",
        adapter_factory=lambda protocol, temporary: SyntheticAdapter(protocol, temporary),
    )
    audited = audit(
        release_path=release,
        approval_path=approval,
        effect_root=tmp_path / "effect",
        audit_root=tmp_path / "audit",
    )
    assert result["strategy_effective"] == "PENDING_INDEPENDENT_AUDIT"
    assert audited["independent_audit"] == "PASS"
    assert audited["strategy_effective"] == "HISTORICAL_GO_NOT_PRODUCTION"
    summary = json.loads(
        next((tmp_path / "effect/first_pass/discovery").rglob("summary.json")).read_text()
    )
    assert {
        "capacity_limited_order_count",
        "mean_holding_days",
        "maximum_security_weight",
        "maximum_industry_weight",
        "maximum_absolute_trade_pnl_share",
        "maximum_absolute_security_pnl_share",
        "maximum_absolute_industry_pnl_share",
        "corporate_action_overlap_count",
    } <= set(summary)
    with pytest.raises(R3G2Error, match="output exists"):
        run(
            release_path=release,
            approval_path=approval,
            output_root=tmp_path / "effect",
            temporary_root=tmp_path / "tmp2",
            adapter_factory=lambda protocol, temporary: SyntheticAdapter(protocol, temporary),
        )


def test_independent_auditor_detects_tampering(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    release, approval, manifest, _ = _control(tmp_path)
    monkeypatch.setenv("SHAIWEI_RELEASE_GIT_HEAD", git_head())
    monkeypatch.setenv("SHAIWEI_RELEASE_MANIFEST", str(manifest))
    run(
        release_path=release,
        approval_path=approval,
        output_root=tmp_path / "effect",
        temporary_root=tmp_path / "tmp",
        adapter_factory=lambda protocol, temporary: SyntheticAdapter(protocol, temporary),
    )
    target = next((tmp_path / "effect/first_pass/discovery").rglob("nav.parquet"))
    target.write_bytes(target.read_bytes() + b"tamper")
    with pytest.raises(R3G2Error, match="manifest differs"):
        audit(
            release_path=release,
            approval_path=approval,
            effect_root=tmp_path / "effect",
            audit_root=tmp_path / "audit",
        )


def test_runtime_preflight_failure_is_sealed_before_effect_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    release, approval, manifest, _ = _control(tmp_path)
    monkeypatch.setenv("SHAIWEI_RELEASE_GIT_HEAD", git_head())
    monkeypatch.setenv("SHAIWEI_RELEASE_MANIFEST", str(manifest))

    class DriftedPreflight(SyntheticAdapter):
        def preflight(self) -> dict:
            document = super().preflight()
            document["partitions"]["discovery"] = {"synthetic": False}
            return document

    with pytest.raises(R3G2Error, match="pre-effect key preflight identity differs"):
        run(
            release_path=release,
            approval_path=approval,
            output_root=tmp_path / "effect",
            temporary_root=tmp_path / "tmp",
            adapter_factory=lambda protocol, temporary: DriftedPreflight(protocol, temporary),
        )
    failure = json.loads((tmp_path / "effect/failure.json").read_text())
    assert failure["effect_read_started"] is False
    assert failure["strategy_effect_attempt_count"] == 0
    assert not (tmp_path / "effect/effect_read_started.json").exists()


def test_release_document_is_metadata_only_and_compose_matches(tmp_path: Path) -> None:
    protocol, release = EffectProtocol.load(), ReleaseProtocol.load()
    snapshot = "b" * 64
    image_manifest = tmp_path / "manifest.json"
    image_manifest.write_text(
        json.dumps(
            {
                "schema_version": "shaiwei-release-manifest-v1",
                "code_snapshot_sha256": snapshot,
                "file_count": 1,
                "files": {},
            }
        )
    )
    preflight = SyntheticAdapter(protocol, tmp_path).preflight()
    document = build_release_document(
        protocol=protocol,
        release_protocol=release,
        preflight=preflight,
        created_at="2026-08-17T00:00:00+00:00",
        implementation_git_commit="a" * 40,
        origin_main_commit="a" * 40,
        code_snapshot=snapshot,
        image_id="sha256:" + "c" * 64,
        image_platform="linux/arm64",
        image_git_commit="a" * 40,
        image_release_manifest_path=image_manifest,
        bound_input_hashes=protocol.bound_input_contract(),
    )
    assert document["scope"]["authority"] == expected_scope_authority()
    assert document["scope"]["execution"]["strategy_effect_attempt_count"] == 3

    compose = yaml.safe_load((ROOT / "compose.ts-v5-r3g2-effect.yaml").read_text())
    runner, auditor = (
        compose["services"]["ts-v5-r3g2-effect-runner"],
        compose["services"]["ts-v5-r3g2-effect-auditor"],
    )
    assert runner["network_mode"] == auditor["network_mode"] == "none"
    assert runner["command"] == RUNNER_COMMAND
    assert auditor["command"] == AUDITOR_COMMAND
    assert runner["mem_limit"] == "14g"
    assert runner["tmpfs"] == ["/tmp:rw,noexec,nosuid,size=6g,mode=1777"]
    assert "/workspace/data/raw" not in [row["target"] for row in auditor["volumes"]]
    assert "env_file" not in runner and "env_file" not in auditor
    expected_runner, expected_auditor = _mounts()

    def mounts(rows: list[dict]) -> list[dict[str, str]]:
        return [
            {
                "source": str(row["source"]).removeprefix("./"),
                "target": row["target"],
                "access": "read_only" if row.get("read_only") else "read_write",
            }
            for row in rows
        ]

    assert mounts(runner["volumes"]) == expected_runner
    assert mounts(auditor["volumes"]) == expected_auditor
    research_ledgers = {
        "ledger/ts_v5_r3f_llm_attempts.csv",
        "ledger/ts_v5_r3f_llm_transports.csv",
    }
    assert {row["source"] for row in expected_runner} & research_ledgers == research_ledgers
    assert not any(row["source"].rstrip("/") == "ledger" for row in expected_runner)
    assert not any("p1-moneyflow-alpha158" in row["source"] for row in expected_runner)
    assert "compose.ts-v5-r3g2-effect.yaml" in CONTROLLED_FILES
    assert "compose.ts-v5-r3g2-effect.yaml" in (ROOT / "Dockerfile").read_text()


def test_auditor_does_not_import_primary_execution_or_gate_modules() -> None:
    source = (
        ROOT / "src/shaiwei/research/trend_swing/r3g2/effect_audit.py"
    ).read_text(encoding="utf-8")
    assert ".effect_execution" not in source
    assert ".effect_metrics" not in source
    assert ".effect_orders" not in source
    assert ".effect_artifacts" not in source
