"""R2D-lite O5（ADR 0016 §11）：20261022 交易日窗口启动协议的冻结身份。"""

from pathlib import Path

from shaiwei import r2d_authorized_start as authorized
from shaiwei import r2d_release_guard as guard
from shaiwei.release_build_context import controller_component_sha256

PROTOCOL = Path("config/r2d_scheduler_release_guard_lite_20261022_v1.yaml")


def test_lite_protocol_binds_new_candidate_running_legacy_and_window():
    protocol = guard.load_protocol(PROTOCOL)
    assert protocol.schema_version == "r2d-scheduler-release-guard-r2-v1"
    assert protocol.guard_id == "r2d-scheduler-release-guard-20261022"
    assert protocol.target_trade_date == "20261022"
    assert (str(protocol.start_window.not_before), str(protocol.start_window.expires_at)) == ("16:40:00", "19:00:00")
    assert protocol.candidate.image == "shaiwei:scheduler-8b5b88779e29c5f3"
    assert protocol.candidate.image_id == (
        "sha256:ce1a13519568fca6f1e59ab3b261b9d210b95b15910ed4d65010004442aaa447"
    )
    assert protocol.candidate.git_head == "f6d3b7085e20f9f2666190ee641896ad345a5378"
    assert protocol.expected_running_release.image_id == (
        "sha256:722f63de15932cb2698e82db7c0140f02921f27f126e1c0235ca62e0a1213b76"
    )
    boundary = protocol.legacy_noop_boundary
    assert boundary is not None and boundary.detail_trade_date == "20261021"
    assert {row.execution_trade_date for row in protocol.expected_latest_forward} == {"20261021"}
    assert {row.code_snapshot_sha256 for row in protocol.expected_latest_forward} == {
        protocol.expected_running_release.code_snapshot_sha256
    }
    assert protocol.predecessor_fixture.format == "r3a"
    assert protocol.predecessor_fixture.release_scope_sha256 == (
        "854b75c9425221e6da86cd8bbb11182cc51fafaf16c5ddc37b930e83a55b70a1"
    )


def test_lite_protocol_freezes_the_unchanged_secure_controller():
    identity = guard.load_protocol(PROTOCOL).controller_identity
    assert set(identity.component_paths) == authorized.REQUIRED_COMPONENTS
    assert identity.candidate_base_head == "f6d3b7085e20f9f2666190ee641896ad345a5378"
    assert identity.component_sha256 == "f88f44a791e630c4d57dcd79f9c7a3684b263bf64a935e9f5829ed53a3d3f998"
    assert controller_component_sha256(Path("."), identity.component_paths) == identity.component_sha256
