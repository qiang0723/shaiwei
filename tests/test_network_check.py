import json

import pandas as pd
from pydantic import SecretStr

from shaiwei import network_check


class FakeClient:
    def query(self, api_name, **kwargs):
        assert api_name == "trade_cal"
        assert kwargs["exchange"] == "SSE"
        assert "fields" in kwargs
        return pd.DataFrame({"cal_date": ["20260716"]})


def test_network_check_reports_success_without_secret(monkeypatch, capsys):
    settings = network_check.load()
    settings.runtime.tushare_token = SecretStr("private-token")
    monkeypatch.setattr(network_check, "load", lambda: settings)
    monkeypatch.setattr(network_check, "create_client", lambda token: FakeClient())
    monkeypatch.setenv("NO_PROXY", "api.waditu.com")

    assert network_check.main() == 0
    output = capsys.readouterr().out
    result = json.loads(output)
    assert result["ok"] is True
    assert result["row_count"] == 1
    assert result["proxy"]["tushare_no_proxy"] is True
    assert "private-token" not in output


def test_network_check_redacts_secret_from_provider_error(monkeypatch, capsys):
    class BrokenClient:
        def query(self, *_args, **_kwargs):
            raise RuntimeError("request rejected for private-token")

    settings = network_check.load()
    settings.runtime.tushare_token = SecretStr("private-token")
    monkeypatch.setattr(network_check, "load", lambda: settings)
    monkeypatch.setattr(network_check, "create_client", lambda token: BrokenClient())

    assert network_check.main() == 1
    output = capsys.readouterr().out
    assert "private-token" not in output
    assert "[REDACTED]" in output


def test_network_check_rejects_empty_calendar_response(monkeypatch, capsys):
    class EmptyClient:
        def query(self, *_args, **_kwargs):
            return pd.DataFrame()

    settings = network_check.load()
    settings.runtime.tushare_token = SecretStr("private-token")
    monkeypatch.setattr(network_check, "load", lambda: settings)
    monkeypatch.setattr(network_check, "create_client", lambda token: EmptyClient())

    assert network_check.main() == 1
    output = capsys.readouterr().out
    result = json.loads(output)
    assert result["ok"] is False
    assert result["error"] == "empty_response"
    assert result["row_count"] == 0
    assert "private-token" not in output
