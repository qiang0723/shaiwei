from pathlib import Path

import pytest

from shaiwei import daily_early_release_guard as base
from shaiwei import r2d_release_guard as guard


def test_explicit_r2d_protocol_path_stays_in_config(monkeypatch, tmp_path: Path) -> None:
    config = tmp_path / "config"
    config.mkdir()
    protocol = config / "r2d_future.yaml"
    protocol.write_text("schema: fixture\n", encoding="utf-8")
    monkeypatch.setattr(guard, "PROJECT_ROOT", tmp_path)

    assert guard._resolve_protocol_path("v1", Path("config/r2d_future.yaml")) == protocol


@pytest.mark.parametrize("name", ("other.yaml", "r2d_future.json"))
def test_explicit_r2d_protocol_rejects_wrong_name(monkeypatch, tmp_path: Path, name: str) -> None:
    config = tmp_path / "config"
    config.mkdir()
    candidate = config / name
    candidate.write_text("schema: fixture\n", encoding="utf-8")
    monkeypatch.setattr(guard, "PROJECT_ROOT", tmp_path)

    with pytest.raises(base.GuardError, match="controlled config boundary"):
        guard._resolve_protocol_path("v1", candidate)


def test_explicit_r2d_protocol_rejects_alias_or_symlink(monkeypatch, tmp_path: Path) -> None:
    config = tmp_path / "config"
    config.mkdir()
    target = config / "r2d_target.yaml"
    target.write_text("schema: fixture\n", encoding="utf-8")
    link = config / "r2d_link.yaml"
    link.symlink_to(target)
    monkeypatch.setattr(guard, "PROJECT_ROOT", tmp_path)

    with pytest.raises(base.GuardError, match="legacy version alias"):
        guard._resolve_protocol_path("r2", target)
    with pytest.raises(base.GuardError, match="controlled config boundary"):
        guard._resolve_protocol_path("v1", link)
