from pathlib import Path

import yaml

from shaiwei.provenance import CONTROLLED_FILES
from shaiwei.research.rf_diag.contract import PROTOCOL_SHA256, RFDScope


ROOT = Path(__file__).parents[1]
COMPOSE = ROOT / "compose.ts-rf-diag.yaml"


def test_protocol_is_lineage_only_and_never_reopens_rf() -> None:
    scope = RFDScope.load()
    assert scope.sha256 == PROTOCOL_SHA256
    objective = scope.document["objective"]
    assert objective["candidate_value_or_score_computation"] is False
    assert objective["outcome_or_return_read"] is False
    assert objective["gate_change_or_re_evaluation"] == "forbidden"
    boundary = scope.document["successor_boundary"]
    assert boundary["diagnosis_does_not_reopen_rf"] is True
    assert boundary["diagnosis_does_not_lower_the_failed_gate"] is True
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
    fixture = document["services"]["rf-diag-fixture"]
    assert fixture["build"]["network"] == "none"
    for name in ("rf-diag-runner", "rf-diag-auditor"):
        writable = [row for row in document["services"][name]["volumes"] if row["read_only"] is False]
        assert len(writable) == 1
        assert writable[0]["source"].endswith("rf-0b-gap-lineage-diagnostic-v1")
    assert "Dockerfile.ts-rf-diag" in CONTROLLED_FILES
    assert COMPOSE.name in CONTROLLED_FILES


def test_rf_diag_package_respects_module_size_and_no_generic_dumping_ground() -> None:
    package = ROOT / "src/shaiwei/research/rf_diag"
    sizes = {path.name: len(path.read_text(encoding="utf-8").splitlines()) for path in package.glob("*.py")}
    assert sizes and max(sizes.values()) <= 400
    assert not ({"utils.py", "helpers.py", "common.py"} & set(sizes))
