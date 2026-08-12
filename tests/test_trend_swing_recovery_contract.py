from copy import deepcopy

import pytest

from shaiwei.research.trend_swing.contract import TrendSwingError
from shaiwei.research.trend_swing.recovery_contract import (
    APPROVAL_SCOPE_ENV,
    CHINEXT_REQUEST,
    EXPECTED_R3_REQUESTS,
    RecoveryAddendum,
    RecoveryProtocol,
    RecoveryRelease,
    RecoveryR2,
    RecoveryR2Addendum,
    _validate_protocol,
    release_scope_payload,
)
from shaiwei.research.trend_swing.recovery_r3_contract import RecoveryR3


def test_recovery_protocol_is_result_blind_and_registers_missing_sources():
    protocol = RecoveryProtocol.load()
    addendum = RecoveryAddendum.load(protocol)
    assert protocol.document["authorization"]["network_execution_authorized"] is False
    assert protocol.document["authorization"]["read_post_entry_return"] is False
    assert set(protocol.required_sources) >= {
        "tushare.stock_basic",
        "baostock.history_k_data_plus",
    }
    assert protocol.document["network_recovery"]["request"] == CHINEXT_REQUEST
    assert addendum.document["authority"]["change_thresholds"] is False


def test_recovery_protocol_rejects_network_self_authorization():
    document = deepcopy(RecoveryProtocol.load().document)
    document["authorization"]["network_execution_authorized"] = True
    with pytest.raises(TrendSwingError, match="authority"):
        _validate_protocol(document)


def test_release_scope_binds_three_exact_requests_and_approval(monkeypatch, tmp_path):
    protocol = RecoveryProtocol.load()
    addendum = RecoveryAddendum.load(protocol)
    recovery_r2 = RecoveryR2.load(protocol, addendum)
    recovery_r2_addendum = RecoveryR2Addendum.load(recovery_r2)
    recovery_r3 = RecoveryR3.load(recovery_r2, recovery_r2_addendum)
    document = release_scope_payload(
        protocol,
        addendum,
        recovery_r2,
        recovery_r2_addendum,
        recovery_r3,
        implementation_snapshot_sha256="a" * 64,
        implementation_git_head="b" * 40,
        ingest_ledger_sha256="c" * 64,
    )
    path = tmp_path / "release.yaml"
    import yaml

    path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    release = RecoveryRelease.load(
        protocol, addendum, recovery_r2, recovery_r2_addendum, recovery_r3,
        path, project_root=tmp_path,
    )
    assert tuple(release.document["scope"]["requests"]) == EXPECTED_R3_REQUESTS
    with pytest.raises(TrendSwingError, match="approval"):
        release.require_user_approval()
    monkeypatch.setenv(APPROVAL_SCOPE_ENV, release.scope_sha256)
    release.require_user_approval()
