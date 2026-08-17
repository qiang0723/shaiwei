"""Select original or recovery effect authority without circular dependencies."""

from __future__ import annotations

from pathlib import Path

from shaiwei.research.trend_swing.r3g2.contract import EffectProtocol, R3G2Error, sha256_file
from shaiwei.research.trend_swing.r3g2.effect_control import (
    EffectApproval,
    EffectReleaseScope,
    _mapping,
)
from shaiwei.research.trend_swing.r3g2.effect_recovery_control import (
    RECOVERY_SCOPE_SCHEMA,
    expected_recovery_approval,
    load_recovery_release,
)


def load_effect_authority(
    release_path: Path, approval_path: Path, protocol: EffectProtocol
) -> tuple[EffectReleaseScope, EffectApproval]:
    release_document = _mapping(release_path)
    if release_document.get("schema_version") == RECOVERY_SCOPE_SCHEMA:
        release = load_recovery_release(release_path, protocol, EffectReleaseScope)
        approval_document = _mapping(approval_path)
        if approval_document != expected_recovery_approval(release.sha256):
            raise R3G2Error("R3G-2 explicit approval differs from the exact release scope")
        approval = EffectApproval(approval_document, sha256_file(approval_path))
        return release, approval
    release = EffectReleaseScope.load(release_path, protocol)
    return release, EffectApproval.load(approval_path, release)
