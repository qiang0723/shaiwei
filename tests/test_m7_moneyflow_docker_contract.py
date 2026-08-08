from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_m7_dockerfile_has_narrow_context_and_unprivileged_user() -> None:
    text = (ROOT / "Dockerfile.m7-moneyflow-data-gate").read_text(encoding="utf-8")
    assert "COPY src/shaiwei/research_gates/m7_moneyflow" in text
    assert "COPY src/shaiwei/research_gates ./" not in text
    assert "COPY . " not in text
    assert ".env" not in text
    assert "USER 65532:65532" in text
    assert "python:3.11-slim@sha256:" in text


def test_m7_compose_is_networkless_read_only_and_narrowly_mounted() -> None:
    document = yaml.safe_load(
        (ROOT / "compose.m7-moneyflow-gate.yaml").read_text(encoding="utf-8")
    )
    common = document["x-m7-common"]
    assert common["network_mode"] == "none"
    assert common["read_only"] is True
    assert common["user"] == "65532:65532"
    assert common["cap_drop"] == ["ALL"]
    assert common["security_opt"] == ["no-new-privileges:true"]
    assert common["pids_limit"] == 128
    services = document["services"]
    assert set(services) == {
        "m7-moneyflow-fixture",
        "m7-moneyflow-runner",
        "m7-moneyflow-auditor",
    }
    serialized = (ROOT / "compose.m7-moneyflow-gate.yaml").read_text(encoding="utf-8")
    assert "/workspace" not in serialized
    assert ".env" not in serialized
    assert "docker.sock" not in serialized
    assert "scheduler" not in serialized
    assert ":/inputs:ro" in serialized
    assert ":/outputs:ro" in serialized


def test_all_new_m7_modules_stay_below_frozen_size_limit() -> None:
    package = ROOT / "src/shaiwei/research_gates/m7_moneyflow"
    counts = {
        path.name: len(path.read_text(encoding="utf-8").splitlines())
        for path in package.glob("*.py")
    }
    assert counts
    assert max(counts.values()) <= 400
