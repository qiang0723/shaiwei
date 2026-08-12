from pathlib import Path

import yaml


ROOT = Path(__file__).parents[1]


def test_recovery_compose_separates_network_profile_and_auditor():
    document = yaml.safe_load((ROOT / "compose.ts-recovery.yaml").read_text(encoding="utf-8"))
    services = document["services"]
    assert set(services) == {
        "ts-recovery-network",
        "ts-recovery-profile",
        "ts-recovery-auditor",
        "ts-r4-profile",
        "ts-r4-auditor",
    }
    network = services["ts-recovery-network"]
    assert set(network["environment"]) >= {
        "SHAIWEI_TS_R3_APPROVAL_SCOPE_SHA256", "SHAIWEI_TS_TOKEN_FILE"
    }
    assert "TUSHARE_TOKEN" not in network["environment"]
    assert network["read_only"] is True
    assert network["cap_drop"] == ["ALL"]
    for name in ("ts-recovery-profile", "ts-recovery-auditor"):
        service = services[name]
        assert service["network_mode"] == "none"
        assert service["read_only"] is True
        assert "TUSHARE_TOKEN" not in service.get("environment", {})
        assert service["cap_drop"] == ["ALL"]


def test_recovery_image_and_provenance_include_dedicated_compose():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    provenance = (ROOT / "src/shaiwei/provenance.py").read_text(encoding="utf-8")
    assert "compose.ts-recovery.yaml" in dockerfile
    assert '"compose.ts-recovery.yaml"' in provenance


def test_r4_services_are_offline_read_only_and_separate_from_scheduler():
    document = yaml.safe_load((ROOT / "compose.ts-recovery.yaml").read_text(encoding="utf-8"))
    profile = document["services"]["ts-r4-profile"]
    auditor = document["services"]["ts-r4-auditor"]

    for service in (profile, auditor):
        assert service["profiles"] == ["ts-r4-offline"]
        assert service["network_mode"] == "none"
        assert service["read_only"] is True
        assert service["restart"] == "no"
        assert service["image"] == "shaiwei:ts-v3-pullback-r4"
        assert all(".env" not in volume["source"] for volume in service["volumes"])
    assert profile["command"][-1] == "profile"
    assert auditor["command"][-1] == "audit"
