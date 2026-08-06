from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).parents[1]


def test_m5_image_is_minimal_pinned_and_contains_no_runtime_data() -> None:
    dockerfile = (ROOT / "Dockerfile.m5-data-gate").read_text(encoding="utf-8")
    requirements = (ROOT / "requirements.m5-data-gate.lock").read_text(
        encoding="utf-8"
    ).splitlines()

    assert dockerfile.startswith(
        "FROM python:3.11-slim@sha256:"
        "db3ff2e1800a8581e2c48a27c3995339d47bdf046da21c7627accd3d51053a93"
    )
    assert "COPY src/shaiwei/research_gates" in dockerfile
    assert "COPY src ./src" not in dockerfile
    for forbidden in ("COPY data", "COPY ledger", "COPY logs", "COPY .env", "COPY tests"):
        assert forbidden not in dockerfile
    assert "USER 65532:65532" in dockerfile
    assert all("==" in line for line in requirements if line)
    assert {line.split("==", 1)[0].lower() for line in requirements if line} == {
        "duckdb",
        "numpy",
        "pandas",
        "pyarrow",
        "python-dateutil",
        "pytz",
        "pyyaml",
        "six",
        "tzdata",
    }
    dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")
    assert "!docs/ADR_0003_M5_GLOBAL_DATA_FAILURE_EVIDENCE.md" in dockerignore
    assert (
        "!docs/M5_DYNAMIC_FUNDAMENTAL_DATA_GATE_RECOVERY_PROTOCOL_20260806.md"
        in dockerignore
    )
    assert (
        "!docs/M5_DYNAMIC_FUNDAMENTAL_DATA_GATE_REAL_RUN_ACCEPTANCE_20260805.md"
        in dockerignore
    )


def test_m5_compose_services_are_offline_short_lived_and_least_privilege() -> None:
    compose = yaml.safe_load((ROOT / "compose.m5-gates.yaml").read_text(encoding="utf-8"))
    services = compose["services"]

    assert set(services) == {"m5-fixture", "m5-runner", "m5-auditor", "m5-registry"}
    for service in services.values():
        assert service["profiles"]
        assert service["network_mode"] == "none"
        assert service["read_only"] is True
        assert service["user"] == "65532:65532"
        assert service["cap_drop"] == ["ALL"]
        assert service["security_opt"] == ["no-new-privileges:true"]
        assert service["pids_limit"] == 128
        assert service["init"] is True
        serialized = str(service).lower()
        for forbidden in ("/workspace", ".env", ".git", "docker.sock", "label", "effect", "model"):
            assert forbidden not in serialized

    assert "volumes" not in services["m5-fixture"]
    assert services["m5-runner"]["cpus"] == 1.0
    assert services["m5-runner"]["mem_limit"] == "2g"
    assert services["m5-auditor"]["cpus"] == 0.5
    assert services["m5-auditor"]["mem_limit"] == "512m"
    assert services["m5-registry"]["cpus"] == 0.5
    assert services["m5-registry"]["mem_limit"] == "512m"
    assert "m5_dynamic_fundamental_data_gate_build_v2.yaml" in str(
        services["m5-runner"]["command"]
    )
    assert "m5_dynamic_fundamental_data_gate_build_v2.yaml" in str(
        services["m5-auditor"]["command"]
    )


def test_m5_compose_mounts_are_narrow_and_directional() -> None:
    compose = yaml.safe_load((ROOT / "compose.m5-gates.yaml").read_text(encoding="utf-8"))
    services = compose["services"]

    runner = services["m5-runner"]["volumes"]
    auditor = services["m5-auditor"]["volumes"]
    registry = services["m5-registry"]["volumes"]
    assert [item.rsplit(":", 1)[-1] for item in runner] == ["ro", "rw"]
    assert [item.rsplit(":", 1)[-1] for item in auditor] == ["ro", "ro", "rw"]
    assert [item.rsplit(":", 1)[-1] for item in registry] == ["rw"]
    assert [item.split(":")[-2] for item in runner] == ["/inputs", "/outputs"]
    assert [item.split(":")[-2] for item in auditor] == ["/inputs", "/outputs", "/audit"]
    assert [item.split(":")[-2] for item in registry] == ["/registry"]
