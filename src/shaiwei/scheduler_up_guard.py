"""`make docker-scheduler-up` 前置守卫：只放行与运行容器（或最后一次 START_PASS）一致的 current 镜像。

背景：compose.yaml 以可变别名 `shaiwei:scheduler-current` 引用生产镜像。R2D Phase A 把别名提升到了
从未运行的候选，此时任何 `docker compose up` 都会在没有 readiness、时间窗、scope、审批和审计的情况下
用候选替换生产。本守卫是只读前置检查，不改标签、不改容器；拒绝即退出码 2。
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Callable

from shaiwei.config import PROJECT_ROOT
from shaiwei.release import AUDIT_PATH, CURRENT_ALIAS

Query = Callable[[list[str]], str]


def compose_project() -> str:
    """Compose 默认项目名取目录名小写；与 compose.yaml 不带 -p 的调用一致。"""
    return PROJECT_ROOT.name.lower()


def docker_query(args: list[str]) -> str:
    result = subprocess.run(
        ["docker", *args], check=True, capture_output=True, text=True, timeout=30
    )
    return result.stdout.strip()


def tag_image_id(docker: Query, tag: str) -> str | None:
    try:
        return docker(["image", "inspect", "--format", "{{.Id}}", tag]) or None
    except (subprocess.SubprocessError, OSError):
        return None


def scheduler_container_images(docker: Query, project: str) -> list[str]:
    ids = docker(
        [
            "ps",
            "-a",
            "--filter",
            f"label=com.docker.compose.project={project}",
            "--filter",
            "label=com.docker.compose.service=scheduler",
            "--format",
            "{{.ID}}",
        ]
    )
    return [docker(["inspect", "--format", "{{.Image}}", cid]) for cid in ids.split()]


def last_started_image_id(audit_path: Path) -> str | None:
    if not audit_path.is_file():
        return None
    last: str | None = None
    for line in audit_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if record.get("event") == "START_PASS":
            last = str(record.get("details", {}).get("image_id") or "") or last
    return last


def decide(
    *, tag_image: str | None, container_images: list[str], last_started: str | None
) -> dict[str, object]:
    short = lambda value: (value or "")[:19]  # noqa: E731
    base = {
        "current_alias": CURRENT_ALIAS,
        "current_image_id": short(tag_image),
        "container_image_ids": [short(value) for value in container_images],
        "last_start_pass_image_id": short(last_started),
    }
    if tag_image is None:
        return {**base, "decision": "REFUSE", "reason": "current alias does not resolve to an image"}
    if container_images:
        if all(value == tag_image for value in container_images):
            return {**base, "decision": "ALLOW", "reason": "current alias equals the existing scheduler container image"}
        return {
            **base,
            "decision": "REFUSE",
            "reason": "current alias points to a different image than the existing scheduler container; "
            "compose up would replace production outside the authorized release path",
        }
    if last_started is not None and tag_image == last_started:
        return {**base, "decision": "ALLOW", "reason": "no scheduler container; current alias equals the last START_PASS image"}
    return {
        **base,
        "decision": "REFUSE",
        "reason": "no scheduler container and the current alias was never started via START_PASS",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default=compose_project())
    parser.add_argument("--audit", type=Path, default=AUDIT_PATH)
    args = parser.parse_args(argv)
    try:
        containers = scheduler_container_images(docker_query, args.project)
    except (subprocess.SubprocessError, OSError) as error:
        print(json.dumps({"decision": "REFUSE", "reason": f"docker unavailable: {type(error).__name__}"}))
        return 2
    verdict = decide(
        tag_image=tag_image_id(docker_query, CURRENT_ALIAS),
        container_images=containers,
        last_started=last_started_image_id(args.audit),
    )
    print(json.dumps(verdict, ensure_ascii=False, sort_keys=True))
    return 0 if verdict["decision"] == "ALLOW" else 2


if __name__ == "__main__":
    raise SystemExit(main())
