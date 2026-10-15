"""shadow-carry-suspended-v1（ADR 0015）：沿用日停牌目标 manifest 合同 v3 的测试清单 §6 与验收重放 §7。"""

import csv
import json
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from shaiwei.config import PROJECT_ROOT, load, load_paper_top20_protocol
from shaiwei.paper.engine import _target_weights as paper_target_weights
from shaiwei.paper.projection import project_top20_signal
from shaiwei.shadow import generation
from shaiwei.shadow.manifest import (
    CARRY_EXPLANATION,
    DataClockError,
    verify_signal_manifest,
    write_signal_manifest,
)
from shaiwei.shadow.reconciliation import _target_weights as recon_target_weights
from shaiwei.web.query_evidence import _read_signal

TOPK = 30
TARGETS = [f"SH{600000 + rank:06d}" for rank in range(1, TOPK + 1)]
COMPLETE = datetime(2026, 9, 29, 11, 37, tzinfo=timezone.utc)


def _sentinels():
    return [
        {"sentinel": f"S{number}", "status": "NOT_APPLICABLE" if number == 10 else "PASS"}
        for number in range(1, 11)
    ]


def _scores(instruments: list[str]) -> pd.DataFrame:
    return pd.DataFrame(
        {"instrument": instruments, "score": [1.0 - index / 1000 for index in range(len(instruments))]}
    )


def _write(tmp_path: Path, scores: pd.DataFrame, **overrides):
    kwargs = {
        "signal_date": date(2026, 9, 29),
        "topk": TOPK,
        "sentinel_results": _sentinels(),
        "data_complete_at": COMPLETE,
        "generated_at": COMPLETE + timedelta(seconds=11),
        "data_snapshot_sha256": "d" * 64,
        "code_commit": "abc",
        "code_snapshot_sha256": "c" * 64,
        "output_dir": tmp_path,
        "rebalance_days": 10,
        **overrides,
    }
    path, digest = write_signal_manifest(scores, **kwargs)
    return path, digest, json.loads(path.read_text(encoding="utf-8"))


def _carry(tmp_path: Path, missing: list[str], *, explained=None, cap=3):
    present = [instrument for instrument in TARGETS if instrument not in missing]
    return _write(
        tmp_path,
        _scores(present + ["SH688001"]),
        target_instruments=TARGETS,
        rebalance_due=False,
        previous_signal_sha256="p" * 64,
        explained_missing=frozenset(missing) if explained is None else explained,
        max_carried_without_score=cap,
    )


# §6-1 调仓日：v3 字段齐全且无沿用缺口
def test_rebalance_day_is_v3_with_all_live_orders(tmp_path: Path):
    _, _, document = _write(tmp_path, _scores(TARGETS + ["SH688001"]))
    assert document["schema_version"] == 3
    assert document["carried_without_score"] == []
    assert document["carry_explanation"] is None
    assert {order["score_status"] for order in document["orders"]} == {"LIVE"}
    assert [order["instrument"] for order in document["orders"]] == TARGETS
    assert all(isinstance(order["score"], float) for order in document["orders"])


# §6-2 沿用日 1 只无 bar：沿用权重与名次、score=null、签名可验证
def test_one_suspended_carried_target_keeps_weight_rank_and_signs(tmp_path: Path):
    path, digest, document = _carry(tmp_path, ["SH600005"])
    assert verify_signal_manifest(path) == digest
    assert document["carried_without_score"] == ["SH600005"]
    assert document["carry_explanation"] == CARRY_EXPLANATION
    order = document["orders"][4]
    assert order == {
        "rank": 5,
        "instrument": "SH600005",
        "score": None,
        "score_status": "CARRIED_NO_SCORE",
        "target_weight": 1 / TOPK,
    }
    assert sum(order["target_weight"] for order in document["orders"]) == pytest.approx(1.0)
    assert sum(order["score_status"] == "LIVE" for order in document["orders"]) == TOPK - 1


# §6-3 上限：3 只通过，4 只失败
def test_cap_allows_three_and_rejects_four(tmp_path: Path):
    _, _, document = _carry(tmp_path / "three", ["SH600002", "SH600009", "SH600030"])
    assert document["carried_without_score"] == ["SH600002", "SH600009", "SH600030"]
    with pytest.raises(DataClockError, match="exceed cap 3"):
        _carry(tmp_path / "four", ["SH600002", "SH600009", "SH600017", "SH600030"])


# §6-4 有 bar 无评分：保留旧文案失败
def test_unexplained_missing_score_keeps_legacy_failure(tmp_path: Path):
    with pytest.raises(DataClockError, match=r"carried targets missing current scores: \['SH600007'\]"):
        _carry(tmp_path, ["SH600007"], explained=frozenset())


