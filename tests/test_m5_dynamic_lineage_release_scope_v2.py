from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).parents[1]
RELEASE_PATH = ROOT / "config/m5_dynamic_fundamental_source_lineage_release_scope_v2.json"


def _sha256(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def test_recovery_release_is_canonical_and_binds_the_pushed_fix() -> None:
    serialized = RELEASE_PATH.read_text(encoding="utf-8")
    document = json.loads(serialized)
    scope = document["scope"]

    assert serialized == json.dumps(
        document,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ) + "\n"
    assert document["schema_version"] == "m5-source-lineage-release-scope-v1"
    assert document["release_scope_sha256"] == _sha256(scope)
    assert document["release_scope_sha256"] == (
        "f7904929991e90a3d4c220cbdaf88818953694803625c41eb3634731e376e2d5"
    )
    assert scope["protocol_scope_sha256"] == (
        "0e4ea4ee6c283b9fad28e1b289f146199154a3e2f5c65d5255d2e462cacb20bc"
    )
    assert scope["case_id"] == (
        "8000c9e107c100cdb41edace547f5869dddda6807005c142ce2847d9433f49ff"
    )
    assert scope["input_manifest_sha256"] == (
        "bda3f6b86a43a13438acc78bfaf14bce772c9b4d94d221272765ba6f6735d0df"
    )
    assert scope["input_manifest_physical_sha256"] == (
        "1e4ea075065d1e5c0d58f40593aa24ce25443b8c696f7032ed04eb7aef795ebf"
    )
    assert scope["implementation"]["git_commit"] == (
        "213d0a103c9f22b327313bdc568c48eea0a9fff8"
    )
    assert scope["implementation"]["origin_main_commit"] == scope["implementation"]["git_commit"]
    assert scope["image"]["image_id"] == (
        "sha256:5dd12995e4a1dbf8aead28d91aca6a040af7da8c2251f783ff657a7a34212d1a"
    )


def test_recovery_release_grants_only_release_readiness() -> None:
    authority = json.loads(RELEASE_PATH.read_text(encoding="utf-8"))["scope"]["authority"]

    assert authority["lineage_release_ready"] is True
    assert authority["production_authorization"] == "none"
    assert all(
        item is False
        for key, item in authority.items()
        if key not in {"lineage_release_ready", "production_authorization"}
    )
