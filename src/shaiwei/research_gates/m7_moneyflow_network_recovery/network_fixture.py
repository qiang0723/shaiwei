"""Offline fixture for M7 exact network-release engineering and isolation."""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path
from typing import Any

import pandas as pd

from shaiwei.research_gates.m7_moneyflow.contract import canonical_json

from shaiwei.research_gates.m7_moneyflow_recovery.contract import (
    RecoveryError,
    RecoveryProtocol,
)
from shaiwei.research_gates.m7_moneyflow_recovery.planning import (
    MoneyflowRequest,
    StatusRequest,
)

from .network_collect import collect_moneyflow_plan, collect_status_plan
from .network_contract import NetworkReleaseProtocol
from .network_release import NetworkRecoveryRelease, build_release_document
from .request_plan import RequestPlanData
from .sealing import write_canonical_once


class _StatusResult:
    error_code = "0"
    error_msg = ""
    fields = ["date", "code", "tradestatus"]

    def __init__(self) -> None:
        self._rows = iter([["2021-01-04", "sh.688001", "0"]])
        self._current: list[str] | None = None

    def next(self) -> bool:
        self._current = next(self._rows, None)
        return self._current is not None

    def get_row_data(self) -> list[str]:
        if self._current is None:
            raise RecoveryError("synthetic status cursor is empty")
        return self._current


class _StatusClient:
    def __init__(self) -> None:
        self.calls = 0

    def query_history_k_data_plus(self, **kwargs: str) -> _StatusResult:
        self.calls += 1
        return _StatusResult()


class _MoneyflowClient:
    def __init__(self, frame: pd.DataFrame) -> None:
        self.frame = frame
        self.calls = 0

    def query(self, api_name: str, **kwargs: object) -> pd.DataFrame:
        self.calls += 1
        return self.frame.copy()


def _plan() -> RequestPlanData:
    status = StatusRequest("688001.SH", "20210104", "20210104", ("20210104",))
    full = MoneyflowRequest("full_market_by_trade_date", {"trade_date": "20210104"})
    targeted = MoneyflowRequest(
        "one_security_one_date",
        {"ts_code": "688002.SH", "start_date": "20210104", "end_date": "20210104"},
    )
    return RequestPlanData((status,), (full,), (targeted,), ("20210104",))


def _moneyflow_row(protocol: RecoveryProtocol) -> pd.DataFrame:
    row: dict[str, Any] = {"ts_code": "688002.SH", "trade_date": "20210104"}
    row.update({field: float(index) for index, field in enumerate(protocol.moneyflow_fields[2:])})
    return pd.DataFrame([row], columns=protocol.moneyflow_fields)


def _release_manifest() -> dict[str, Any]:
    return {
        "plan_id": "1" * 64,
        "plan_root_relative_path": "data/control/m7-recovery/request-plans/" + "1" * 64,
        "target_identity": {
            "track_a": {"physical_sha256": "2" * 64, "logical_sha256": "3" * 64},
            "track_b": {"physical_sha256": "4" * 64, "logical_sha256": "5" * 64},
        },
        "request_summary": {
            "status": {
                "request_count": 527,
                "required_key_count": 527,
                "request_identity_bundle_sha256": "6" * 64,
            },
            "full_market": {
                "request_count": 1,
                "request_identity_bundle_sha256": "7" * 64,
            },
            "targeted": {
                "request_count": 541,
                "request_identity_bundle_sha256": "8" * 64,
            },
        },
    }


def verify_network_fixture(project_root: Path) -> dict[str, Any]:
    network = NetworkReleaseProtocol.load(
        project_root / "config/m7_moneyflow_evidence_recovery_network_release_v1.yaml",
        project_root=project_root,
    )
    recovery = RecoveryProtocol.load(
        project_root / "config/m7_moneyflow_evidence_recovery_v1.yaml",
        engineering_path=project_root / "config/m7_moneyflow_evidence_recovery_engineering_v1.yaml",
        project_root=project_root,
    )
    release_document = build_release_document(
        network,
        _release_manifest(),
        plan_manifest_sha256="9" * 64,
        created_at="2026-08-09T16:00:00+08:00",
        git_commit="a" * 40,
        code_bundle_sha256="b" * 64,
        image_id="sha256:" + "c" * 64,
        platform="linux/arm64",
    )
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        release_path = root / "release.json"
        write_canonical_once(release_path, release_document)
        release = NetworkRecoveryRelease.load(
            release_path,
            network,
            plan_manifest=_release_manifest(),
            plan_manifest_sha256="9" * 64,
        )
        plan = _plan()
        status_client = _StatusClient()
        moneyflow_client = _MoneyflowClient(_moneyflow_row(recovery))
        status = collect_status_plan(
            recovery,
            plan,
            release_scope_sha256=release.sha256,
            client=status_client,
            batch_root=root / "status",
            claim_root=root / "status-claims",
            pause=lambda _: None,
        )
        moneyflow = collect_moneyflow_plan(
            recovery,
            plan,
            release_scope_sha256=release.sha256,
            client=moneyflow_client,
            batch_root=root / "moneyflow",
            claim_root=root / "moneyflow-claims",
            pause=lambda _: None,
        )
        before = status_client.calls
        try:
            collect_status_plan(
                recovery,
                plan,
                release_scope_sha256=release.sha256,
                client=status_client,
                batch_root=root / "status",
                claim_root=root / "status-claims",
                pause=lambda _: None,
            )
        except RecoveryError:
            duplicate_stopped = status_client.calls == before
        else:
            duplicate_stopped = False
    if not duplicate_stopped:
        raise RecoveryError("recovery network fixture did not stop duplicate provider call")
    return {
        "status": "PASS",
        "verdict": "GO_M7_RECOVERY_NETWORK_RELEASE_ENGINEERING_ONLY",
        "release_scope_sha256": release.sha256,
        "status_request_count": status["request_count"],
        "moneyflow_request_count": moneyflow["request_count"],
        "mock_provider_call_count": status_client.calls + moneyflow_client.calls,
        "duplicate_stopped_before_provider": True,
        "external_network_used": False,
        "secret_read": False,
        "real_security_key_read": False,
        "production_authorization": "none",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = verify_network_fixture(args.project_root.resolve(strict=True))
    except (OSError, RecoveryError, TypeError, ValueError) as error:
        print(canonical_json({"status": "FAIL", "error_class": type(error).__name__}))
        return 2
    print(canonical_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
