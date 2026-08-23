from __future__ import annotations

import hashlib
from pathlib import Path

import yaml


ROOT = Path(__file__).parents[1]
REGISTRY = ROOT / "config/effect_attempt_claim_gate_v1.yaml"


def _document() -> dict:
    return yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))


def _discovered(document: dict) -> set[str]:
    filenames = set(document["discovery"]["runner_filenames"])
    markers = tuple(document["discovery"]["effect_start_markers"])
    found: set[str] = set()
    for path in (ROOT / "src/shaiwei/research").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if path.name in filenames and any(marker in text for marker in markers):
            found.add(path.relative_to(ROOT).as_posix())
    return found


def test_effect_runner_inventory_is_self_discovered_complete_and_hash_bound() -> None:
    document = _document()
    legacy = document["legacy_closed_entrypoints"]
    active = document["claim_gate_entrypoints"]
    registered = {row["path"] for row in [*legacy, *active]}

    assert document["schema_version"] == "effect-attempt-claim-gate-registry-v1"
    assert len(legacy) == 8
    assert len(registered) == 10
    assert len(active) == 2
    assert registered == _discovered(document)
    for row in [*legacy, *active]:
        payload = (ROOT / row["path"]).read_bytes()
        assert hashlib.sha256(payload).hexdigest() == row["sha256"]


def test_legacy_entries_remain_closed_and_future_entries_cannot_be_implied() -> None:
    document = _document()
    status = document["legacy_status"]
    gate = document["claim_gate"]

    assert status == {
        "classification": "LEGACY_CLOSED_NO_CANONICAL_CLAIM",
        "original_scopes_closed": True,
        "source_retrofit_authorized": False,
        "same_scope_reuse_authorized": False,
        "historical_ledger_or_result_mutation_authorized": False,
    }
    entries = document["claim_gate_entrypoints"]
    assert {entry["classification"] for entry in entries} == {
        "CLAIM_FIRST_RELEASE_READY_NOT_EXECUTED",
        "CLAIM_FIRST_SUCCESSOR_RELEASE_NOT_EXECUTED",
    }
    for entry in entries:
        assert entry["claim_before_effect_reader"] is True
        assert entry["canonical_ledger_write_authorized_before_exact_approval"] is False
        assert entry["real_effect_read_authorized_before_exact_approval"] is False
        assert entry["same_scope_retry_authorized"] is False
        assert entry["production_authorization"] == "none"
    assert gate["claim_before_effect_reader"] is True
    assert gate["same_scope_retry_authorized"] is False
    assert gate["actual_ledger_write_authorized_in_a1_5a"] is False
    assert gate["real_effect_read_authorized_in_a1_5a"] is False
    assert document["next_migration"][
        "requires_new_protocol_release_scope_and_user_authorization"
    ] is True


def test_claim_gate_module_is_bounded_and_does_not_import_effect_engines() -> None:
    path = ROOT / "src/shaiwei/research/effect_attempt_claim.py"
    text = path.read_text(encoding="utf-8")

    assert len(text.splitlines()) <= 400
    assert "shaiwei.ledger import append_experiment_once" in text
    for forbidden in ("qlib", "lightgbm", "production_conversion", "trend_swing", "pandas"):
        assert forbidden not in text.lower()
