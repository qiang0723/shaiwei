from pathlib import Path
import re

from fastapi.testclient import TestClient
import yaml

from shaiwei.web.ui import create_app


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
    for route in ("/", "/overview", "/paper", "/signals"):
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
