"""Narrow live provider loaders used only after exact scope approval."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

import requests

from shaiwei.research_gates.m7_moneyflow_recovery.claims import RetryableTransportError
from shaiwei.research_gates.m7_moneyflow_recovery.contract import RecoveryError


TRANSPORT_ERRORS = (requests.RequestException, TimeoutError, ConnectionError, OSError)


class _RetryingClient:
    def __init__(self, raw: Any) -> None:
        self.raw = raw

    def query(self, api_name: str, **kwargs: object) -> Any:
        try:
            return self.raw.query(api_name, **kwargs)
        except TRANSPORT_ERRORS as error:
            raise RetryableTransportError("recovery Tushare transport failed") from error


class _RetryingBaostock:
    def __init__(self, raw: Any) -> None:
        self.raw = raw

    def query_history_k_data_plus(self, **kwargs: str) -> Any:
        try:
            return self.raw.query_history_k_data_plus(**kwargs)
        except TRANSPORT_ERRORS as error:
            raise RetryableTransportError("recovery Baostock transport failed") from error


def load_tushare_client(secret_file: Path) -> _RetryingClient:
    if secret_file.is_symlink() or not secret_file.is_file():
        raise RecoveryError("recovery Tushare secret file is missing or unsafe")
    token = secret_file.read_text(encoding="utf-8").strip()
    if len(token) < 16 or any(character.isspace() for character in token):
        raise RecoveryError("recovery Tushare secret shape differs")
    try:
        import tushare as ts
    except ImportError as error:
        raise RecoveryError("recovery Tushare client dependency is missing") from error
    return _RetryingClient(ts.pro_api(token))


@contextmanager
def baostock_session() -> Iterator[_RetryingBaostock]:
    try:
        import baostock as bs
    except ImportError as error:
        raise RecoveryError("recovery Baostock client dependency is missing") from error
    try:
        login = bs.login()
    except TRANSPORT_ERRORS as error:
        raise RetryableTransportError("recovery Baostock login transport failed") from error
    if str(login.error_code) != "0":
        raise RecoveryError("recovery Baostock login failed semantically")
    try:
        yield _RetryingBaostock(bs)
    finally:
        bs.logout()
