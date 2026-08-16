from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from shaiwei.provenance import CONTROLLED_FILES
from shaiwei.research.trend_swing.r3g2.contract import EffectProtocol, R3G2Error
from shaiwei.research.trend_swing.r3g2.w7_control import load_release_protocol
from shaiwei.research.trend_swing.r3g2.w7_release import build_release_document


ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ROOT / "compose.ts-v5-r3g2-w7.yaml"
DOCKERFILE = ROOT / "Dockerfile"


def test_release_protocol_has_no_real_authority_before_exact_approval() -> None:
    protocol = EffectProtocol.load()
    release, digest = load_release_protocol(protocol)
    authority = release["authority_before_explicit_approval"]

    assert len(digest) == 64
    assert release["status"] == "RESULT_BLIND_W7_LINEAGE_RELEASE_PREPARATION_ONLY"
    assert authority["release_metadata_and_synthetic_fixture"] is True
    assert {
        key for key, value in authority.items() if isinstance(value, bool) and value
    } == {"release_metadata_and_synthetic_fixture"}
    execution = release["execution_after_exact_approval"]
    assert execution["complete_internal_passes"] == ["first_pass", "replay"]
    assert execution["strategy_effect_attempt_count"] == 0
    assert execution["same_release_retry_authorized"] is False


def test_compose_is_offline_minimal_and_auditor_has_no_qlib() -> None:
    document = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))
    serialized = COMPOSE.read_text(encoding="utf-8")
    services = document["services"]

    assert "env_file" not in serialized
    assert ".env" not in serialized
    assert "docker.sock" not in serialized
    assert "ledger/" not in serialized
    for service in services.values():
        assert service["network_mode"] == "none"
        assert service["read_only"] is True
        assert service["cap_drop"] == ["ALL"]
        assert service["restart"] == "no"
    assert "volumes" not in services["ts-v5-r3g2-w7-fixture"]
    auditor_volumes = services["ts-v5-r3g2-w7-auditor"]["volumes"]
    assert all(volume["target"] != "/qlib" for volume in auditor_volumes)
    runner_targets = {
        volume["target"] for volume in services["ts-v5-r3g2-w7-runner"]["volumes"]
    }
    assert runner_targets == {"/qlib", "/inputs/release.json", "/inputs/approval.json", "/outputs"}


def test_w7_compose_is_part_of_the_controlled_image_snapshot() -> None:
    assert "compose.ts-v5-r3g2-w7.yaml" in CONTROLLED_FILES
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")
    assert "compose.ts-v5-r3g2-w7.yaml" in dockerfile


def test_release_builder_rejects_an_unpushed_implementation() -> None:
    protocol = EffectProtocol.load()
    release, digest = load_release_protocol(protocol)
    with pytest.raises(R3G2Error, match="not pushed"):
        build_release_document(
            protocol=protocol,
            release_protocol=release,
            release_protocol_sha256=digest,
            created_at="2026-08-17T00:00:00+00:00",
            implementation_git_commit="a" * 40,
            origin_main_commit="b" * 40,
            code_snapshot="c" * 64,
            image_id=f"sha256:{'d' * 64}",
            image_platform="linux/arm64",
            image_git_commit="a" * 40,
            image_release_manifest_sha256="e" * 64,
            image_release_manifest_file_count=1,
            inputs=release["frozen_provider"],
        )
