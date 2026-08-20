"""Container entrypoint profiles for versioned Head30 release protocols."""

from __future__ import annotations

from dataclasses import dataclass


RUN_MODULE = "shaiwei.research.production_conversion.real_run"
AUDIT_MODULE = "shaiwei.research.production_conversion.real_audit"


@dataclass(frozen=True)
class RuntimeProfile:
    runner_service: str
    auditor_service: str
    runner_command: tuple[str, ...]
    auditor_command: tuple[str, ...]


def _commands(protocol_file: str | None) -> tuple[tuple[str, ...], tuple[str, ...]]:
    protocol = (
        ("--protocol", f"/workspace/config/{protocol_file}")
        if protocol_file
        else ()
    )
    runner = (
        "python", "-m", RUN_MODULE, *protocol,
        "--release", "/inputs/release.json",
        "--approval", "/inputs/approval.json",
        "--provider-root", "/qlib",
        "--m6-effect-root", "/m6-effect",
        "--m6-audit", "/inputs/m6-audit.json",
        "--output-root", "/outputs",
    )
    auditor = (
        "python", "-m", AUDIT_MODULE, *protocol,
        "--release", "/inputs/release.json",
        "--approval", "/inputs/approval.json",
        "--effect-root", "/outputs",
        "--audit-root", "/audit",
    )
    return runner, auditor


def _profile(name: str, protocol_file: str | None) -> RuntimeProfile:
    runner, auditor = _commands(protocol_file)
    return RuntimeProfile(
        runner_service=f"m6-production-head30-{name}runner",
        auditor_service=f"m6-production-head30-{name}auditor",
        runner_command=runner,
        auditor_command=auditor,
    )


PROFILES = {
    "m6-csi800-production-head30-release-v1": _profile("", None),
    "m6-csi800-production-head30-entrypoint-recovery-v1": _profile(
        "recovery-", "m6_csi800_production_head30_entrypoint_recovery_v1.yaml"
    ),
    "m6-csi800-production-head30-price-recovery-v1": _profile(
        "price-recovery-", "m6_csi800_production_head30_price_recovery_v1.yaml"
    ),
}
BASE_PROFILE = PROFILES["m6-csi800-production-head30-release-v1"]


def runtime_profile(protocol_id: str) -> RuntimeProfile:
    try:
        return PROFILES[protocol_id]
    except KeyError as error:
        raise ValueError("production-converter runtime profile is unknown") from error


__all__ = ["BASE_PROFILE", "RuntimeProfile", "runtime_profile"]
