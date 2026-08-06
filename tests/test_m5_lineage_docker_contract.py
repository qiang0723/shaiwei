from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).parents[1]


def test_lineage_image_contains_only_frozen_controls_and_code() -> None:
    dockerfile = (ROOT / "Dockerfile.m5-lineage-recovery").read_text(encoding="utf-8")
    for required in (
        "m5_dynamic_fundamental_source_lineage_recovery_v3.yaml",
        "m5_dynamic_fundamental_source_lineage_scope_recovery_v4.yaml",
        "m5_dynamic_fundamental_source_lineage_recovery_protocol_scope_v4.json",
        "m5_dynamic_fundamental_source_lineage_build_v4.yaml",
        "ADR_0004_M5_STATEMENT_VERSION_LINEAGE.md",
        "M5_DYNAMIC_FUNDAMENTAL_SOURCE_LINEAGE_SCOPE_RECOVERY_PROTOCOL_20260806.md",
        "M5_DYNAMIC_FUNDAMENTAL_SOURCE_LINEAGE_REAL_RUN_ACCEPTANCE_20260806.md",
    ):
        assert required in dockerfile
    for forbidden in ("COPY data", "COPY ledger", "COPY logs", "COPY .env", "COPY tests"):
        assert forbidden not in dockerfile


def test_lineage_compose_is_offline_short_lived_and_directional() -> None:
    compose = yaml.safe_load((ROOT / "compose.m5-lineage.yaml").read_text(encoding="utf-8"))
    services = compose["services"]
    assert set(services) == {
        "m5-lineage-fixture",
        "m5-lineage-runner",
        "m5-lineage-auditor",
        "m5-lineage-registry",
    }
    for service in services.values():
        assert service["network_mode"] == "none"
        assert service["read_only"] is True
        assert service["user"] == "65532:65532"
        assert service["cap_drop"] == ["ALL"]
        assert service["security_opt"] == ["no-new-privileges:true"]
        assert service["pids_limit"] == 128
        serialized = str(service).lower()
        for forbidden in (
            "/workspace",
            ".env",
            ".git",
            "docker.sock",
            "/labels",
            "/effects",
            "/models",
        ):
            assert forbidden not in serialized
    assert "volumes" not in services["m5-lineage-fixture"]
    assert [item.rsplit(":", 1)[-1] for item in services["m5-lineage-runner"]["volumes"]] == [
        "ro",
        "rw",
    ]
    assert [item.split(":")[-2] for item in services["m5-lineage-auditor"]["volumes"]] == [
        "/lineage-input",
        "/lineage-output",
        "/lineage-audit",
    ]
