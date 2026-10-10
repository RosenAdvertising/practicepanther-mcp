"""Concurrency and cancellation regressions for stateless request execution."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
import requests
from conftest import DummyResponse

from practicepanther_mcp import credentials, server
from practicepanther_mcp.client import PracticePantherClient


def test_concurrent_clients_refresh_a_rotating_token_only_once(
    token_env,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clients = [PracticePantherClient(), PracticePantherClient()]
    expired_requests = Barrier(2, timeout=5)
    refresh_calls: list[str] = []

    def fake_request(session, method, url, **kwargs):
        if session.headers["Authorization"] == "Bearer old-access":
            expired_requests.wait()
            return DummyResponse(400, {"error": "invalid_grant"})
        assert session.headers["Authorization"] == "Bearer new-access"
        return DummyResponse(200, {"id": "user-1"})

    def fake_refresh(url, data, timeout):
        refresh_calls.append(data["refresh_token"])
        if len(refresh_calls) > 1:
            return DummyResponse(400, {"error": "invalid_grant"})
        return DummyResponse(
            200, {"access_token": "new-access", "refresh_token": "new-refresh"}
        )

    monkeypatch.setattr(requests.sessions.Session, "request", fake_request)
    monkeypatch.setattr(requests, "post", fake_refresh)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda client: client.get_current_user(), clients))

    assert results == [{"id": "user-1"}, {"id": "user-1"}]
    assert refresh_calls == ["old-refresh"]
    saved = credentials._parse_env_file(token_env / ".env")
    assert saved["PP_ACCESS_TOKEN"] == "new-access"
    assert saved["PP_REFRESH_TOKEN"] == "new-refresh"
    assert all(client.creds.refresh_token == "new-refresh" for client in clients)


def test_tool_cancellation_propagates_through_the_error_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def cancelled_call(*args, **kwargs):
        raise asyncio.CancelledError

    monkeypatch.setattr(server.MCPServer, "call_tool", cancelled_call)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(server.mcp.call_tool("get_current_user", {}))
