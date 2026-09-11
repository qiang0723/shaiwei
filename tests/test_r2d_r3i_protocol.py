"""R3I frozen natural boundary; no production files or Docker."""
from datetime import datetime
import hashlib
from pathlib import Path

import pytest

from shaiwei import daily_early_release_guard as base
from shaiwei import r2d_authorized_start as authorized
from shaiwei import r2d_release_guard as guard
from shaiwei.r2d_legacy_boundary import validate_noop_boundary
from shaiwei.release_build_context import controller_component_sha256

R3H = Path("config/r2d_scheduler_release_guard_r3h_start_v1.yaml")
R3I = Path("config/r2d_scheduler_release_guard_r3i_start_v1.yaml")


def test_r3i_changes_only_dates_and_forward_hashes():
    old = guard.load_protocol(R3H).model_dump(mode="json")
    new = guard.load_protocol(R3I).model_dump(mode="json")
    old["guard_id"] = "r2d-scheduler-release-guard-20260911"
    old["target_trade_date"] = "20260911"
    old["legacy_noop_boundary"]["detail_trade_date"] = "20260910"
    hashes = {
        "model_baseline": "5be99ab10a196ef0a1a555ce3b76dc3b74a7fcba932180291fd77a6d631fa503",
        "model_top20": "81995ebe9e371495cc3cad8267c2b168e9af8c0de5ffd2a447a94ce3a9b3db7b",
    }
    for row in old["expected_latest_forward"]:
        row["execution_trade_date"] = "20260910"
        row["artifact_sha256"] = hashes[row["account_id"]]
    assert new == old
    identity = guard.load_protocol(R3I).controller_identity
    assert set(identity.component_paths) == authorized.REQUIRED_COMPONENTS
    assert controller_component_sha256(Path("."), identity.component_paths) == identity.component_sha256


@pytest.mark.parametrize("timestamp,valid", [
    ("2026-09-11T16:39:59+08:00", False),
    ("2026-09-11T16:40:00+08:00", True),
    ("2026-09-11T18:59:59+08:00", True),
    ("2026-09-11T19:00:00+08:00", False),
    ("2026-09-10T17:00:00+08:00", False),
    ("2026-09-12T17:00:00+08:00", False),
])
def test_r3i_exact_window(timestamp, valid):
    protocol = guard.load_protocol(R3I)
    if valid:
        authorized.check_time(protocol, datetime.fromisoformat(timestamp))
    else:
        with pytest.raises(base.GuardError):
            authorized.check_time(protocol, datetime.fromisoformat(timestamp))


@pytest.mark.parametrize("kind", ["valid", "morning", "prior_day", "detail", "daily", "shadow", "paper"])
def test_r3i_rejects_stale_boundary_or_any_target_attempt(kind):
    protocol = guard.load_protocol(R3I)
    health = {"status": "noop", "detail": "20260910",
              "updated_at": "2026-09-11T08:20:00+00:00"}
    counts = {"daily": 0, "shadow": 0, "paper": 0}
    if kind == "morning":
        health["updated_at"] = "2026-09-11T01:03:50.519203+00:00"
    elif kind == "prior_day":
        health["updated_at"] = "2026-09-10T08:20:00+00:00"
    elif kind == "detail":
        health["detail"] = "20260909"
    elif kind in counts:
        counts[kind] = 1
    kwargs = dict(target_trade_date=protocol.target_trade_date, timezone=protocol.timezone,
                  health=health, counts=counts)
    if kind == "valid":
        assert validate_noop_boundary(protocol.legacy_noop_boundary, **kwargs)
    else:
        with pytest.raises(base.GuardError):
            validate_noop_boundary(protocol.legacy_noop_boundary, **kwargs)


def test_r3i_cannot_repeat_phase_a_or_use_legacy_execute():
    protocol = guard.load_protocol(R3I)
    now = datetime.fromisoformat("2026-09-11T17:00:00+08:00")
    with pytest.raises(base.GuardError, match="cannot repeat Phase A"):
        guard.prepare_guard(protocol, now=now, execute=False)
    with pytest.raises(base.GuardError, match="retired"):
        guard.start_guard(protocol, now=now, execute=True)


def test_r3i_frozen_bytes_and_document_binding():
    expected = "9b91890a56f559570333d41c85e68b2653a714c7221ace0880e221ac1f7f5060"
    assert hashlib.sha256(R3I.read_bytes()).hexdigest() == expected
    assert expected in Path("docs/R2D_R3I_START_ONLY_PROTOCOL_20260911.md").read_text()
    assert hashlib.sha256(R3H.read_bytes()).hexdigest() == (
        "8e348eb851654aec9653164827f71ec80a2fe3f3d4421e95e344f72d27e330f6"
    )
