from pathlib import Path

import yaml

from shaiwei.provenance import CONTROLLED_FILES
from shaiwei.research.rf_0c.contract import PROTOCOL_SHA256, RFCScope


ROOT = Path(__file__).parents[1]
COMPOSE = ROOT / "compose.ts-rf-0c.yaml"


def test_protocol_single_caliber_change_and_unchanged_gates() -> None:
    scope = RFCScope.load()
    assert scope.sha256 == PROTOCOL_SHA256
    caliber = scope.document["caliber_change_vs_rf_0b"]
    assert caliber["single_change"] == "supplementary_suspension_evidence_layer"
    assert caliber["gate_thresholds_unchanged_from_rf_0b"] is True
    assert caliber["no_other_semantics_change"] is True
    gate = scope.document["field_quality_gate"]
    assert gate["open_coverage_minimum_of_member_days"] == 0.99
    assert gate["unclassified_missing_field_rows_maximum"] == 0
    assert scope.document["identity_registry"]["must_equal_sealed_rf_0b_registry"] is True
    assert scope.document["production_authorization"] == "none"


def test_docker_boundary_is_offline_read_only_and_secret_free() -> None:
    document = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))
    serialized = COMPOSE.read_text(encoding="utf-8")
    assert ".env" not in serialized and "docker.sock" not in serialized
    for service in document["services"].values():
        assert service["network_mode"] == "none"
        assert service["read_only"] is True
        assert service["restart"] == "no"
        assert service["cap_drop"] == ["ALL"]
    fixture = document["services"]["rf-0c-fixture"]
    assert fixture["build"]["network"] == "none"
    for name in ("rf-0c-profile", "rf-0c-auditor"):
        writable = [row for row in document["services"][name]["volumes"] if row["read_only"] is False]
        assert len(writable) == 1
        assert writable[0]["source"].endswith("rf-0c-field-identity-preflight-v1")
    assert "Dockerfile.ts-rf-0c" in CONTROLLED_FILES
    assert COMPOSE.name in CONTROLLED_FILES


def test_rf_0c_package_respects_module_size_and_no_generic_dumping_ground() -> None:
    package = ROOT / "src/shaiwei/research/rf_0c"
    sizes = {path.name: len(path.read_text(encoding="utf-8").splitlines()) for path in package.glob("*.py")}
    assert sizes and max(sizes.values()) <= 400
    assert not ({"utils.py", "helpers.py", "common.py"} & set(sizes))
