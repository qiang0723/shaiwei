import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest

from shaiwei.shadow.manifest import (
    DataClockError,
    reconcile_next_open,
    verify_signal_manifest,
    write_signal_manifest,
)


def _sentinels():
    return [
        {"sentinel": f"S{number}", "status": "NOT_APPLICABLE" if number == 10 else "PASS"}
        for number in range(1, 11)
    ]


def test_shadow_manifest_is_ranked_hashed_and_never_overwritten(tmp_path: Path):
    complete = datetime(2026, 7, 15, 8, tzinfo=timezone.utc)
    scores = pd.DataFrame({"instrument": ["B", "A", "C"], "score": [0.2, 0.3, 0.1]})
    kwargs = {
        "signal_date": date(2026, 7, 15),
        "topk": 2,
        "sentinel_results": _sentinels(),
        "data_complete_at": complete,
        "generated_at": complete + timedelta(minutes=1),
        "data_snapshot_sha256": "d" * 64,
        "code_commit": "abc",
        "code_snapshot_sha256": "c" * 64,
        "output_dir": tmp_path,
    }
    path, digest = write_signal_manifest(scores, **kwargs)
    document = json.loads(path.read_text())
    assert [order["instrument"] for order in document["orders"]] == ["A", "B"]
    assert verify_signal_manifest(path) == digest
    with pytest.raises(FileExistsError):
        write_signal_manifest(scores, **kwargs)


def test_shadow_manifest_blocks_failed_sentinel(tmp_path: Path):
    sentinels = _sentinels()
    sentinels[0]["status"] = "FAIL"
    now = datetime.now(timezone.utc)
    with pytest.raises(DataClockError, match="S1"):
        write_signal_manifest(
            pd.DataFrame({"instrument": ["A"], "score": [1.0]}),
            signal_date=date.today(), topk=1, sentinel_results=sentinels,
            data_complete_at=now, generated_at=now, data_snapshot_sha256="d" * 64,
            code_commit="abc", code_snapshot_sha256="c" * 64, output_dir=tmp_path,
        )


def test_shadow_next_open_reconciliation(tmp_path: Path):
    now = datetime.now(timezone.utc)
    path, _ = write_signal_manifest(
        pd.DataFrame({"instrument": ["A"], "score": [1.0]}),
        signal_date=date.today(), topk=1, sentinel_results=_sentinels(), data_complete_at=now,
        generated_at=now, data_snapshot_sha256="d" * 64, code_commit="abc",
        code_snapshot_sha256="c" * 64, output_dir=tmp_path,
    )
    execution = pd.DataFrame(
        [{"instrument": "A", "executable": True, "actual_open": 10.1, "reference_open": 10.0}]
    )
    result = reconcile_next_open(path, execution)
    assert result.loc[0, "reconcile_status"] == "OK"
    assert result.loc[0, "open_deviation"] == pytest.approx(0.01)
