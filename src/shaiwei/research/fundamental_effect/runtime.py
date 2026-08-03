"""Explicit study identity for the shared fundamental-effect engine."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EffectRuntime:
    research_family: str
    multiple_testing_families: tuple[str, ...]
    candidate_attempt_count: int
    engine_version: str
    artifact_prefix: str
    residual_schema: str
    factor_test_schema: str
    summary_schema: str
    manifest_schema: str
    candidate_source: str
    model_or_engine: str
    implementation_source: str
    implementation_engine: str
    train_period: str
    valid_period: str

    def __post_init__(self) -> None:
        if not self.research_family or self.research_family not in self.multiple_testing_families:
            raise ValueError("research family must belong to the multiple-testing families")
        if len(self.multiple_testing_families) != len(set(self.multiple_testing_families)):
            raise ValueError("multiple-testing families must be unique")
        if self.candidate_attempt_count < 1:
            raise ValueError("candidate attempt count must be positive")


F1_RUNTIME = EffectRuntime(
    research_family="f1-csi800-fundamental-v1",
    multiple_testing_families=("f1-csi800-fundamental-v1",),
    candidate_attempt_count=6,
    engine_version="f1-csi800-fundamental-effect-v1",
    artifact_prefix="f1-fundamental",
    residual_schema="f1-csi800-fundamental-residual-build-v1",
    factor_test_schema="f1-factor-test-v1",
    summary_schema="f1-csi800-fundamental-effect-summary-v1",
    manifest_schema="f1-csi800-fundamental-effect-manifest-v1",
    candidate_source="Tushare-financial-statements-F1",
    model_or_engine="Alpha158 + frozen fundamental rank blend",
    implementation_source="F1-implementation-attempt",
    implementation_engine="F1 fixed effect runner",
    train_period="2016-07-01~2018-12-31",
    valid_period="W1-W6 + frozen stress periods",
)


F2_RUNTIME = EffectRuntime(
    research_family="f2-csi800-fundamental-dynamics-v1",
    multiple_testing_families=(
        "f1-csi800-fundamental-v1",
        "f2-csi800-fundamental-dynamics-v1",
    ),
    candidate_attempt_count=6,
    engine_version="f2-csi800-fundamental-dynamics-effect-v1",
    artifact_prefix="f2-fundamental-dynamics",
    residual_schema="f2-csi800-fundamental-dynamics-residual-build-v1",
    factor_test_schema="f2-factor-test-v1",
    summary_schema="f2-csi800-fundamental-dynamics-effect-summary-v1",
    manifest_schema="f2-csi800-fundamental-dynamics-effect-manifest-v1",
    candidate_source="Tushare-financial-statements-F2-consecutive-annual-change",
    model_or_engine="Alpha158 + frozen fundamental dynamics rank blend",
    implementation_source="F2-implementation-attempt",
    implementation_engine="F2 fixed effect runner",
    train_period="2016-07-01~2018-12-31",
    valid_period="W1-W6 + frozen stress periods",
)
