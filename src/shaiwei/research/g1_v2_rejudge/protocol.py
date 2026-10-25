"""严格载入冻结配置 `config/g1_v2_rejudge_v2.yaml`：21 个定义的身份、复现目标与 P1 原代码哈希、g1-v2 规格绑定，任一漂移即拒绝。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from shaiwei.config import PROJECT_ROOT, Settings
from shaiwei.ledger import LEDGER_DIR, sha256_file

CONFIG_PATH = PROJECT_ROOT / "config" / "g1_v2_rejudge_v2.yaml"
FACTOR_ADMISSIONS_V2 = LEDGER_DIR / "factor_admissions_v2.csv"
FAMILIES = (
    "stage1-gp-preflight-v1",
    "p1-moneyflow-v1",
    "f1-csi800-fundamental-v1",
    "f2-csi800-fundamental-dynamics-v1",
)


class RejudgeProtocolError(RuntimeError):
    pass


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Judge(_Frozen):
    spec_version: Literal["g1-v2"]
    spec_config: str
    spec_config_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class Baseline(_Frozen):
    head_before_freeze: str = Field(pattern=r"^[0-9a-f]{40}$")
    experiments_rows: int
    factor_admissions_v1_decisions: Literal[29]
    factor_admissions_v1_admitted: Literal[0]
    factor_admissions_v1_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    factor_admissions_v2_exists: Literal[False]
    g1_v2_statistics_on_candidates: Literal[0]
    family_n_before: dict[str, int]


class Decisions(_Frozen):
    ledger: Literal["new:ledger/factor_admissions_v2.csv"]
    reports_dir: Literal["logs/g1-v2"]
    gp_placeholder_rationale: Literal["rejudge_and_report_reject"]
    unit: Literal["distinct_factor_definition_latest_v1_generation"]
    p1_reconstruction: Literal["original_tools_p1_moneyflow_code_and_raw_panel_with_reproduction_gate"]
    multiple_testing_families: Literal["as_declared_by_v1_evidence"]
    pass_meaning: Literal["ledger_only_library_insertion_requires_separate_protocol"]


class Superseded(_Frozen):
    candidate_experiment_id: str
    v1_decision_id: str
    v1_code_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class Supersedes(_Frozen):
    protocol_id: Literal["g1-v2-rejudge-v1"]
    config: str
    voided_before_results: Literal[True]


class P1Source(_Frozen):
    tool_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    tool_files: dict[str, str]
    raw_candidates_path: str
    raw_candidates_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ReproductionGate(_Frozen):
    max_abs_daily_difference: float = Field(gt=0, le=1e-6)
    on_failure: Literal["NOT_REEVALUATED"]
    retry_after_failure: Literal[False]


class Target(_Frozen):
    kind: Literal["factor_panel", "daily_ic"]
    path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class Candidate(_Frozen):
    candidate_experiment_id: str = Field(min_length=1)
    v1_decision_id: str = Field(min_length=1)
    formula: str = Field(min_length=1)
    v1_evidence_path: str
    v1_evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    rationale_chars: int = Field(ge=0)
    reproduction_target: Target
    v1_code_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    v1_family_trial_count: int = Field(ge=1)
    supersedes: tuple[Superseded, ...] = ()


class Isolation(_Frozen):
    forbidden_writes: tuple[str, ...]
    network: Literal[False]
    secrets: Literal[False]
    data_read_only: tuple[str, ...]


class RejudgeConfig(_Frozen):
    schema_version: Literal["g1-v2-rejudge-v2"]
    protocol_id: Literal["g1-v2-rejudge-v2"]
    status: Literal["FROZEN_BEFORE_RESULTS"]
    frozen_on: date
    document: str
    supersedes: Supersedes
    judge: Judge
    result_blind_baseline: Baseline
    decisions: Decisions
    multiple_testing_families: dict[str, tuple[str, ...]]
    family_order: tuple[str, ...]
    p1_source: P1Source
    reproduction_gate: ReproductionGate
    attempts_per_unit: Literal[1]
    families: dict[str, tuple[Candidate, ...]]
    isolation: Isolation

    def candidates(self) -> list[tuple[str, Candidate]]:
        return [(family, candidate) for family in self.family_order for candidate in self.families[family]]


@dataclass(frozen=True)
class RejudgeIdentity:
    config: RejudgeConfig
    config_sha256: str
    document_sha256: str
    spec_sha256: str


def _check(condition: bool, message: str) -> None:
    if not condition:
        raise RejudgeProtocolError(message)


def load_rejudge_protocol(settings: Settings, path: Path = CONFIG_PATH, *, verify_artifacts: bool = True) -> RejudgeIdentity:
    """冻结身份逐项核对：g1-v2 规格 SHA、协议文档、家族与候选数、每个 v1 证据与复现目标的哈希。"""
    from shaiwei.research.g1_v2 import load_spec

    config = RejudgeConfig.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
    document = PROJECT_ROOT / config.document
    _check(document.is_file(), f"re-judge protocol document is missing: {config.document}")
    spec = load_spec(settings, PROJECT_ROOT / config.judge.spec_config)
    _check(spec.sha256 == config.judge.spec_config_sha256, "g1-v2 spec sha256 drifted from the frozen re-judge protocol")
    _check(tuple(config.families) == FAMILIES and config.family_order == FAMILIES, "re-judge families or order differ from the frozen four")
    counts = {family: len(config.families[family]) for family in FAMILIES}
    _check(counts == {FAMILIES[0]: 4, FAMILIES[1]: 6, FAMILIES[2]: 6, FAMILIES[3]: 5}, f"unit counts drifted: {counts}")
    identifiers = [candidate.candidate_experiment_id for _, candidate in config.candidates()]
    _check(len(identifiers) == len(set(identifiers)) == 21, "re-judge units must be 21 unique experiments")
    superseded = [item.candidate_experiment_id for _, candidate in config.candidates() for item in candidate.supersedes]
    _check(len(superseded) == 8 and not set(superseded) & set(identifiers), "the 8 superseded v1 decisions must stay out of the units")
    for family in FAMILIES:
        formulas = [candidate.formula for candidate in config.families[family]]
        _check(len(formulas) == len(set(formulas)), f"{family} repeats a factor definition")
        declared = config.multiple_testing_families[family]
        _check(family in declared and set(declared) <= set(FAMILIES), f"{family} multiple-testing families are invalid")
    if verify_artifacts:
        source = config.p1_source
        _check(sha256_file(PROJECT_ROOT / source.raw_candidates_path) == source.raw_candidates_sha256, "P1 raw candidate panel changed")
        _check((PROJECT_ROOT / "tools" / "__init__.py").is_file(), "tools package marker is missing")
        for relative, digest in source.tool_files.items():
            _check(sha256_file(PROJECT_ROOT / relative) == digest, f"P1 original code changed: {relative}")
        for _, candidate in config.candidates():
            _check(sha256_file(PROJECT_ROOT / candidate.v1_evidence_path) == candidate.v1_evidence_sha256, f"v1 evidence changed: {candidate.candidate_experiment_id}")
            target = candidate.reproduction_target
            _check(sha256_file(PROJECT_ROOT / target.path) == target.sha256, f"reproduction target changed: {candidate.candidate_experiment_id}")
    return RejudgeIdentity(config=config, config_sha256=sha256_file(path), document_sha256=sha256_file(document), spec_sha256=spec.sha256)
