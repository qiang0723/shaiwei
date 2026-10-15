"""ADR 0018 冻结输入历史身份核验器。"""

import hashlib
import subprocess
from pathlib import Path

import pytest

from shaiwei.config import PROJECT_ROOT
from shaiwei.frozen_input_identity import (
    Authority,
    FrozenInputIdentityError,
    load_authority,
    verify_frozen_input,
)

COMMIT = "a" * 40
FROZEN = b"frozen content\n"
FROZEN_SHA = hashlib.sha256(FROZEN).hexdigest()


def _world(tmp_path: Path, *, live: bytes = FROZEN) -> Authority:
    (tmp_path / "config").mkdir()
    protocol = tmp_path / "config" / "protocol.yaml"
    protocol.write_text("frozen: true\n", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "input.py").write_bytes(live)
    return Authority.model_validate(
        {
            "schema_version": "closed-lane-frozen-input-authority-v1",
            "authority_id": "adr-0018-v1",
            "document": "docs/adr.md",
            "entries": [
                {
                    "protocol_path": "config/protocol.yaml",
                    "protocol_sha256": hashlib.sha256(protocol.read_bytes()).hexdigest(),
                    "freeze_commit": COMMIT,
                }
            ],
        }
    )


def _git(*, ancestor: int = 0, blob: bytes | None = FROZEN, error: Exception | None = None):
    def run(args):
        if error is not None:
            raise error
        if args[0] == "merge-base":
            assert args == ["merge-base", "--is-ancestor", COMMIT, "HEAD"]
            return subprocess.CompletedProcess(args, ancestor, b"", b"")
        assert args == ["show", f"{COMMIT}:src/input.py"]
        return subprocess.CompletedProcess(args, 0 if blob is not None else 128, blob or b"", b"")

    return run


def _verify(tmp_path: Path, authority: Authority, git, *, relative="src/input.py", protocol="config/protocol.yaml"):
    return verify_frozen_input(
        relative, FROZEN_SHA, protocol_path=protocol, root=tmp_path, git=git, authority=authority
    )


def test_live_match_needs_no_git(tmp_path: Path):
    authority = _world(tmp_path)
    assert _verify(tmp_path, authority, _git(error=AssertionError("git must not be called"))) == "LIVE"


def test_drifted_live_file_is_proven_by_freeze_commit_blob(tmp_path: Path):
    authority = _world(tmp_path, live=b"evolved\n")
    assert _verify(tmp_path, authority, _git()) == "HISTORICAL"


@pytest.mark.parametrize(
    "git, message",
    [
        (_git(blob=b"tampered\n"), "does not match the frozen hash"),
        (_git(ancestor=1), "not an ancestor"),
        (_git(blob=None), "absent at freeze commit"),
        (_git(error=FileNotFoundError("git")), "git is unavailable"),
    ],
)
def test_unprovable_drift_fails_closed(tmp_path: Path, git, message):
    authority = _world(tmp_path, live=b"evolved\n")
    with pytest.raises(FrozenInputIdentityError, match=message):
        _verify(tmp_path, authority, git)


def test_missing_entry_and_changed_protocol_fail_closed(tmp_path: Path):
    authority = _world(tmp_path, live=b"evolved\n")
    with pytest.raises(FrozenInputIdentityError, match="no unique frozen-input authority"):
        _verify(tmp_path, authority, _git(), protocol="config/other.yaml")
    (tmp_path / "config" / "protocol.yaml").write_text("frozen: false\n", encoding="utf-8")
    with pytest.raises(FrozenInputIdentityError, match="frozen protocol identity differs"):
        _verify(tmp_path, authority, _git())


@pytest.mark.parametrize("relative", ["/etc/passwd", "../outside.py", ""])
def test_path_must_be_confined(tmp_path: Path, relative):
    authority = _world(tmp_path)
    with pytest.raises(FrozenInputIdentityError, match="confined|escapes"):
        _verify(tmp_path, authority, _git(), relative=relative)


def test_real_authority_entries_match_their_frozen_protocols_and_history():
    """只读：两条真实条目的协议哈希与冻结提交中的历史输入均与冻结值一致。"""
    authority = load_authority()
    expected = {
        "config/m6_csi800_production_head30_v1.yaml": (
            "src/shaiwei/shadow/manifest.py",
            "0c5b1b7496306414695365e6b77c45a31012563bef91e592e7840bc66fc38839",
        ),
        "config/m6_csi800_model_attribution_v1.yaml": (
            "config/settings.yaml",
            "23dfbcd6be65a569de265387473cd991b4d10b0da0f4ac13f5bac32be313e242",
        ),
    }
    assert {entry.protocol_path for entry in authority.entries} == set(expected)
    for entry in authority.entries:
        protocol = PROJECT_ROOT / entry.protocol_path
        assert hashlib.sha256(protocol.read_bytes()).hexdigest() == entry.protocol_sha256
        relative, frozen_sha = expected[entry.protocol_path]
        blob = subprocess.run(
            ["git", "show", f"{entry.freeze_commit}:{relative}"],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
        ).stdout
        assert hashlib.sha256(blob).hexdigest() == frozen_sha
