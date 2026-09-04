from datetime import datetime
from pathlib import Path

import pytest

from shaiwei import daily_early_release_guard as base
from shaiwei import r2d_release_guard as guard


PREDECESSOR = Path("config/r2d_scheduler_release_guard_r3b_prepare_v1.yaml")
RECOVERY = Path("config/r2d_scheduler_release_guard_r3d_prepare_v1.yaml")
START_RECOVERY = Path("config/r2d_scheduler_release_guard_r3e_start_v1.yaml")


def test_r3d_prepare_rebinds_only_dates_and_forward_evidence() -> None:
    predecessor = guard.load_protocol(PREDECESSOR)
    recovery = guard.load_protocol(RECOVERY)

    assert recovery.prepare_date == "20260903"
    assert recovery.target_trade_date == "20260904"
    assert {item.execution_trade_date for item in recovery.expected_latest_forward} == {"20260903"}
    assert recovery.candidate == predecessor.candidate
    assert recovery.expected_running_release == predecessor.expected_running_release
    assert recovery.predecessor_fixture == predecessor.predecessor_fixture
    assert (
        recovery.controller_identity.candidate_base_head
        == predecessor.controller_identity.candidate_base_head
    )
    assert recovery.controller_identity.component_paths == predecessor.controller_identity.component_paths
    assert recovery.controller_identity.controller_source_head == "cffa10027320c4cbe710a3737f35b1d3e5e01962"
    assert (
        recovery.controller_identity.component_sha256
        == "3605916b90f6a21d9746e9200cd04b94ba2c020a1b69d3ac9c7f596c2a5c8aad"
    )
    assert set(recovery.expected_legacy_mounts_before_prepare) == {
        "/run/shaiwei-locks",
        "/workspace/data",
        "/workspace/ledger",
        "/workspace/logs",
    }


def test_r3e_start_recovery_is_start_only_and_rebinds_natural_boundary() -> None:
    prepared = guard.load_protocol(RECOVERY)
    recovery = guard.load_protocol(START_RECOVERY)

    assert recovery.schema_version == "r2d-scheduler-release-guard-r2-v1"
    assert recovery.target_trade_date == "20260907"
    assert recovery.start_window.not_before.isoformat() == "16:40:00"
    assert recovery.start_window.expires_at.isoformat() == "19:00:00"
    assert {item.execution_trade_date for item in recovery.expected_latest_forward} == {
        "20260904"
    }
    assert recovery.candidate == prepared.candidate
    assert recovery.expected_running_release == prepared.expected_running_release
    assert recovery.predecessor_fixture == prepared.predecessor_fixture
    assert recovery.controller_identity == prepared.controller_identity
    assert recovery.expected_legacy_mounts_before_prepare == (
        "/workspace/data",
        "/workspace/ledger",
        "/workspace/logs",
        "/run/shaiwei-locks",
    )
    assert recovery.legacy_noop_boundary is not None
    assert recovery.legacy_noop_boundary.detail_trade_date == "20260904"
    assert recovery.legacy_noop_boundary.require_target_daily_rows == 0
    assert recovery.legacy_noop_boundary.require_target_shadow_rows == 0
    assert recovery.legacy_noop_boundary.require_target_paper_rows == 0
    with pytest.raises(base.GuardError, match="cannot repeat Phase A"):
        guard.prepare_guard(
            recovery,
            now=datetime.fromisoformat("2026-09-03T21:00:00+08:00"),
            execute=False,
        )
