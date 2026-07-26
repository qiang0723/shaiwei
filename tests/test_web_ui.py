from pathlib import Path
import re

from fastapi.testclient import TestClient
import yaml

from shaiwei.web.ui import _allowed_api_path, _allowed_ui_path, create_app


def _static_fixture(root: Path) -> Path:
    dist = root / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text(
        '<!doctype html><html lang="zh-CN"><head>'
        '<meta name="csp-nonce" content="__P3_STYLE_NONCE__"></head>'
        '<body><div id="root"></div></body></html>',
        encoding="utf-8",
    )
    (dist / "assets/app-a1b2c3.js").write_text("export {};\n", encoding="utf-8")
    (dist / "assets/app-a1b2c3.css").write_text("body{margin:0}\n", encoding="utf-8")
    return dist


def test_ui_serves_only_frozen_routes_and_hashed_assets(tmp_path: Path) -> None:
    client = TestClient(create_app(static_root=_static_fixture(tmp_path)))
    factor_id = "a" * 64
    for route in (
        "/", "/overview", "/paper", "/signals", "/data-quality", "/system-runs",
        "/factors", "/factors/compare", f"/factors/{factor_id}",
        f"/factors/{factor_id}/admissions", "/experiments",
        "/experiments/research_experiment/a1b2c3d4e5f6",
    ):
        response = client.get(route)
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        assert '<div id="root">' in response.text

    asset = client.get("/assets/app-a1b2c3.js")
    assert asset.status_code == 200
    assert asset.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert asset.headers["content-type"].startswith("text/javascript")

    assert client.get("/factor").status_code == 404
    assert client.get("/assets/subdir/app.js").status_code == 404
    assert client.get("/docs").status_code == 404


def test_ui_security_headers_and_read_only_boundary(tmp_path: Path) -> None:
    client = TestClient(create_app(static_root=_static_fixture(tmp_path)))
    response = client.get("/overview")
    csp = response.headers["content-security-policy"]
    nonce_match = re.search(r"'nonce-([A-Za-z0-9_-]+)'", csp)
    assert nonce_match is not None
    assert f'content="{nonce_match.group(1)}"' in response.text
    assert "script-src 'self'" in csp
    assert "style-src 'self' 'nonce-" in csp
    assert "unsafe-inline" not in csp
    assert "unsafe-eval" not in csp
    assert "frame-ancestors 'none'" in csp
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["permissions-policy"].startswith("camera=()")

    second = client.get("/overview")
    assert second.headers["content-security-policy"] != csp
    assert "__P3_STYLE_NONCE__" not in response.text
    assert "__P3_STYLE_NONCE__" not in second.text

    rejected = client.post("/overview")
    assert rejected.status_code == 405
    assert rejected.text == "GET/HEAD only"


def test_ui_health_fails_closed_when_build_is_missing(tmp_path: Path) -> None:
    client = TestClient(create_app(static_root=tmp_path / "missing"))
    response = client.get("/healthz")
    assert response.status_code == 503
    assert response.json() == {
        "status": "FAIL",
        "service": "web-ui",
        "static_ready": False,
    }
    assert client.get("/overview").status_code == 404


def test_p3_ui_machine_protocol_matches_runtime_boundary() -> None:
    config = yaml.safe_load(Path("config/p3_web_ui_v1.yaml").read_text(encoding="utf-8"))
    assert config["protocol_id"] == "p3-web-ui-v1"
    assert config["routes"] == ["/overview", "/paper", "/signals"]
    assert config["security"]["inline_script"] is False
    assert config["security"]["inline_style"] is False
    assert config["security"]["unsafe_eval"] is False
    assert config["security"]["ui_host_bind"] == "127.0.0.1"
    assert config["performance"]["initial_gzip_bytes_max"] == 614400

    operations = yaml.safe_load(
        Path("config/p3_web_operations_ui_v1.yaml").read_text(encoding="utf-8")
    )
    assert operations["protocol_id"] == "p3-web-operations-ui-v1"
    assert operations["routes"] == ["/data-quality", "/system-runs"]
    assert operations["status_rules"]["data_pass_does_not_override_evidence_warn"] is True
    assert operations["status_rules"]["core_status_separate_from_notification_status"] is True
    assert operations["security"]["ui_host_bind"] == "127.0.0.1"

    factors = yaml.safe_load(
        Path("config/p3_factor_factory_ui_v1.yaml").read_text(encoding="utf-8")
    )
    assert factors["protocol_id"] == "p3-factor-factory-ui-v1"
    assert factors["status"] == "FROZEN_BEFORE_IMPLEMENTATION"
    assert factors["page_contract"]["formal_library_empty_is_primary_fact"] is True
    assert factors["page_contract"]["historical_as_of_compare_enabled"] is False
    assert factors["comparison"]["sorted_by_performance"] is False
    assert factors["navigation"]["mobile_primary_routes"] == [
        "/overview", "/factors", "/paper"
    ]


