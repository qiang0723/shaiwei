"""Targeted runtime checks for the local read-only Web component."""

from __future__ import annotations

from pathlib import Path
import subprocess
import time
import urllib.request
from typing import Mapping

from shaiwei.build_identity.web_release_config import WebReleaseConfig, WebReleaseError


WEB_SERVICES = ("web-query", "research-control", "web-ui")
_EXPECTED_NETWORK_SUFFIXES = {
    "web-query": {"web-internal"},
    "research-control": {"control-internal"},
    "web-ui": {"control-internal", "web-internal", "web-loopback"},
}


def _run(argv: list[str], *, root: Path) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(argv, cwd=root, capture_output=True, text=True)
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()[-4000:]
        raise WebReleaseError(f"command failed: {' '.join(argv)}: {detail}")
    return result


def _container_id(root: Path, config: WebReleaseConfig, service: str) -> str:
    value = _run(
        ["docker", "compose", "-f", config.compose_path, "--profile", "web", "ps", "-q", service],
        root=root,
    ).stdout.strip()
    if not value:
        raise WebReleaseError(f"Web service container is not running: {service}")
    return value


def container_identity(root: Path, config: WebReleaseConfig, service: str) -> dict[str, object]:
    """Read only the non-secret container fields required by the release contract."""
    container_id = _container_id(root, config, service)
    fields = [
        "{{.Id}}",
        "{{.Image}}",
        "{{.State.Health.Status}}",
        "{{.HostConfig.ReadonlyRootfs}}",
        "{{json .HostConfig.CapDrop}}",
        "{{json .HostConfig.SecurityOpt}}",
        "{{json .Mounts}}",
        "{{json .NetworkSettings.Ports}}",
        "{{json .NetworkSettings.Networks}}",
    ]
    output = _run(
        ["docker", "container", "inspect", "--format", "\n".join(fields), container_id],
        root=root,
    ).stdout.splitlines()
    if len(output) != len(fields):
        raise WebReleaseError(f"Web container identity is incomplete: {service}")
    import json

    return {
        "container_id": output[0],
        "image_id": output[1],
        "health": output[2],
        "read_only_rootfs": output[3] == "true",
        "cap_drop": json.loads(output[4]),
        "security_opt": json.loads(output[5]),
        "mounts": json.loads(output[6]),
        "ports": json.loads(output[7]),
        "networks": json.loads(output[8]),
    }


def _network_suffix(name: str) -> str:
    for suffix in ("web-internal", "web-loopback", "control-internal"):
        if name == suffix or name.endswith(f"_{suffix}"):
            return suffix
    return name


def validate_container_contract(
    service: str,
    identity: Mapping[str, object],
    expected_image_id: str,
) -> None:
    """Fail closed on image, health, privilege, mount, network, or port drift."""
    if service not in WEB_SERVICES:
        raise WebReleaseError(f"unknown Web service: {service}")
    if identity.get("image_id") != expected_image_id or identity.get("health") != "healthy":
        raise WebReleaseError(f"Web container image or health differs: {service}")
    cap_drop = identity.get("cap_drop")
    if identity.get("read_only_rootfs") is not True or not isinstance(cap_drop, list) or "ALL" not in cap_drop:
        raise WebReleaseError(f"Web container read-only or capability contract differs: {service}")
    security_opt = identity.get("security_opt")
    if not isinstance(security_opt, list) or "no-new-privileges:true" not in security_opt:
        raise WebReleaseError(f"Web container security options differ: {service}")
    mounts = identity.get("mounts")
    if not isinstance(mounts, list) or any(not isinstance(mount, dict) for mount in mounts):
        raise WebReleaseError(f"Web container mounts are invalid: {service}")
    if any(
        mount.get("Destination") == "/workspace"
        or "docker.sock" in str(mount.get("Source", ""))
        or "docker.sock" in str(mount.get("Destination", ""))
        for mount in mounts
    ):
        raise WebReleaseError(f"Web container has a forbidden mount: {service}")
    writable = {str(mount.get("Destination")) for mount in mounts if mount.get("RW") is True}
    expected_writable = {"/workspace/data/control/m5"} if service == "research-control" else set()
    if writable != expected_writable:
        raise WebReleaseError(f"Web container writable mounts differ: {service}")
    networks = identity.get("networks")
    if not isinstance(networks, dict):
        raise WebReleaseError(f"Web container networks are invalid: {service}")
    suffixes = {_network_suffix(name) for name in networks}
    if suffixes != _EXPECTED_NETWORK_SUFFIXES[service]:
        raise WebReleaseError(f"Web container networks differ: {service}")
    ports = identity.get("ports")
    if not isinstance(ports, dict):
        raise WebReleaseError(f"Web container ports are invalid: {service}")
    published = [binding for bindings in ports.values() if bindings for binding in bindings]
    if service == "web-ui":
        if published != [{"HostIp": "127.0.0.1", "HostPort": "8080"}]:
            raise WebReleaseError("Web UI loopback port contract differs")
    elif published:
        raise WebReleaseError(f"Web internal service exposes a host port: {service}")


def wait_and_verify_runtime(
    root: Path,
    config: WebReleaseConfig,
    expected_image_ids: Mapping[str, str],
    *,
    timeout_seconds: int = 90,
) -> dict[str, dict[str, object]]:
    deadline = time.monotonic() + timeout_seconds
    last_error = ""
    while time.monotonic() < deadline:
        try:
            identities = {
                service: container_identity(root, config, service) for service in WEB_SERVICES
            }
            for service, identity in identities.items():
                validate_container_contract(service, identity, expected_image_ids[service])
            return identities
        except WebReleaseError as error:
            last_error = str(error)
            time.sleep(2)
    raise WebReleaseError(f"Web release runtime contract did not become healthy: {last_error}")


def verify_read_only_http(config: WebReleaseConfig) -> None:
    for path in ("/healthz", "/api/v1/overview"):
        with urllib.request.urlopen(f"{config.ui_base_url}{path}", timeout=10) as response:
            if response.status != 200:
                raise WebReleaseError(f"Web read-only endpoint failed: {path}")
    with urllib.request.urlopen(f"{config.ui_base_url}/", timeout=10) as response:
        csp = response.headers.get("Content-Security-Policy", "")
        if response.status != 200 or "default-src 'self'" not in csp:
            raise WebReleaseError("Web UI root or CSP contract differs")
