from __future__ import annotations

from copy import deepcopy
import json
import shutil

import numpy as np
import pandas as pd
import pytest
import yaml

from shaiwei.config import PROJECT_ROOT
from shaiwei.provenance import code_snapshot_sha256, git_head
from shaiwei.research.model_attribution.audit import audit
from shaiwei.research.model_attribution.clock import (
    load_calendar,
    mature_last_signal,
    verify_frozen_windows,
)
from shaiwei.research.model_attribution.contract import (
    AttributionError,
    ProtocolBundle,
    project_path,
    write_once_json,
)
from shaiwei.research.model_attribution.inference import (
    decide_from_passes,
    evaluate_alternatives,
    holm_adjust,
    newey_west_mean_t,
)
from shaiwei.research.model_attribution.models import (
    fit_predict_with_injected_models,
    model_factory_smoke,
)
from shaiwei.research.model_attribution.scoring import (
    maximum_drawdown,
    portfolio_conversion_summary,
    rank_blend,
)
from shaiwei.research.model_attribution.synthetic import (
    _arm_evidence,
    _synthetic_score_windows,
    run,
)


CALENDAR = PROJECT_ROOT / "data/qlib_bin/calendars/day.txt"
MANIFEST = PROJECT_ROOT / "data/qlib_bin/_shaiwei_manifest.json"
TEST_ROOT = PROJECT_ROOT / "data/research/m6_csi800_model_attribution_v1/test-work"


@pytest.fixture(autouse=True)
def clean_test_root():
    shutil.rmtree(TEST_ROOT, ignore_errors=True)
    TEST_ROOT.mkdir(parents=True, exist_ok=True)
    yield
    shutil.rmtree(TEST_ROOT, ignore_errors=True)


def test_protocol_bundle_metadata_and_calendar_boundaries_are_exact() -> None:
    bundle = ProtocolBundle.load()
    metadata = bundle.verify_metadata_inputs(MANIFEST, CALENDAR)
    assert metadata["semantic_market_rows_read"] is False
    assert metadata["qlib_tree_sha256"] == (
        "0532f6cd7c2c78f0936f92a986aef83a848175fe6f332274e06c7ed6e8c11778"
    )
    calendar = load_calendar(CALENDAR)
    assert mature_last_signal(calendar, "2018-06-30", 11) == "20180613"
    verified = verify_frozen_windows(bundle.result, calendar)
    assert len(verified) == 6
    assert verified[-1]["score_last_signal"] == "2024-12-16"


def test_protocol_parameter_and_clock_tampering_fail_closed() -> None:
    bundle = ProtocolBundle.load()
    result = deepcopy(bundle.result)
    result["portfolio"]["topk"] = 31
    result_path = TEST_ROOT / "result.yaml"
    result_path.write_text(yaml.safe_dump(result, sort_keys=False), encoding="utf-8")
    with pytest.raises(AttributionError, match="portfolio differs"):
        ProtocolBundle.load(result_path=result_path)

    result["portfolio"]["topk"] = 30
    result["arms"][1]["parameters"]["alpha"] = 2.0
    result_path.write_text(yaml.safe_dump(result, sort_keys=False), encoding="utf-8")
    with pytest.raises(AttributionError, match="Ridge parameters differ"):
        ProtocolBundle.load(result_path=result_path)

    result = deepcopy(bundle.result)
    result["windows"][0]["purged_train_last_signal"] = "2018-06-14"
    with pytest.raises(AttributionError, match="boundary differs"):
        verify_frozen_windows(result, load_calendar(CALENDAR))


def test_qlib_factories_are_instantiated_without_fit() -> None:
    smoke = model_factory_smoke(ProtocolBundle.load().result)
    assert smoke == {
        "control_class": "qlib.contrib.model.gbdt.LGBModel",
        "ridge_class": "qlib.contrib.model.linear.LinearModel",
        "ridge_estimator": "ridge",
        "ridge_alpha": 1.0,
        "fit_called": False,
    }


def test_injected_training_adapter_has_a_narrow_testable_boundary() -> None:
    index = pd.MultiIndex.from_tuples(
        [(pd.Timestamp("2024-01-02"), "SYN000")],
        names=["datetime", "instrument"],
    )

    class Stub:
        def __init__(self, value: float):
            self.value = value
            self.fitted = False

        def fit(self, dataset):
            assert dataset == "synthetic-dataset"
            self.fitted = True

        def predict(self, dataset, segment):
            assert self.fitted and dataset == "synthetic-dataset" and segment == "test"
            return pd.Series([self.value], index=index)

    control, ridge = Stub(1.0), Stub(2.0)
    predictions = fit_predict_with_injected_models(
        "synthetic-dataset",
        model_factory=lambda: (control, ridge),
    )
    assert predictions[0].iloc[0] == 1.0
    assert predictions[1].iloc[0] == 2.0


def test_rank_blend_is_deterministic_and_key_or_value_drift_fails() -> None:
    values = _synthetic_score_windows(seed=1, days=3, instruments=4)["W1"]
    first = rank_blend(values[0], values[1])
    second = rank_blend(values[0], values[1])
    pd.testing.assert_series_equal(first, second)
    expected = (
        values[0].groupby(level=0).rank(method="average", pct=True)
        + values[1].groupby(level=0).rank(method="average", pct=True)
    ) / 2
    pd.testing.assert_series_equal(first, expected.rename("score"))

    mismatched = values[1].iloc[1:]
    with pytest.raises(AttributionError, match="keys differ"):
        rank_blend(values[0], mismatched)
    nonfinite = values[1].copy()
    nonfinite.iloc[0] = np.nan
    with pytest.raises(AttributionError, match="nonfinite"):
        rank_blend(values[0], nonfinite)


