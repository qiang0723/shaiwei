import json
from datetime import date
from pathlib import Path

import pytest

from shaiwei.pipeline.stage0 import _completed_steps, _selected, steps


def test_stage0_pipeline_has_fail_closed_order_and_no_stage1():
    names = [step.name for step in steps(date(2026, 7, 15))]
    assert names == [
        "quality", "runtime", "bootstrap", "namechange", "market", "financial", "crosscheck",
        "sentinel", "qlib", "baseline", "shadow", "alphagen", "audit",
    ]
    assert not any("stage1" in " ".join(step.argv).lower() for step in steps(date(2026, 7, 15)))


def test_pipeline_resume_is_bound_to_asof_and_code_hash(tmp_path: Path):
    log = tmp_path / "run.jsonl"
    events = [
        {"step": "quality", "status": "PASS", "as_of": "2026-07-15", "code_snapshot_sha256": "a"},
        {"step": "runtime", "status": "FAIL", "as_of": "2026-07-15", "code_snapshot_sha256": "a"},
        {"step": "market", "status": "PASS", "as_of": "2026-07-15", "code_snapshot_sha256": "b"},
    ]
    log.write_text("".join(json.dumps(event) + "\n" for event in events), encoding="utf-8")
    assert _completed_steps(log, code_hash="a", as_of=date(2026, 7, 15)) == {"quality"}


def test_pipeline_rejects_reversed_slice():
    all_steps = steps(date(2026, 7, 15))
    with pytest.raises(ValueError, match="must not be after"):
        _selected(all_steps, "baseline", "market")