# §6-5 可解释与不可解释并存：不可解释优先失败
def test_unexplained_takes_precedence_over_explained(tmp_path: Path):
    with pytest.raises(DataClockError, match=r"missing current scores: \['SH600008'\]"):
        _carry(tmp_path, ["SH600003", "SH600008"], explained=frozenset({"SH600003"}))


# §6-6 未提供可解释集合或上限为 0：与旧合同相同
def test_default_arguments_reproduce_legacy_contract(tmp_path: Path):
    present = [instrument for instrument in TARGETS if instrument != "SH600005"]
    with pytest.raises(DataClockError, match="missing current scores"):
        _write(tmp_path / "a", _scores(present), target_instruments=TARGETS, rebalance_due=False)
    with pytest.raises(DataClockError, match="exceed cap 0"):
        _carry(tmp_path / "b", ["SH600005"], cap=0)


# §6-7 v2 旧 manifest 仍可校验
def test_legacy_v2_manifest_still_verifies(tmp_path: Path):
    _, _, document = _write(tmp_path / "v3", _scores(TARGETS))
    legacy = {
        key: value
        for key, value in document.items()
        if key not in {"signal_sha256", "carried_without_score", "carry_explanation"}
    }
    legacy["schema_version"] = 2
    legacy["orders"] = [
        {key: value for key, value in order.items() if key != "score_status"} for order in legacy["orders"]
    ]
    import hashlib

    canonical = json.dumps(legacy, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    legacy["signal_sha256"] = hashlib.sha256(canonical).hexdigest()
    path = tmp_path / "legacy.json"
    path.write_text(json.dumps(legacy), encoding="utf-8")
    assert verify_signal_manifest(path) == legacy["signal_sha256"]


# §6-8 generation：可解释集合计算与转发
def test_carried_without_bar_uses_tushare_codes_and_skips_unparseable():
    codes = frozenset({"600001.SH", "000002.SZ"})
    assert generation.carried_without_bar(["SH600001", "SZ000002", "SH600363"], codes) == {"SH600363"}
    assert generation.carried_without_bar(["XX1"], frozenset()) == frozenset()


def _generation_world(monkeypatch, tmp_path: Path, scores: pd.DataFrame):
    sentinel = tmp_path / "sentinel.json"
    sentinel.write_text(json.dumps({"results": _sentinels()}), encoding="utf-8")
    snapshot = SimpleNamespace(
        code_snapshot_sha256="c" * 64,
        data_snapshot_sha256="d" * 64,
        artifact_sha256="q" * 64,
        sentinel_report_path=sentinel,
        provider_uri="unused",
    )
    model = tmp_path / "model.txt"
    model.write_bytes(b"model")
    monkeypatch.setattr(generation, "initialize_qlib", lambda *_a, **_k: None)
    monkeypatch.setattr(generation, "_train_scores", lambda *_a: (scores, {"train": ("a", "b"), "valid": ("c", "d")}, b"m"))
    monkeypatch.setattr(generation, "_persist_model", lambda *_a: model)
    monkeypatch.setattr(generation, "append_experiment", lambda **_k: "exp")
    monkeypatch.setattr(generation, "git_head", lambda: "abc")
    previous, _, _ = _write(tmp_path / "previous", _scores(TARGETS), signal_date=date(2026, 9, 28))
    return snapshot, previous


def test_generation_forwards_explained_missing_on_carry_day(monkeypatch, tmp_path: Path):
    scores = _scores([instrument for instrument in TARGETS if instrument != "SH600012"])
    snapshot, previous = _generation_world(monkeypatch, tmp_path, scores)
    bar_codes = frozenset(f"{instrument[2:]}.SH" for instrument in TARGETS if instrument != "SH600012")
    generated = generation.generate_forward_signal(
        load(),
        signal_date=date(2026, 9, 29),
        snapshot=snapshot,
        data_complete_at=COMPLETE,
        output_root=tmp_path / "out",
        previous_manifest_path=previous,
        rebalance_due=False,
        signal_day_bar_codes=bar_codes,
    )
    document = json.loads(generated.manifest_path.read_text(encoding="utf-8"))
    assert document["carried_without_score"] == ["SH600012"]


def test_generation_without_bar_codes_keeps_legacy_failure(monkeypatch, tmp_path: Path):
    scores = _scores([instrument for instrument in TARGETS if instrument != "SH600012"])
    snapshot, previous = _generation_world(monkeypatch, tmp_path, scores)
    with pytest.raises(DataClockError, match="missing current scores"):
        generation.generate_forward_signal(
            load(),
            signal_date=date(2026, 9, 29),
            snapshot=snapshot,
            data_complete_at=COMPLETE,
            output_root=tmp_path / "out",
            previous_manifest_path=previous,
            rebalance_due=False,
            signal_day_bar_codes=None,
        )


def test_generation_rebalance_day_ignores_bar_codes(monkeypatch, tmp_path: Path):
    snapshot, previous = _generation_world(monkeypatch, tmp_path, _scores(TARGETS))
    generated = generation.generate_forward_signal(
        load(),
        signal_date=date(2026, 9, 29),
        snapshot=snapshot,
        data_complete_at=COMPLETE,
        output_root=tmp_path / "out",
        previous_manifest_path=previous,
        rebalance_due=True,
        signal_day_bar_codes=frozenset(),
    )
    document = json.loads(generated.manifest_path.read_text(encoding="utf-8"))
    assert document["carried_without_score"] == []


# §6-9 shadow_cycle：代码集合读取，失败时返回 None
def test_signal_day_bar_codes_reads_daily_and_degrades_to_none(monkeypatch):
    from shaiwei.pipeline import shadow_cycle

    monkeypatch.setattr(
        shadow_cycle, "_exact_daily", lambda _d: pd.DataFrame({"ts_code": ["600001.SH", "000002.SZ"]})
    )
    assert shadow_cycle._signal_day_bar_codes("20260929") == {"600001.SH", "000002.SZ"}

    def broken(_d):
        raise RuntimeError("content hash mismatch")

    monkeypatch.setattr(shadow_cycle, "_exact_daily", broken)
    assert shadow_cycle._signal_day_bar_codes("20260929") is None


# §6-10 下游回归：只读 instrument/rank/weight 的消费者对 null 分数无感
def test_downstream_consumers_tolerate_null_score(tmp_path: Path):
    path, digest, document = _carry(tmp_path, ["SH600005"])
    projected = project_top20_signal(
        {**document, "signal_sha256": digest},
        source_signal_sha256=digest,
        policy=load_paper_top20_protocol().paper_portfolio,
    )
    top20 = projected.signal["orders"]
    assert len(top20) == 20
    assert top20[4]["score"] is None and top20[4]["score_status"] == "CARRIED_NO_SCORE"
    assert len(paper_target_weights(document)[0]) == TOPK
    assert len(recon_target_weights(document)) == TOPK

    class Cut:
        def artifact(self, relative, *, prefix):
            assert relative.startswith(prefix)
            return path.read_bytes()

    row = {
        "signal_manifest_path": f"data/shadow/signals/{path.name}",
        "signal_sha256": digest,
        "signal_trade_date": "20260929",
        "code_snapshot_sha256": "c" * 64,
        "data_snapshot_sha256": "d" * 64,
    }
    assert _read_signal(Cut(), row)["carried_without_score"] == ["SH600005"]


# §7 一次性只读验收重放（默认跳过）：20260928 目标 + 20260929 真实行情，合成分数，不运行模型
@pytest.mark.skipif(
    os.getenv("SHAIWEI_ACCEPTANCE_REPLAY") != "1", reason="one-time read-only acceptance replay"
)
def test_acceptance_replay_20260929_explains_only_600363(tmp_path: Path):
    from shaiwei.pipeline import shadow_cycle

    with (PROJECT_ROOT / "ledger" / "shadow_runs.csv").open(newline="", encoding="utf-8") as handle:
        passed = [r for r in csv.DictReader(handle) if r["signal_trade_date"] == "20260928" and r["status"] == "PASS"]
    assert len(passed) == 1
    previous = json.loads((PROJECT_ROOT / passed[0]["signal_manifest_path"]).read_text(encoding="utf-8"))
    targets = [str(order["instrument"]) for order in previous["orders"]]
    bar_codes = shadow_cycle._signal_day_bar_codes("20260929")
    assert bar_codes is not None
    traded = sorted(f"{code[-2:]}{code[:6]}" for code in bar_codes if code[-2:] in {"SH", "SZ"})
    explained = generation.carried_without_bar(targets, bar_codes)
    _, _, document = _write(
        tmp_path,
        _scores(traded),
        target_instruments=targets,
        rebalance_due=False,
        previous_signal_sha256=previous["signal_sha256"],
        explained_missing=explained,
        max_carried_without_score=load().shadow_pipeline.max_carried_without_score,
    )
    assert document["schema_version"] == 3
    assert document["carried_without_score"] == ["SH600363"]
    assert sum(order["score_status"] == "LIVE" for order in document["orders"]) == TOPK - 1
