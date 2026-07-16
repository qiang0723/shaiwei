import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from shaiwei.config import load
from shaiwei.pipeline.scheduler import healthcheck, write_health


def test_scheduler_health_is_fresh_and_rejects_degraded(tmp_path: Path):
    path = tmp_path / "health.json"
    settings = load()
    write_health("noop", path=path)
    assert healthcheck(settings, path=path)

    payload = json.loads(path.read_text())
    payload["status"] = "degraded"
    path.write_text(json.dumps(payload))
    assert not healthcheck(settings, path=path)


def test_scheduler_health_rejects_stale_file(tmp_path: Path):
    path = tmp_path / "health.json"
    settings = load()
    path.write_text(
        json.dumps(
            {
                "status": "noop",
                "updated_at": (
                    datetime.now(timezone.utc)
                    - timedelta(seconds=settings.daily.health_stale_seconds + 1)
                ).isoformat(),
            }
        )
    )
    assert not healthcheck(settings, path=path)
