from __future__ import annotations

import os
from typing import Any

import pytest
import requests

from practicepanther_mcp import credentials


class DummyResponse:
    def __init__(
        self,
        status_code: int = 200,
        json_data: Any | None = None,
        text: str = "",
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self._json_data = json_data
        self.text = text if text else ("" if json_data is None else str(json_data))
        self.headers = headers or {}

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 400

    def json(self) -> Any:
        if isinstance(self._json_data, BaseException):
            raise self._json_data
        return self._json_data


@pytest.fixture(autouse=True)
def block_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def blocked(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("Unexpected network call in test")

    monkeypatch.setattr(requests.sessions.Session, "request", blocked)
    monkeypatch.setattr(requests, "post", blocked)


@pytest.fixture
def token_env(tmp_path, monkeypatch: pytest.MonkeyPatch):
    keys = [*credentials.KNOWN_KEYS, credentials.CONFIG_DIR_ENV]
    for key in keys:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv(credentials.CONFIG_DIR_ENV, str(tmp_path))
    credentials.save_values(
        {
            "PP_CLIENT_ID": "client-id",
            "PP_CLIENT_SECRET": "client-secret",
            "PP_REDIRECT_URI": credentials.DEFAULT_REDIRECT_URI,
            "PP_ACCESS_TOKEN": "old-access",
            "PP_REFRESH_TOKEN": "old-refresh",
        }
    )
    yield tmp_path
    for key in keys:
        os.environ.pop(key, None)


@pytest.fixture
def client(token_env):
    from practicepanther_mcp.client import PracticePantherClient

    return PracticePantherClient()
