"""g1-positive-control-v2 的合成端到端：g1-v2 裁判、PIT 中性化、逐日配对证据与 N3 基线复制对照（不读真实数据）。"""

import csv
import json
from dataclasses import replace

import pytest
from pydantic import ValidationError

from shaiwei.ledger import EXPERIMENTS, FACTOR_ADMISSIONS
from shaiwei.research.g1 import G1Evidence
from shaiwei.research.g1_calibration import audit as audit_module
from shaiwei.research.g1_calibration import execute as execute_module
from shaiwei.research.g1_calibration import runner, signals
from shaiwei.research.g1_calibration.protocol import CONFIG_PATH_V2, load_protocol
from shaiwei.research.g1_calibration.scope import approval_text, ledger_baseline, record_approval
from shaiwei.research.g1_v2 import G1EvidenceV2, load_spec
from tests.test_g1_calibration import _context, _roots, baselines, research, settings  # noqa: F401
from tests.test_g1_calibration_release import FACTS, _install, _scope


@pytest.fixture(scope="module")
def protocol_v2(settings):  # noqa: F811
    return load_protocol(settings, CONFIG_PATH_V2)


def _reduced_v2(protocol, *, seeds=2):
    config = protocol.config
    routes = dict(config.routes)
    for route in ("N1", "N2", "N3"):
        start = config.routes[route].seed_values()[0]
        routes[route] = config.routes[route].model_copy(update={"seeds": tuple(range(start, start + seeds))})
    reduced = config.model_copy(update={
        "routes": routes, "calibration": config.calibration.model_copy(update={"target_mean_rank_ic": (0.04,)}),
    })
    return replace(protocol, config=reduced)


def test_v2_protocol_is_bound_to_g1_v2_and_plans_n3(settings, protocol_v2):  # noqa: F811
    assert protocol_v2.version == "v2" and protocol_v2.gates == frozenset(load_spec(settings).spec.gates)
    cells = signals.plan_cells(protocol_v2, 30)
    assert [cell[0].route for cell in cells][-1] == "N3" and len(cells[-1]) == 30
    assert sum(len(cell) for cell in cells) == 123
    assert sum(len(cell) for cell in signals.plan_cells(protocol_v2, 10)) == 83  # 削减只动 N1/N2，从不动 N3


@pytest.fixture(scope="module")
def executed_v2(tmp_path_factory, settings, protocol_v2, research, baselines):  # noqa: F811
    patcher = pytest.MonkeyPatch()
    patcher.setattr(runner, "_max_library_correlation", lambda *_args: 0.0)
    tmp_path = tmp_path_factory.mktemp("g1-v2")
    reduced = _reduced_v2(protocol_v2)
    execution = "g1cal-0123456789ab-20261025T010000Z"
    roots = _roots(settings, tmp_path, execution)
    formal = {path: path.read_bytes() for path in (EXPERIMENTS, FACTOR_ADMISSIONS)}
    admissions = tmp_path / "factor_admissions.csv"
    admissions.write_bytes(FACTOR_ADMISSIONS.read_bytes())
    baseline = ledger_baseline(reduced, experiments=roots.experiments, runs=roots.runs, admissions=admissions)
    scope = _scope(reduced, evaluations=19, execution=execution, baseline=baseline).model_copy(update={"protocol_id": reduced.config.protocol_id})
    control = tmp_path / "control"
    envelope = _install(scope, control)
    record_approval(envelope.scope_sha256, approval_text(envelope), control)
    patcher.setattr(execute_module, "load_protocol", lambda *_args: reduced)
    result = execute_module.execute(
        envelope.scope_sha256, settings=settings, control=control, roots=roots, facts=lambda _settings: FACTS,
        admissions=admissions, context_loader=lambda s, p, timings: _context(s, p, research, baselines),
    )
    document = json.loads((roots.reports / "summary.json").read_text(encoding="utf-8"))
    yield {"document": document, "roots": roots, "reduced": reduced, "formal": formal, "result": result,
           "control": control, "admissions": admissions, "execution": execution}
    patcher.undo()


def test_v2_run_completes_with_increment_evidence_and_ledger_fields(executed_v2):
    document, roots = executed_v2["document"], executed_v2["roots"]
    assert {path: path.read_bytes() for path in executed_v2["formal"]} == executed_v2["formal"]
    summary = document["summary"]
    assert summary["status"] == "COMPLETE" and summary["terminal_state"] in executed_v2["reduced"].config.interpretation.terminal_states
    assert summary["increment_control"]["judged"] == 2 and summary["increment_control"]["judged_gates"] == [
        "incremental_icir_t", "valid_trial_increment_irs", "deflated_increment_ir",
    ]
    rows = list(csv.DictReader(roots.experiments.open(encoding="utf-8")))
    families = {json.loads(row["params_json"])["g1_research_family"] for row in rows}
    assert all(family.startswith("g1-calibration-v2/") for family in families) and len(rows) == 19
    for row in rows:
        result = json.loads(row["result_json"])
        assert "selection_increment_ir" in result
        assert ("selection_sharpe" in result) == (json.loads(row["params_json"])["route"] != "N3")


def test_v2_evidence_uses_schema_2_and_the_formal_v1_judge_rejects_it(executed_v2):
    roots = executed_v2["roots"]
    evidence = json.loads(next((roots.data / "R1" / "0.04").glob("*/g1_evidence.json")).read_text(encoding="utf-8"))
    assert evidence.pop("admission_scope") == "NOT_FOR_ADMISSION"
    assert evidence["schema_version"] == 2 and evidence["neutralization"] == "pit_support"
    G1EvidenceV2.model_validate(evidence)
    with pytest.raises(ValidationError):
        G1Evidence.model_validate(evidence)
    n3 = json.loads(next((roots.data / "N3").glob("*/increment_evidence.json")).read_text(encoding="utf-8"))
    assert n3["schema_version"] == "g1-calibration-increment-v1" and set(n3) >= {"candidate_score_rank_ic", "baseline_score_rank_ic"}


def test_v2_reports_carry_the_g1_v2_gate_set_and_n3_judges_only_increments(settings, executed_v2):  # noqa: F811
    roots = executed_v2["roots"]
    spec = load_spec(settings)
    report = json.loads(next((roots.reports / "R1" / "0.04").glob("*.json")).read_text(encoding="utf-8"))
    assert set(report["gates"]) == set(spec.spec.gates) and report["bindings"]["spec_sha256"] == spec.sha256
    assert "increment_t" in report["statistics"] and "excess_t" in report["statistics"]
    n3 = json.loads(next((roots.reports / "N3").glob("*.json")).read_text(encoding="utf-8"))
    assert set(n3["gates"]) == {"incremental_icir_t", "valid_trial_increment_irs", "deflated_increment_ir"}
    assert n3["layers"]["main"] == all(gate["passed"] for gate in n3["gates"].values())


def test_v2_independent_audit_passes_and_recomputes_the_terminal_state(settings, executed_v2):  # noqa: F811
    roots = executed_v2["roots"]
    result = audit_module.audit(
        executed_v2["execution"], settings=settings, protocol=executed_v2["reduced"], data_dir=roots.data,
        reports_dir=roots.reports, control_root=executed_v2["control"], experiments=roots.experiments,
        runs=roots.runs, admissions=executed_v2["admissions"],
    )
    assert result["status"] == "PASS", result["findings"]
    assert result["units_audited"] == 19 and result["recomputed_terminal_state"] == executed_v2["result"]["terminal_state"]
