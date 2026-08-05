from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).parents[1]
SCOPE_PATH = (
    ROOT / "config/m5_dynamic_fundamental_cross_pool_protocol_scope_v1.json"
)


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def test_protocol_scope_is_canonical_and_all_frozen_files_match() -> None:
    envelope = json.loads(SCOPE_PATH.read_text(encoding="utf-8"))
    scope = envelope["scope"]

    assert envelope["protocol_scope_sha256"] == _canonical_sha256(scope)
    for frozen in scope["frozen_files"]:
        path = Path(frozen["path"])
        assert not path.is_absolute()
        assert ".." not in path.parts
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == frozen[
            "sha256"
        ]


def test_protocol_scope_is_pushed_protocol_only_and_execution_closed() -> None:
    scope = json.loads(SCOPE_PATH.read_text(encoding="utf-8"))["scope"]
    git_freeze = scope["git_freeze"]
    permitted = scope["permitted_next_construction"]
    authority = scope["authority"]

    assert git_freeze["protocol_commit"] == git_freeze["local_origin_main_at_scope_creation"]
    assert git_freeze["protocol_commit_pushed_before_scope_creation"]
    assert permitted == {
        "data_gate_implementation_and_release_only": True,
        "real_data_gate_execution": False,
        "synthetic_engineering_gate_execution": False,
    }
    assert authority["data_gate_release_scope_created"] is False
    assert authority["data_gate_approval_recorded"] is False
    assert authority["engineering_gate_release_scope_created"] is False
    assert authority["engineering_gate_approval_recorded"] is False
    assert authority["real_data_read_authorized"] is False
    assert authority["label_read_authorized"] is False
    assert authority["sealed_effect_read_authorized"] is False
    assert authority["model_training_authorized"] is False
    assert authority["backtest_authorized"] is False
    assert authority["production_authorization"] == "none"
    assert authority["scheduler_mutation_authorized"] is False
    assert authority["web_change_authorized"] is False
