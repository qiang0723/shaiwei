from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pandas as pd
import pytest

from shaiwei.research.trend_swing.r3g2.contract import EffectProtocol, R3G2Error
from shaiwei.research.trend_swing.r3g2.w7_audit import audit_pair, audit_pass
from shaiwei.research.trend_swing.r3g2.w7_lineage import W7Output, save_pass


def _output(*, code: str = "000001.SZ", last_score: float = 0.4) -> W7Output:
    index = pd.MultiIndex.from_tuples(
        [
            (pd.Timestamp("2025-01-02"), code),
            (pd.Timestamp("2025-01-03"), code),
        ],
        names=["datetime", "instrument"],
    )
    return W7Output(
        predictions=pd.Series([0.2, last_score], index=index, name="score"),
        model_bytes=b"synthetic-clean-lgbm\n",
    )


def test_protocol_projects_the_exact_w7_window() -> None:
    protocol = EffectProtocol.load()

    assert protocol.sha256 == (
        "c3aa5a2bef199d8745b6e0399085dcf5a60d9f28f29a5426ea0104831f3572bf"
    )
    assert protocol.w7_window() == {
        "name": "W7",
        "train": ["2022-01-01", "2024-06-30"],
        "purged_train_last_signal": "2024-06-13",
        "valid": ["2024-07-01", "2024-12-31"],
        "purged_valid_last_signal": "2024-12-16",
        "test": ["2025-01-01", "2025-12-31"],
        "score_last_signal": "2025-12-16",
    }
    assert len(protocol.selected_point_hashes) == 3


def test_w7_pass_is_write_once_and_independently_replayable(tmp_path: Path) -> None:
    protocol = EffectProtocol.load()
    first = save_pass(tmp_path / "first", _output(), protocol)
    replay = save_pass(tmp_path / "replay", _output(), protocol)

    assert first["all_reused"] is False
    assert replay["all_reused"] is False
    assert first["bundle_sha256"] == replay["bundle_sha256"]
    audit = audit_pair(tmp_path / "first", tmp_path / "replay", protocol)
    assert audit["deterministic_replay"] is True
    assert audit["label_rankic_return_or_effect_read"] is False
    assert audit["verdict"] == "GO_W7_LINEAGE_ENGINEERING_FIXTURE_ONLY"

    reused = save_pass(tmp_path / "first", _output(), protocol)
    assert reused["all_reused"] is True


def test_w7_write_once_conflict_and_replay_drift_fail_closed(tmp_path: Path) -> None:
    protocol = EffectProtocol.load()
    first_output = _output()
    save_pass(tmp_path / "first", first_output, protocol)
    with pytest.raises(R3G2Error, match="write-once conflict"):
        save_pass(tmp_path / "first", replace(first_output, model_bytes=b"changed"), protocol)

    save_pass(tmp_path / "replay", _output(last_score=0.5), protocol)
    with pytest.raises(R3G2Error, match="first pass and replay differ"):
        audit_pair(tmp_path / "first", tmp_path / "replay", protocol)


@pytest.mark.parametrize("code, score", [("430001.BJ", 0.2), ("000001.SZ", float("nan"))])
def test_w7_forbids_bse_and_nonfinite_scores(
    tmp_path: Path, code: str, score: float
) -> None:
    with pytest.raises(R3G2Error, match="quality gate"):
        save_pass(tmp_path / "pass", _output(code=code, last_score=score), EffectProtocol.load())


def test_independent_audit_rejects_untracked_artifact(tmp_path: Path) -> None:
    protocol = EffectProtocol.load()
    save_pass(tmp_path / "pass", _output(), protocol)
    (tmp_path / "pass" / "labels.parquet").write_bytes(b"forbidden")

    with pytest.raises(R3G2Error, match="file set differs"):
        audit_pass(tmp_path / "pass", protocol)
