from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import pytest
import yaml

from shaiwei.research_gates.m7_moneyflow.contract import canonical_json, sha256_json
from shaiwei.research_gates.m7_moneyflow_lineage.compute import compute_lineage_core
from shaiwei.research_gates.m7_moneyflow_lineage.contract import LineageProtocol, UNIVERSE_IDS
from shaiwei.research_gates.m7_moneyflow_lineage.reader import LineageInputs
from shaiwei.research_gates.m7_moneyflow_recovery.batch_reader import read_receipt
from shaiwei.research_gates.m7_moneyflow_recovery.batch_store import BatchIdentity, write_batch
from shaiwei.research_gates.m7_moneyflow_recovery.contract import RecoveryError, RecoveryProtocol
from shaiwei.research_gates.m7_moneyflow_recovery.fixture import synthetic_inputs
from shaiwei.research_gates.m7_moneyflow_recovery.planning import (
    MoneyflowRequest,
    StatusRequest,
)
from shaiwei.research_gates.m7_moneyflow_recovery.providers import (
    collect_status,
    fetch_moneyflow,
    fetch_status,
)
from shaiwei.research_gates.m7_moneyflow_recovery.release import (
    NonExecutableRecoveryRelease,
    RecoveryReleaseBuild,
    build_synthetic_release,
)
from shaiwei.research_gates.m7_moneyflow_recovery.release_fixture import (
    verify_release_fixture,
)
from shaiwei.research_gates.m7_moneyflow_recovery.target_projection import (
    project_recovery_targets,
)


ROOT = Path(__file__).resolve().parents[1]


def _recovery() -> RecoveryProtocol:
    return RecoveryProtocol.load(
        ROOT / "config/m7_moneyflow_evidence_recovery_v1.yaml",
        engineering_path=ROOT / "config/m7_moneyflow_evidence_recovery_engineering_v1.yaml",
        project_root=ROOT,
    )


def _lineage() -> LineageProtocol:
    return LineageProtocol.load(ROOT / "config/m7_moneyflow_gap_lineage_v1.yaml", project_root=ROOT)


def _projection_inputs() -> LineageInputs:
    a_count, b_count = 908, 541
    records = []
    for index in range(a_count + b_count):
        records.append(
            {
                "trade_date": "20210104",
                "formation_date": "20201231",
                "universe_id": UNIVERSE_IDS[index % len(UNIVERSE_IDS)],
                "ts_code": f"{680000 + index:06d}.SH",
                "segment": "2021H1",
            }
        )
    membership = pd.DataFrame(records)
    a_codes = membership.iloc[:a_count]["ts_code"]
    b_codes = membership.iloc[a_count:]["ts_code"]
    suspension = pd.DataFrame(
        {
            "ts_code": a_codes,
            "trade_date": "20201231",
            "primary_full_day": 1,
            "primary_intraday": 0,
        }
    )
    daily = pd.DataFrame({"ts_code": b_codes, "trade_date": "20201231"})
    return LineageInputs(
        membership=membership,
        moneyflow_keys=pd.DataFrame(columns=("ts_code", "trade_date", "request_trade_date")),
        daily_keys=daily,
        suspension=suspension,
        independent_status=pd.DataFrame(
            columns=(
                "ts_code",
                "trade_date",
                "independent_nontrading",
                "independent_trading",
                "invalid_status_rows",
            )
        ),
        official_dates=("20201231", "20210104"),
        quarantined_source_dates=frozenset(),
        evidence={"numeric_moneyflow_value_columns_read": 0},
    )


def test_exact_target_projection_reuses_lineage_and_is_aggregate_only() -> None:
    inputs = _projection_inputs()
    lineage = _lineage()
    expected = sha256_json(compute_lineage_core(lineage, inputs))
    track_a, track_b, summary = project_recovery_targets(
        _recovery(), lineage, inputs, expected_lineage_core_sha256=expected
    )
    assert len(track_a) == 908
    assert len(track_b) == 541
    assert set(track_a["trade_date"]) == {"20201231"}
    assert set(track_b["trade_date"]) == {"20201231"}
    assert summary["numeric_moneyflow_value_columns_read"] == 0
    assert re.search(r"[0-9]{6}\.(?:SH|SZ|BJ)", canonical_json(summary)) is None


class _BsResult:
    error_code = "0"
    error_msg = ""
    fields = ["date", "code", "tradestatus"]

    def __init__(self) -> None:
        self.rows = iter([["2021-01-04", "sh.688001", "0"]])
        self.current: list[str] | None = None

    def next(self) -> bool:
        self.current = next(self.rows, None)
        return self.current is not None

    def get_row_data(self) -> list[str]:
        assert self.current is not None
        return self.current


