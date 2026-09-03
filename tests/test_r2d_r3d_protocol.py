from pathlib import Path

from shaiwei import r2d_release_guard as guard


PREDECESSOR = Path("config/r2d_scheduler_release_guard_r3b_prepare_v1.yaml")
RECOVERY = Path("config/r2d_scheduler_release_guard_r3d_prepare_v1.yaml")


def test_r3d_prepare_rebinds_only_dates_and_forward_evidence() -> None:
    predecessor = guard.load_protocol(PREDECESSOR)
    recovery = guard.load_protocol(RECOVERY)

    assert recovery.prepare_date == "20260903"
    assert recovery.target_trade_date == "20260904"
    assert {item.execution_trade_date for item in recovery.expected_latest_forward} == {
        "20260903"
    }
    assert recovery.candidate == predecessor.candidate
    assert recovery.expected_running_release == predecessor.expected_running_release
    assert recovery.predecessor_fixture == predecessor.predecessor_fixture
    assert recovery.controller_identity == predecessor.controller_identity
    assert recovery.expected_legacy_mounts_before_prepare == (
        "/workspace/data",
        "/workspace/ledger",
        "/workspace/logs",
    )