def test_operations_proxy_paths_are_exact_and_notification_ids_are_bounded() -> None:
    assert _allowed_api_path("/api/v1/data-quality")
    assert _allowed_api_path("/api/v1/system/runs")
    assert _allowed_api_path("/api/v1/notifications/ce3bfbf96e9ec474")
    assert not _allowed_api_path("/api/v1/notifications")
    assert not _allowed_api_path("/api/v1/notifications/CE3BFBF96E9EC474")
    assert not _allowed_api_path("/api/v1/notifications/ce3bfbf96e9ec474/extra")
    assert not _allowed_api_path("/api/v1/notifications/../../.env")


def test_factor_ui_and_proxy_paths_are_exact_and_bounded() -> None:
    factor_id = "a" * 64
    assert _allowed_ui_path("/factors")
    assert _allowed_ui_path("/factors/compare")
    assert _allowed_ui_path(f"/factors/{factor_id}")
    assert _allowed_ui_path(f"/factors/{factor_id}/admissions")
    assert not _allowed_ui_path("/factors/not-a-factor")
    assert not _allowed_ui_path(f"/factors/{factor_id}/extra")

    assert _allowed_api_path("/api/v1/factors")
    assert _allowed_api_path("/api/v1/factors/compare")
    assert _allowed_api_path(f"/api/v1/factors/{factor_id}")
    assert _allowed_api_path(f"/api/v1/factors/{factor_id}/admissions")
    assert not _allowed_api_path("/api/v1/factors/not-a-factor")
    assert not _allowed_api_path(f"/api/v1/factors/{factor_id}/extra")


def test_experiment_ui_and_proxy_paths_are_exact_and_bounded() -> None:
    detail = "/experiments/research_experiment/a1b2c3d4e5f6"
    api_detail = f"/api/v1{detail}"
    assert _allowed_ui_path("/experiments")
    assert _allowed_ui_path(detail)
    assert _allowed_api_path("/api/v1/experiments")
    assert _allowed_api_path(api_detail)
    assert _allowed_ui_path("/experiments/p2_effect_correction/run-20260725")
    assert not _allowed_ui_path("/experiments/unknown/a1b2c3d4e5f6")
    assert not _allowed_ui_path("/experiments/research_experiment/a/b")
    assert not _allowed_ui_path("/experiments/research_experiment/%2e%2e")
    assert not _allowed_api_path("/api/v1/experiments/research_experiment")
    assert not _allowed_api_path(f"{api_detail}/extra")
    assert not _allowed_api_path("/api/v1/experiments/../../.env")


def test_experiment_ui_machine_protocol_is_frozen_and_narrow() -> None:
    config = yaml.safe_load(
        Path("config/p3_experiment_ui_v1.yaml").read_text(encoding="utf-8")
    )
    assert config["protocol_id"] == "p3-experiment-ui-v1"
    assert config["status"] == "FROZEN_BEFORE_IMPLEMENTATION"
    assert config["structural_baseline"]["projected_total_count"] == 783
    assert config["page_contract"]["performance_sort_or_filter"] is False
    assert config["page_contract"]["client_outcome_inference"] is False
    assert config["detail"]["outcome_from_backend"] is True
    assert config["detail"]["daily_nav_chart"] is False
    assert config["security"]["ui_host_bind"] == "127.0.0.1"
