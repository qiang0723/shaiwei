"""R3J frozen natural boundary; no production files or Docker."""
from datetime import datetime
import hashlib
from pathlib import Path

import pytest

from shaiwei import daily_early_release_guard as base
from shaiwei import r2d_authorized_start as authorized
from shaiwei import r2d_release_guard as guard
from shaiwei.r2d_legacy_boundary import validate_noop_boundary
from shaiwei.release_build_context import controller_component_sha256

R3I = Path("config/r2d_scheduler_release_guard_r3i_start_v1.yaml")
R3J = Path("config/r2d_scheduler_release_guard_r3j_start_v1.yaml")


def test_r3j_changes_only_dates_and_forward_hashes():
    old = guard.load_protocol(R3I).model_dump(mode="json")
    new = guard.load_protocol(R3J).model_dump(mode="json")
    old["guard_id"] = "r2d-scheduler-release-guard-20260915"
    old["target_trade_date"] = "20260915"
    old["legacy_noop_boundary"]["detail_trade_date"] = "20260914"
    hashes = {
        "model_baseline": "9566327f116b84f15fee27353e9424fe48656333fef0ad397aea10796a654e7e",
        "model_top20": "ee0a56d6c425920703f423d82630bf9975dd6e27a5c14936d11e41374b255fb1",
    }
    for row in old["expected_latest_forward"]:
        row["execution_trade_date"] = "20260914"
        row["artifact_sha256"] = hashes[row["account_id"]]
    assert new == old
    identity = guard.load_protocol(R3J).controller_identity
    assert set(identity.component_paths) == authorized.REQUIRED_COMPONENTS
    assert controller_component_sha256(Path("."), identity.component_paths) == identity.component_sha256


@pytest.mark.parametrize("timestamp,valid", [
    ("2026-09-15T16:39:59+08:00", False),
    ("2026-09-15T16:40:00+08:00", True),
    ("2026-09-15T18:59:59+08:00", True),
    ("2026-09-15T19:00:00+08:00", False),
    ("2026-09-14T17:00:00+08:00", False),
    ("2026-09-16T17:00:00+08:00", False),
])
def test_r3j_exact_window(timestamp, valid):
    protocol = guard.load_protocol(R3J)
    if valid:
        authorized.check_time(protocol, datetime.fromisoformat(timestamp))
    else:
        with pytest.raises(base.GuardError):
            authorized.check_time(protocol, datetime.fromisoformat(timestamp))


@pytest.mark.parametrize("kind", ["valid", "morning", "prior_day", "detail", "daily", "shadow", "paper"])
def test_r3j_rejects_stale_boundary_or_any_target_attempt(kind):
    protocol = guard.load_protocol(R3J)
    health = {"status": "noop", "detail": "20260914",
              "updated_at": "2026-09-15T08:20:00+00:00"}
    counts = {"daily": 0, "shadow": 0, "paper": 0}
    if kind == "morning":
        health["updated_at"] = "2026-09-15T01:03:50.519203+00:00"
    elif kind == "prior_day":
        health["updated_at"] = "2026-09-14T08:20:00+00:00"
    elif kind == "detail":
        health["detail"] = "20260911"
    elif kind in counts:
        counts[kind] = 1
    kwargs = dict(target_trade_date=protocol.target_trade_date, timezone=protocol.timezone,
                  health=health, counts=counts)
    if kind == "valid":
        assert validate_noop_boundary(protocol.legacy_noop_boundary, **kwargs)
    else:
        with pytest.raises(base.GuardError):
            validate_noop_boundary(protocol.legacy_noop_boundary, **kwargs)


def test_r3j_cannot_repeat_phase_a_or_use_legacy_execute():
    protocol = guard.load_protocol(R3J)
    now = datetime.fromisoformat("2026-09-15T17:00:00+08:00")
    with pytest.raises(base.GuardError, match="cannot repeat Phase A"):
        guard.prepare_guard(protocol, now=now, execute=False)
    with pytest.raises(base.GuardError, match="retired"):
        guard.start_guard(protocol, now=now, execute=True)


def test_r3j_frozen_bytes_and_document_binding():
    expected = "5372a6ff4549cade08d2371dd0560d1b63e40e91e8c9ebf108a93f524e6389c1"
    assert hashlib.sha256(R3J.read_bytes()).hexdigest() == expected
    assert expected in Path("docs/R2D_R3J_START_ONLY_PROTOCOL_20260915.md").read_text()
    assert hashlib.sha256(R3I.read_bytes()).hexdigest() == (
        "9b91890a56f559570333d41c85e68b2653a714c7221ace0880e221ac1f7f5060"
    )