def test_hac_holm_portfolio_and_decision_precedence() -> None:
    values = (0.0003 + 0.00008 * np.sin(np.arange(1260) / 4.0)).tolist()
    assert newey_west_mean_t(values, lags=10) > 3
    adjusted = holm_adjust({"ridge": 0.01, "blend": 0.04})
    assert adjusted == {"ridge": 0.02, "blend": 0.04}
    with pytest.raises(AttributionError, match="two finite"):
        holm_adjust({"a": 0.1})

    evidence = {
        "ridge_alpha1_v1": _arm_evidence(
            score_pass=True, portfolio_shift=0.00030, seed=1
        ),
        "lgbm_ridge_rank_blend_50_50_v1": _arm_evidence(
            score_pass=False, portfolio_shift=-0.00010, seed=2
        ),
    }
    result = evaluate_alternatives(evidence, ProtocolBundle.load().result)
    assert result["decision"] == "MODEL_STRUCTURE_SUPPORTED"
    assert decide_from_passes(result["decision_inputs"], blocked=True) == "BLOCKED"


def test_portfolio_summary_cost_turnover_and_drawdown_are_recomputed() -> None:
    base = {f"W{window}": (0.001, -0.0005, 0.0008) for window in range(1, 7)}
    better = {f"W{window}": (0.0012, -0.0004, 0.0010) for window in range(1, 7)}
    control = {scenario: base for scenario in ("1", "1.5", "2")}
    alternative = {scenario: better for scenario in ("1", "1.5", "2")}
    summary = portfolio_conversion_summary(
        control,
        alternative,
        control_turnover=100.0,
        alternative_turnover=90.0,
    )
    assert summary["positive_base_delta_windows"] == 6
    assert all(value > 0 for value in summary["pooled_cost_delta"].values())
    assert summary["turnover_ratio"] == 0.9
    assert summary["maximum_drawdown"] == maximum_drawdown(better["W1"])


def test_write_once_and_project_path_fail_closed() -> None:
    path = TEST_ROOT / "evidence.json"
    digest, reused = write_once_json(path, {"a": 1})
    assert len(digest) == 64 and reused is False
    assert write_once_json(path, {"a": 1}) == (digest, True)
    with pytest.raises(AttributionError, match="write-once conflict"):
        write_once_json(path, {"a": 2})
    with pytest.raises(AttributionError, match="escapes"):
        project_path("../outside")


def test_synthetic_runner_replay_and_independent_audit_are_deterministic() -> None:
    report = TEST_ROOT / "report.json"
    audit_path = TEST_ROOT / "audit.json"
    first = run(MANIFEST, CALENDAR, report)
    second = run(MANIFEST, CALENDAR, report)
    assert first["report_sha256"] == second["report_sha256"]
    assert first["reused"] is False and second["reused"] is True
    document = json.loads(report.read_text(encoding="utf-8"))
    assert document["engineering_verdict"] == "GO_ENGINEERING_ONLY"
    assert document["strategy_effective"] == "NOT_EVALUATED"
    assert document["release_identity"] == {
        "git_head": git_head(),
        "code_snapshot_sha256": code_snapshot_sha256(),
        "embedded_release_manifest_verified": False,
    }
    assert len(document["decision_cases"]) == 5
    assert all(document["failure_closed_checks"].values())

    first_audit = audit(report, CALENDAR, audit_path)
    second_audit = audit(report, CALENDAR, audit_path)
    assert first_audit["audit_sha256"] == second_audit["audit_sha256"]
    assert first_audit["reused"] is False and second_audit["reused"] is True


def test_independent_audit_rejects_tampered_decision_and_does_not_import_inference() -> None:
    report = TEST_ROOT / "report.json"
    run(MANIFEST, CALENDAR, report)
    document = json.loads(report.read_text(encoding="utf-8"))
    document["decision_cases"][0]["actual"] = "MIXED_NOT_CONCLUSIVE"
    report.write_text(json.dumps(document, sort_keys=True), encoding="utf-8")
    with pytest.raises(AttributionError, match="independent audit failed"):
        audit(report, CALENDAR, TEST_ROOT / "audit.json")

    source = (PROJECT_ROOT / "src/shaiwei/research/model_attribution/audit.py").read_text()
    assert "model_attribution.inference" not in source


def test_m6_docker_profile_is_offline_narrow_and_non_production() -> None:
    compose = yaml.safe_load((PROJECT_ROOT / "compose.research.yaml").read_text())
    service = compose["services"]["m6-model-attribution-engineering"]
    assert service["profiles"] == ["m6-model-attribution-engineering"]
    assert service["network_mode"] == "none"
    assert service["read_only"] is True
    assert service["cap_drop"] == ["ALL"]
    assert service["security_opt"] == ["no-new-privileges:true"]
    assert "ports" not in service and "env_file" not in service
    sources = [volume["source"] for volume in service["volumes"]]
    assert sources == [
        "./data/qlib_bin/_shaiwei_manifest.json",
        "./data/qlib_bin/calendars/day.txt",
        "./data/research/m6_csi800_model_attribution_v1/engineering",
    ]
    assert "./data" not in sources and "./ledger" not in sources and "." not in sources
    targets = [volume["target"] for volume in service["volumes"]]
    assert targets[:2] == [
        "/inputs/m6_frozen_qlib_manifest.json",
        "/inputs/m6_frozen_calendar.txt",
    ]
    assert all(not target.startswith("/workspace/config/") for target in targets)
    assert service["command"][:3] == [
        "python",
        "-m",
        "shaiwei.research.model_attribution.synthetic",
    ]
