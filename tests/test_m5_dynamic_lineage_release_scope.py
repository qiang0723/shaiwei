from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).parents[1]
RELEASE_PATH = ROOT / "config/m5_dynamic_fundamental_source_lineage_release_scope_v1.json"


def _sha256(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def test_lineage_release_scope_is_canonical_content_addressed_and_unapproved() -> None:
    serialized = RELEASE_PATH.read_text(encoding="utf-8")
    document = json.loads(serialized)
    scope = document["scope"]

    assert (
        serialized
        == json.dumps(
            document,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    )
    assert document["schema_version"] == "m5-source-lineage-release-scope-v1"
    assert document["release_scope_sha256"] == _sha256(scope)
    assert document["release_scope_sha256"] == (
        "b01058b55ff3dd6c06cf0722541214ecbb793de92a3115410c073daab26cf155"
    )
    assert scope["protocol_scope_sha256"] == (
        "96c4f996f2641e6b18c26d8228ee72712b2670d70fe0cdedf95c99cd2e463ccd"
    )
    assert scope["case_id"] == ("6b6c849f4ded89f631e1af8127f0e7321898aa7f4ce0c2630806fc8c8ef7be16")
    assert scope["input_manifest_sha256"] == (
        "b9b7c7fb4b4f87ee931cbbc202134d7faf8bc4c891fe252267f3e777b6bfe5d7"
    )
    assert scope["implementation"]["git_commit"] == ("f2e5483f55278010cde4ea5ff5f8e3b56c09ae37")
    assert scope["implementation"]["origin_main_commit"] == scope["implementation"]["git_commit"]
    assert scope["image"]["image_id"] == (
        "sha256:fe9101f11a54d0b2111c0000ffff5a21d7d72fd86f4300aa30ae7b934119b606"
    )


def test_lineage_release_grants_no_execution_data_or_production_authority() -> None:
    scope = json.loads(RELEASE_PATH.read_text(encoding="utf-8"))["scope"]
    authority = scope["authority"]

    assert authority["lineage_release_ready"] is True
    assert authority["lineage_approval_recorded"] is False
    assert authority["lineage_execution_authorized"] is False
    assert authority["formal_registry_write_authorized"] is False
    assert authority["real_data_read_authorized"] is False
    assert authority["real_conflict_diagnosis_authorized"] is False
    assert authority["external_call_authorized"] is False
    assert authority["credential_read_authorized"] is False
    assert authority["pit_compute_authorized"] is False
    assert authority["candidate_compute_authorized"] is False
    assert authority["label_read_authorized"] is False
    assert authority["effect_read_authorized"] is False
    assert authority["model_training_authorized"] is False
    assert authority["backtest_authorized"] is False
    assert authority["production_authorization"] == "none"
