from datetime import datetime
from pathlib import Path

import pytest

from shaiwei import daily_early_release_guard as base
from shaiwei import r2d_authorized_start as authorized
from shaiwei import r2d_release_guard as guard
from shaiwei.release_build_context import controller_component_sha256


PREDECESSOR = Path("config/r2d_scheduler_release_guard_r3e_start_v1.yaml")
RECOVERY = Path("config/r2d_scheduler_release_guard_r3f_start_v1.yaml")


def test_r3f_rebinds_only_the_next_natural_start_boundary() -> None:
    predecessor = guard.load_protocol(PREDECESSOR)
    recovery = guard.load_protocol(RECOVERY)

    assert recovery.schema_version == "r2d-scheduler-release-guard-r2-v1"
    assert recovery.prepare_date == predecessor.prepare_date == "20260903"
    assert recovery.target_trade_date == "20260908"
    assert recovery.start_window.not_before.isoformat() == "16:40:00"
    assert recovery.start_window.expires_at.isoformat() == "19:00:00"
    assert recovery.candidate == predecessor.candidate
    assert recovery.expected_running_release == predecessor.expected_running_release
    assert recovery.predecessor_fixture == predecessor.predecessor_fixture
    assert recovery.expected_legacy_mounts_before_prepare == (
        "/workspace/data",
        "/workspace/ledger",
        "/workspace/logs",
        "/run/shaiwei-locks",
    )


def test_r3f_binds_20260907_forwards_and_zero_write_noop_gate() -> None:
    recovery = guard.load_protocol(RECOVERY)

    expected = {item.account_id: item for item in recovery.expected_latest_forward}
    assert set(expected) == {"model_baseline", "model_top20"}
    assert {item.execution_trade_date for item in expected.values()} == {"20260907"}
    assert {item.code_snapshot_sha256 for item in expected.values()} == {
        "4e5244b6b02739dd209a9b01ea715c43ed9a874a7014156e20cf364f06a82708"
    }
    assert expected["model_baseline"].artifact_sha256 == (
        "29931c72063f171476a68da70f49d6f306f9844969713074a27b0ed12a042618"
    )
    assert expected["model_top20"].artifact_sha256 == (
        "aeb7bc1790c0f7118c6db5d292d3cfae80f0be032a45502c672e6b656b982174"
    )
    boundary = recovery.legacy_noop_boundary
    assert boundary is not None
    assert boundary.detail_trade_date == "20260907"
    assert boundary.updated_on_target_date_not_before.isoformat() == "16:00:00"
    assert (
        boundary.require_target_daily_rows,
        boundary.require_target_shadow_rows,
        boundary.require_target_paper_rows,
    ) == (0, 0, 0)
    with pytest.raises(base.GuardError, match="cannot repeat Phase A"):
        guard.prepare_guard(
            recovery,
            now=datetime.fromisoformat("2026-09-03T21:00:00+08:00"),
            execute=False,
        )


def test_r3f_freezes_the_secure_controller_inventory() -> None:
    recovery = guard.load_protocol(RECOVERY)
    identity = recovery.controller_identity

    assert set(identity.component_paths) == authorized.REQUIRED_COMPONENTS
    assert len(identity.component_paths) == 13
    assert identity.controller_source_head == "69f0d913ebd60126ebe8d2f190053329858a45d6"
    assert identity.component_sha256 == controller_component_sha256(
        Path("."), identity.component_paths
    )
