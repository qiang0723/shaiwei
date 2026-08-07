from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import shutil

import numpy as np
import pandas as pd
import pytest
import yaml

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.topk_conversion.audit import audit
from shaiwei.research.topk_conversion.contract import ConversionError, ProtocolBundle
from shaiwei.research.topk_conversion.execution import (
    assert_top30_compatible,
    backtest_signal,
    scheduled_topk,
)
from shaiwei.research.topk_conversion.metrics import evaluate_case
from shaiwei.research.topk_conversion.synthetic import EXPECTED_CASES, build_bundle, execute_fixture


TEST_ROOT = PROJECT_ROOT / "data/cache/tests/m6_topk_conversion"


@pytest.fixture
def output_root() -> Path:
    shutil.rmtree(TEST_ROOT, ignore_errors=True)
    TEST_ROOT.mkdir(parents=True)
    yield TEST_ROOT
    shutil.rmtree(TEST_ROOT, ignore_errors=True)


def _prediction(*, bse: bool = False, duplicate: bool = False) -> pd.Series:
    dates = pd.bdate_range("2091-01-02", periods=2)
    names = [f"SYN{index:03d}" for index in range(40)]
    if bse:
        names[0] = "430001.BJ"
    index = pd.MultiIndex.from_product([dates, names], names=["datetime", "instrument"])
    if duplicate:
        tuples = list(index)
        tuples[1] = tuples[0]
        index = pd.MultiIndex.from_tuples(tuples, names=index.names)
    return pd.Series(np.arange(len(index), dtype=float), index=index, name="score")


def test_contract_loads_exact_single_variable_result_blind_scope() -> None:
    bundle = ProtocolBundle.load()

    assert bundle.result["single_variable_contract"]["control_value"] == 30
    assert bundle.result["single_variable_contract"]["treatment_value"] == 20
    assert bundle.result["scope"]["changed_portfolio_variable_count"] == 1
    assert bundle.result["scope"]["new_model_arm_count"] == 0
    assert bundle.engineering["authority"]["real_label_or_effect_read_authorized"] is False


def test_contract_rejects_a_second_portfolio_change(output_root: Path) -> None:
    bundle = ProtocolBundle.load()
    changed = deepcopy(bundle.result)
    changed["portfolio_constants"]["n_drop"] = 2
    path = output_root / "changed-result.yaml"
    path.write_text(yaml.safe_dump(changed, sort_keys=False), encoding="utf-8")

    with pytest.raises(ConversionError, match="portfolio constants differ"):
        ProtocolBundle.load(
            result_path=path,
            engineering_path=PROJECT_ROOT
            / "config/m6_csi800_topk20_conversion_engineering_v1.yaml",
        )


def test_schedule_is_deterministic_and_fail_closed_for_bse_or_duplicate_keys() -> None:
    prediction = _prediction()
    first = scheduled_topk(prediction, topk=20, rebalance_days=1)
    shuffled = prediction.sample(frac=1.0, random_state=7)
    second = scheduled_topk(shuffled, topk=20, rebalance_days=1)

    assert first == second
    assert all(len(names) == 20 for names in first.values())
    with pytest.raises(ConversionError, match="contains .BJ"):
        scheduled_topk(_prediction(bse=True), topk=20, rebalance_days=1)
    with pytest.raises(ConversionError, match="keys or schedule"):
        scheduled_topk(_prediction(duplicate=True), topk=20, rebalance_days=1)


def test_portfolio_adapter_changes_only_topk_and_normalizes_injected_report() -> None:
    protocol = ProtocolBundle.load().result
    captured: dict[str, object] = {}

    def fake_backtest(**kwargs):
        captured.update(kwargs)
        dates = pd.bdate_range("2091-01-02", periods=2)
        report = pd.DataFrame(
            {
                "return": [0.001, 0.002],
                "bench": [0.0001, 0.0002],
                "cost": [0.00005, 0.00005],
                "turnover": [0.01, 0.01],
            },
            index=dates,
        )
        return report, object()

    report = backtest_signal(
        _prediction(),
        start="2091-01-02",
        end="2091-01-03",
        protocol=protocol,
        topk=20,
        backtest_function=fake_backtest,
    )

    strategy = captured["strategy"]
    assert strategy.topk == 20
    assert strategy.n_drop == 3
    assert strategy.rebalance_days == 10
    assert captured["account"] == 100_000_000
    assert list(report.columns) == [
        "gross_return",
        "benchmark_return",
        "recorded_cost",
        "turnover",
    ]
    with pytest.raises(ConversionError, match="unregistered TopK"):
        backtest_signal(
            _prediction(),
            start="2091-01-02",
            end="2091-01-03",
            protocol=protocol,
            topk=25,
            backtest_function=fake_backtest,
        )


def test_top30_compatibility_gate_requires_exact_content() -> None:
    reference = {"W1": {"control": [{"value": 1.0}]}}
    assert_top30_compatible(reference, deepcopy(reference))
    changed = deepcopy(reference)
    changed["W1"]["control"][0]["value"] = 2.0
    with pytest.raises(ConversionError, match="Top30 replay differs"):
        assert_top30_compatible(reference, changed)


