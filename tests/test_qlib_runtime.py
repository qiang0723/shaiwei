from shaiwei.backtest.qlib_runtime import initialize_qlib
from shaiwei.config import PROJECT_ROOT, load


def test_qlib_runtime_keeps_recorder_under_ignored_logs(monkeypatch):
    captured = {}

    def fake_init(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr("shaiwei.backtest.qlib_runtime.qlib.init", fake_init)
    settings = load()
    initialize_qlib(settings)

    manager = captured["exp_manager"]
    assert manager["kwargs"]["uri"] == f"sqlite:///{(PROJECT_ROOT / 'logs/mlflow.db').resolve()}"
    assert captured["provider_uri"] == str(settings.runtime.data_root / "qlib_bin")
