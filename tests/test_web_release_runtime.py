from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from shaiwei.build_identity.web_release_build import WebReleaseError
from shaiwei.build_identity.web_release_deploy import (
    _append_audit,
    _audit_records,
)
from shaiwei.build_identity.web_release_runtime import validate_container_contract


IMAGE_ID = f"sha256:{'a' * 64}"


def _identity(service: str) -> dict[str, object]:
    networks = {
        "web-query": {"shaiwei-web_web-internal": {}},
        "research-control": {"shaiwei-web_control-internal": {}},
        "web-ui": {
            "shaiwei-web_control-internal": {},
            "shaiwei-web_web-internal": {},
            "shaiwei-web_web-loopback": {},
        },
    }[service]
    mounts = []
    if service == "research-control":
        mounts = [
            {"Source": "/project/data/control/m5", "Destination": "/workspace/data/control/m5", "RW": True},
            {"Source": "/project/config", "Destination": "/workspace/config/v1.yaml", "RW": False},
        ]
    ports: dict[str, object]
    if service == "web-ui":
        ports = {"8080/tcp": [{"HostIp": "127.0.0.1", "HostPort": "8080"}]}
    else:
        ports = {"8000/tcp": None}
    return {
        "container_id": "b" * 64,
        "image_id": IMAGE_ID,
        "health": "healthy",
        "read_only_rootfs": True,
        "cap_drop": ["ALL"],
        "security_opt": ["no-new-privileges:true"],
        "mounts": mounts,
        "ports": ports,
        "networks": networks,
    }


@pytest.mark.parametrize("service", ["web-query", "research-control", "web-ui"])
def test_container_contract_accepts_frozen_local_read_only_boundary(service: str) -> None:
    validate_container_contract(service, _identity(service), IMAGE_ID)


@pytest.mark.parametrize(
    ("service", "mutation", "message"),
    [
        ("web-query", lambda doc: doc.update({"health": "unhealthy"}), "image or health"),
        ("web-query", lambda doc: doc.update({"read_only_rootfs": False}), "read-only"),
        ("web-query", lambda doc: doc.update({"cap_drop": []}), "capability"),
        ("web-query", lambda doc: doc.update({"security_opt": []}), "security options"),
        (
            "web-query",
            lambda doc: doc["mounts"].append(
                {"Source": "/var/run/docker.sock", "Destination": "/var/run/docker.sock", "RW": False}
            ),
            "forbidden mount",
        ),
        (
            "web-query",
            lambda doc: doc["mounts"].append(
                {"Source": "/project", "Destination": "/workspace", "RW": False}
            ),
            "forbidden mount",
        ),
        (
            "web-query",
            lambda doc: doc["mounts"].append(
                {"Source": "/project/data", "Destination": "/workspace/data", "RW": True}
            ),
            "writable mounts differ",
        ),
        ("web-query", lambda doc: doc.update({"networks": {"bridge": {}}}), "networks differ"),
        (
            "web-query",
            lambda doc: doc.update(
                {"ports": {"8000/tcp": [{"HostIp": "0.0.0.0", "HostPort": "8000"}]}}
            ),
            "exposes a host port",
        ),
        (
            "web-ui",
            lambda doc: doc.update(
                {"ports": {"8080/tcp": [{"HostIp": "0.0.0.0", "HostPort": "8080"}]}}
            ),
            "loopback port contract differs",
        ),
    ],
)
def test_container_contract_fails_closed_on_runtime_drift(service: str, mutation, message: str) -> None:
    identity = deepcopy(_identity(service))
    mutation(identity)
    with pytest.raises(WebReleaseError, match=message):
        validate_container_contract(service, identity, IMAGE_ID)


def test_release_audit_is_hash_chained_and_tamper_evident(tmp_path: Path) -> None:
    path = tmp_path / "release.jsonl"
    first = _append_audit(path, "STARTED", {"candidate": "a" * 64})
    second = _append_audit(path, "COMPLETED", {"candidate": "a" * 64})
    records = _audit_records(path)
    assert records[0]["record_sha256"] == first
    assert records[1]["previous_record_sha256"] == first
    assert records[1]["record_sha256"] == second

    document = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    document["event"] = "TAMPERED"
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text(json.dumps(document) + "\n" + lines[1] + "\n", encoding="utf-8")
    with pytest.raises(WebReleaseError, match="audit chain differs"):
        _audit_records(path)
