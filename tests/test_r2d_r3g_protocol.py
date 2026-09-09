"""R3G frozen natural boundary; no production files or Docker."""
from datetime import datetime
from pathlib import Path

import pytest

from shaiwei import daily_early_release_guard as base
from shaiwei import r2d_authorized_start as authorized
from shaiwei import r2d_release_guard as guard
from shaiwei.r2d_legacy_boundary import validate_noop_boundary
from shaiwei.release_build_context import controller_component_sha256

R3F = Path("config/r2d_scheduler_release_guard_r3f_start_v1.yaml")
R3G = Path("config/r2d_scheduler_release_guard_r3g_start_v1.yaml")


def test_r3g_changes_only_dates_and_forward_hashes():
    old = guard.load_protocol(R3F).model_dump(mode="json")
    new = guard.load_protocol(R3G).model_dump(mode="json")
    old["guard_id"] = "r2d-scheduler-release-guard-20260909"
    old["target_trade_date"] = "20260909"
    old["legacy_noop_boundary"]["detail_trade_date"] = "20260908"
    hashes = {
        "model_baseline": "9ef872c17c4fea2ee277029ea930dad739f0709544f4c82d9f69f047bae30312",
        "model_top20": "0faa96dad0f8352bb30a96ac450541562d6607abbead80332f6b22c5c8ea805d",
    }
    for row in old["expected_latest_forward"]:
        row["execution_trade_date"] = "20260908"
        row["artifact_sha256"] = hashes[row["account_id"]]
    assert new == old
    identity = guard.load_protocol(R3G).controller_identity
    assert set(identity.component_paths) == authorized.REQUIRED_COMPONENTS
    assert controller_component_sha256(Path("."), identity.component_paths) == identity.component_sha256


@pytest.mark.parametrize("timestamp,valid", [
    ("2026-09-09T16:39:59+08:00", False),
    ("2026-09-09T16:40:00+08:00", True),
    ("2026-09-09T18:59:59+08:00", True),
    ("2026-09-09T19:00:00+08:00", False),
    ("2026-09-08T17:00:00+08:00", False),
    ("2026-09-10T17:00:00+08:00", False),
])
def test_r3g_exact_window(timestamp, valid):
    protocol = guard.load_protocol(R3G)
    if valid:
        authorized.check_time(protocol, datetime.fromisoformat(timestamp))
    else:
        with pytest.raises(base.GuardError):
            authorized.check_time(protocol, datetime.fromisoformat(timestamp))


@pytest.mark.parametrize("kind", ["valid", "morning", "prior_day", "detail", "daily", "shadow", "paper"])
def test_r3g_rejects_stale_boundary_or_any_target_attempt(kind):
    protocol = guard.load_protocol(R3G)
    health = {"status": "noop", "detail": "20260908",
              "updated_at": "2026-09-09T08:20:00+00:00"}
    counts = {"daily": 0, "shadow": 0, "paper": 0}
    if kind == "morning":
        health["updated_at"] = "2026-09-09T01:03:50.519203+00:00"
    elif kind == "prior_day":
        health["updated_at"] = "2026-09-08T08:20:00+00:00"
    elif kind == "detail":
        health["detail"] = "20260907"
    elif kind in counts:
        counts[kind] = 1
    kwargs = dict(target_trade_date=protocol.target_trade_date, timezone=protocol.timezone,
                  health=health, counts=counts)
    if kind == "valid":
        assert validate_noop_boundary(protocol.legacy_noop_boundary, **kwargs)
    else:
        with pytest.raises(base.GuardError):
            validate_noop_boundary(protocol.legacy_noop_boundary, **kwargs)


def test_r3g_cannot_repeat_phase_a_or_use_legacy_execute():
    protocol = guard.load_protocol(R3G)
    now = datetime.fromisoformat("2026-09-09T17:00:00+08:00")
    with pytest.raises(base.GuardError, match="cannot repeat Phase A"):
        guard.prepare_guard(protocol, now=now, execute=False)
    with pytest.raises(base.GuardError, match="retired"):
        guard.start_guard(protocol, now=now, execute=True)