class _BsClient:
    def __init__(self) -> None:
        self.calls = 0

    def query_history_k_data_plus(self, **kwargs: str) -> _BsResult:
        self.calls += 1
        assert kwargs["fields"] == "date,code,tradestatus"
        return _BsResult()


class _TsClient:
    def __init__(self, frame: pd.DataFrame) -> None:
        self.frame = frame
        self.calls = 0

    def query(self, api_name: str, **kwargs: object) -> pd.DataFrame:
        self.calls += 1
        assert api_name == "moneyflow"
        assert "fields" in kwargs
        return self.frame.copy()


def test_dependency_injected_providers_make_one_mock_call_and_no_env_read() -> None:
    bs = _BsClient()
    status = fetch_status(bs, StatusRequest("688001.SH", "20210104", "20210104", ("20210104",)))
    assert bs.calls == 1
    assert status.to_dict("records") == [
        {"ts_code": "688001.SH", "trade_date": "20210104", "trade_status": "0"}
    ]
    protocol = _recovery()
    clean = synthetic_inputs(protocol).targeted_rows.iloc[[0]]
    ts = _TsClient(clean)
    result = fetch_moneyflow(
        ts,
        protocol,
        MoneyflowRequest(
            "one_security_one_date",
            {"ts_code": "688000.SH", "start_date": "20210105", "end_date": "20210105"},
        ),
    )
    assert ts.calls == 1
    assert tuple(result.columns) == protocol.moneyflow_fields


def test_claimed_provider_entry_stops_duplicate_before_mock_call(tmp_path: Path) -> None:
    client = _BsClient()
    request = StatusRequest("688001.SH", "20210104", "20210104", ("20210104",))
    first = collect_status(
        tmp_path,
        release_scope_sha256="a" * 64,
        client=client,
        request=request,
    )
    assert first.attempt_count == 1
    with pytest.raises(RecoveryError, match="already claimed"):
        collect_status(
            tmp_path,
            release_scope_sha256="a" * 64,
            client=client,
            request=request,
        )
    assert client.calls == 1


def test_isolated_batch_is_write_once_and_detects_tampering(tmp_path: Path) -> None:
    frame = pd.DataFrame([{"ts_code": "688001.SH", "trade_date": "20210104", "trade_status": "0"}])
    identity = BatchIdentity("a" * 64, "b" * 64, "baostock.history_k_data_plus", "exact_status_window")
    receipt = write_batch(tmp_path, identity, frame)
    receipt_path = tmp_path / Path(receipt["batch_relative_path"]).with_name("receipt.json")
    _, observed = read_receipt(tmp_path, receipt_path)
    assert observed.equals(frame)
    with pytest.raises(RecoveryError, match="already consumed"):
        write_batch(tmp_path, identity, frame)
    (tmp_path / receipt["batch_relative_path"]).write_bytes(b"tampered")
    with pytest.raises(RecoveryError):
        read_receipt(tmp_path, receipt_path)


def test_synthetic_release_is_non_executable_and_fixture_passes() -> None:
    build = RecoveryReleaseBuild.load(
        ROOT / "config/m7_moneyflow_recovery_release_build_v1.yaml", project_root=ROOT
    )
    document = build_synthetic_release(
        build,
        implementation_commit="a" * 40,
        code_bundle_sha256="b" * 64,
        image_id="sha256:" + "c" * 64,
        target_plan_manifest_sha256="d" * 64,
        request_bundles={},
    )
    release = NonExecutableRecoveryRelease.parse(canonical_json(document) + "\n", build)
    assert release.document["scope"]["authority"]["execution_authorized"] is False
    result = verify_release_fixture(ROOT)
    assert result["verdict"] == "GO_M7_RECOVERY_RELEASE_ENGINEERING_ONLY"
    assert result["actual_provider_call_count"] == 0
    assert result["collector_writable_roots_separate"] is True
    assert result["independent_audit_exact_match"] is True


def test_release_docker_role_is_offline_unmounted_and_modules_remain_small() -> None:
    compose = yaml.safe_load(
        (ROOT / "compose.m7-moneyflow-evidence-recovery.yaml").read_text(encoding="utf-8")
    )
    service = compose["services"]["m7-recovery-release-fixture"]
    assert service["network_mode"] == "none"
    assert service["read_only"] is True
    assert service["user"] == "65532:65532"
    serialized = canonical_json(service)
    assert all(token not in serialized for token in ("volumes", ".env", "docker.sock", "/workspace"))
    package = ROOT / "src/shaiwei/research_gates/m7_moneyflow_recovery"
    assert max(len(path.read_text(encoding="utf-8").splitlines()) for path in package.glob("*.py")) <= 400
    provider_source = (package / "providers.py").read_text(encoding="utf-8")
    assert "shaiwei.config" not in provider_source
    assert "create_client" not in provider_source