def test_all_four_synthetic_decisions_are_unique_and_expected() -> None:
    protocols = ProtocolBundle.load()
    bundle = build_bundle(protocols)

    actual = {
        name: evaluate_case(case, protocols.result)["decision"]
        for name, case in bundle["cases"].items()
    }
    assert actual == EXPECTED_CASES


def test_top30_drift_nonfinite_and_bse_fail_before_decision() -> None:
    protocols = ProtocolBundle.load()
    case = build_bundle(protocols)["cases"]["TOPK20_CONVERSION_SUPPORTED"]
    changed = deepcopy(case)
    changed["top30_reference"]["W1"]["clean_lgbm_control_v1"][0]["gross_return"] += 0.1
    with pytest.raises(ConversionError, match="Top30 replay differs"):
        evaluate_case(changed, protocols.result)
    changed = deepcopy(case)
    changed["reports"]["20"]["W1"]["clean_lgbm_control_v1"][0]["gross_return"] = float("nan")
    with pytest.raises(ConversionError, match="nonfinite"):
        evaluate_case(changed, protocols.result)
    changed = deepcopy(case)
    changed["scheduled_names"]["20"]["W1"]["clean_lgbm_control_v1"][0] = "430001.BJ"
    with pytest.raises(ConversionError, match="contains .BJ"):
        evaluate_case(changed, protocols.result)


def test_fixture_writes_identical_passes_and_reuses_same_identity(output_root: Path) -> None:
    runner_root = output_root / "runner"
    first = execute_fixture(runner_root)
    second = execute_fixture(runner_root)
    report = json.loads((runner_root / "report.json").read_text(encoding="utf-8"))

    assert first["bundle_sha256"] == second["bundle_sha256"]
    assert first["report_sha256"] == second["report_sha256"]
    assert first["first_pass_reused"] is False
    assert first["replay_reused"] is False
    assert first["report_reused"] is False
    assert second["first_pass_reused"] is True
    assert second["replay_reused"] is True
    assert second["report_reused"] is True
    assert report["engineering_verdict"] == "GO_ENGINEERING_ONLY"
    assert report["real_m6_effect_read"] is False
    assert report["real_model_fit_count"] == report["real_backtest_count"] == 0


def test_independent_audit_reconstructs_and_reuses(output_root: Path) -> None:
    runner_root = output_root / "runner"
    audit_root = output_root / "audit"
    execute_fixture(runner_root)

    first = audit(runner_root, audit_root)
    second = audit(runner_root, audit_root)

    assert first["independent_audit"] == "PASS"
    assert first["audit_sha256"] == second["audit_sha256"]
    assert first["reused"] is False
    assert second["reused"] is True


def test_independent_audit_rejects_tampered_bundle(output_root: Path) -> None:
    runner_root = output_root / "runner"
    execute_fixture(runner_root)
    path = runner_root / "first_pass/bundle.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    document["cases"]["TOPK20_CONVERSION_SUPPORTED"]["reports"]["20"]["W1"][
        "ridge_alpha1_v1"
    ][0]["gross_return"] += 0.1
    path.write_text(json.dumps(document, sort_keys=True), encoding="utf-8")

    with pytest.raises(ConversionError, match="audit failed"):
        audit(runner_root, output_root / "audit")


def test_independent_auditor_has_no_primary_metric_or_execution_import() -> None:
    text = (PROJECT_ROOT / "src/shaiwei/research/topk_conversion/audit.py").read_text(
        encoding="utf-8"
    )
    statistics = (
        PROJECT_ROOT / "src/shaiwei/research/topk_conversion/audit_statistics.py"
    ).read_text(encoding="utf-8")
    forbidden = ProtocolBundle.load().engineering["architecture"][
        "independent_auditor_forbidden_imports"
    ]

    assert all(value not in text for value in forbidden)
    assert all(value not in statistics for value in forbidden)


def test_docker_services_are_offline_narrow_and_secret_free() -> None:
    compose = yaml.safe_load(
        (PROJECT_ROOT / "compose.m6-topk-conversion.yaml").read_text(encoding="utf-8")
    )
    services = compose["services"]

    assert set(services) == {
        "m6-topk-conversion-fixture",
        "m6-topk-conversion-auditor",
    }
    for service in services.values():
        assert service["network_mode"] == "none"
        assert service["read_only"] is True
        assert service["cap_drop"] == ["ALL"]
        assert service["security_opt"] == ["no-new-privileges:true"]
        assert "env_file" not in service
        assert all("/var/run/docker.sock" not in str(row) for row in service["volumes"])
        assert all("qlib" not in str(row).lower() for row in service["volumes"])
        assert all("model_attribution_v1/effect" not in str(row) for row in service["volumes"])


def test_new_modules_respect_frozen_line_budget() -> None:
    package = PROJECT_ROOT / "src/shaiwei/research/topk_conversion"
    lines = {path.name: len(path.read_text(encoding="utf-8").splitlines()) for path in package.glob("*.py")}

    assert lines
    assert max(lines.values()) <= 400
