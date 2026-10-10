"""In-process tests for the stateless 2026-07-28 Streamable HTTP transport.

Every test drives `create_serve_app()` — the same app `main()` serves under
uvicorn — over raw ASGI, so nothing here starts a real socket.
"""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from typing import Any

import httpx2
import pytest
import requests
from conftest import DummyResponse
from mcp import Client

from practicepanther_mcp import __version__, server


PROTOCOL_VERSION = "2026-07-28"
PROTOCOL_VERSION_META_KEY = "io.modelcontextprotocol/protocolVersion"
CLIENT_CAPABILITIES_META_KEY = "io.modelcontextprotocol/clientCapabilities"
CLIENT_INFO_META_KEY = "io.modelcontextprotocol/clientInfo"
SERVER_INFO_META_KEY = "io.modelcontextprotocol/serverInfo"
TRANSPORT_ENV = "PRACTICEPANTHER_MCP_TRANSPORT"
HOST_ENV = "PRACTICEPANTHER_MCP_HOST"
ALLOWED_HOSTS_ENV = "PRACTICEPANTHER_MCP_ALLOWED_HOSTS"
ALLOWED_ORIGINS_ENV = "PRACTICEPANTHER_MCP_ALLOWED_ORIGINS"


def _clear_transport_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin the transport environment to the documented defaults."""
    for key in (
        TRANSPORT_ENV,
        HOST_ENV,
        ALLOWED_HOSTS_ENV,
        ALLOWED_ORIGINS_ENV,
        "PORT",
    ):
        monkeypatch.delenv(key, raising=False)


def _modern_request(
    method: str,
    params: dict[str, Any] | None = None,
    request_id: int = 1,
) -> tuple[dict[str, str], dict[str, Any]]:
    request_params = dict(params or {})
    request_params["_meta"] = {
        PROTOCOL_VERSION_META_KEY: PROTOCOL_VERSION,
        CLIENT_CAPABILITIES_META_KEY: {},
        CLIENT_INFO_META_KEY: {"name": "practicepanther-http-test", "version": "0"},
    }
    headers = {
        "accept": "application/json, text/event-stream",
        "content-type": "application/json",
        "mcp-protocol-version": PROTOCOL_VERSION,
        "mcp-method": method,
    }
    if method in {"tools/call", "prompts/get"}:
        headers["mcp-name"] = str(request_params["name"])
    elif method == "resources/read":
        headers["mcp-name"] = str(request_params["uri"])
    return headers, {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": method,
        "params": request_params,
    }


def _tools_list_request(request_id: int = 1) -> tuple[dict[str, str], dict[str, Any]]:
    return _modern_request("tools/list", request_id=request_id)


def _result(response: httpx2.Response) -> dict[str, Any]:
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["jsonrpc"] == "2.0"
    return payload["result"]


async def _serve_requests(
    app,
    *,
    base_url: str = "http://127.0.0.1:9911",
    requests_spec: list[tuple[str, str, dict[str, str], dict[str, Any]]],
) -> list[httpx2.Response]:
    """Run each (method, path, headers, json body) request inside one lifespan."""
    async with app.router.lifespan_context(app):
        transport = httpx2.ASGITransport(app=app)
        async with httpx2.AsyncClient(transport=transport, base_url=base_url) as client:
            responses = []
            for method, path, headers, body in requests_spec:
                responses.append(
                    await client.request(method, path, headers=headers, json=body)
                )
            return responses


def test_http_tools_list_equals_the_stdio_servers_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A 2026-07-28 tools/list POST returns 200 and matches the stdio server."""
    _clear_transport_env(monkeypatch)
    app = server.create_serve_app()
    headers, body = _tools_list_request()
    response = asyncio.run(
        _serve_requests(app, requests_spec=[("POST", "/mcp", headers, body)])
    )[0]

    assert response.status_code == 200
    http_tools = _result(response)["tools"]
    http_by_name = {tool["name"]: tool["inputSchema"] for tool in http_tools}
    assert len(http_by_name) == 36

    async def stdio_list() -> dict[str, Any]:
        async with Client(server.mcp, cache=None) as client:
            result = await client.list_tools()
        return {tool.name: tool.input_schema for tool in result.tools}

    stdio_by_name = asyncio.run(stdio_list())
    assert http_by_name == stdio_by_name


def test_read_tool_runs_end_to_end_over_http_with_vendor_mocks(
    monkeypatch: pytest.MonkeyPatch, token_env
) -> None:
    """One read tool goes request -> tool -> PracticePanther client -> response."""
    _clear_transport_env(monkeypatch)
    calls: list[dict[str, Any]] = []

    def fake_request(session_self, method, url, **kwargs):
        calls.append(
            {
                "method": method,
                "url": url,
                "authorization": session_self.headers["Authorization"],
            }
        )
        return DummyResponse(200, {"id": "user-1", "email_address": "toby@example.com"})

    monkeypatch.setattr(requests.sessions.Session, "request", fake_request)
    app = server.create_serve_app()
    headers, body = _modern_request(
        "tools/call", {"name": "get_current_user", "arguments": {}}
    )
    headers["authorization"] = "Bearer ignored-request-token"
    response = asyncio.run(
        _serve_requests(app, requests_spec=[("POST", "/mcp", headers, body)])
    )[0]

    assert response.status_code == 200
    result = _result(response)
    assert result["isError"] is False
    assert json.loads(result["content"][0]["text"]) == {
        "id": "user-1",
        "email_address": "toby@example.com",
    }
    assert calls == [
        {
            "method": "GET",
            "url": "https://app.practicepanther.com/api/v2/users/me",
            "authorization": "Bearer old-access",
        }
    ]


def test_responses_have_no_session_id_and_requests_share_no_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No Mcp-Session-Id anywhere, and the second POST needs nothing from the first."""
    _clear_transport_env(monkeypatch)
    app = server.create_serve_app()
    first_headers, first_body = _tools_list_request(request_id=1)
    second_headers, second_body = _tools_list_request(request_id=2)
    # A different client needs no initialization or state from the first POST.
    second_body["params"]["_meta"][CLIENT_INFO_META_KEY]["name"] = "second-client"
    second_headers["mcp-session-id"] = "unrelated-client-session"
    first, second = asyncio.run(
        _serve_requests(
            app,
            requests_spec=[
                ("POST", "/mcp", first_headers, first_body),
                ("POST", "/mcp", second_headers, second_body),
            ],
        )
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert "mcp-session-id" not in first.headers
    assert "mcp-session-id" not in second.headers
    assert first.json()["id"] == 1
    assert second.json()["id"] == 2
    assert first.json()["result"]["tools"] == second.json()["result"]["tools"]


def test_bogus_transport_value_exits_naming_both_options(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(TRANSPORT_ENV, "bogus")
    with pytest.raises(SystemExit) as excinfo:
        server.main()

    message = str(excinfo.value)
    assert "bogus" in message
    assert "stdio" in message
    assert "streamable-http" in message


def test_default_transport_is_stdio(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(TRANSPORT_ENV, raising=False)
    assert server._requested_transport() == "stdio"

    recorded: list[str] = []
    monkeypatch.setattr(server.mcp, "run", lambda: recorded.append("stdio-ran"))
    server.main()
    assert recorded == ["stdio-ran"]


def test_transport_value_is_stripped_and_lowercased(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(TRANSPORT_ENV, "  STREAMABLE-HTTP  ")
    assert server._requested_transport() == "streamable-http"


def test_streamable_http_transport_dispatches_to_the_http_server(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(TRANSPORT_ENV, "streamable-http")
    recorded: list[str] = []

    async def fake_serve() -> None:
        recorded.append("served")

    monkeypatch.setattr(server, "_serve_streamable_http", fake_serve)
    server.main()
    assert recorded == ["served"]


def test_port_defaults_and_rejects_non_integers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PORT", raising=False)
    assert server._port() == 8080

    monkeypatch.setenv("PORT", "not-a-port")
    with pytest.raises(SystemExit) as excinfo:
        server._port()
    assert "PORT" in str(excinfo.value)
    assert "not-a-port" in str(excinfo.value)


def test_loopback_host_needs_no_extra_security_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_transport_env(monkeypatch)
    assert server._host() == "127.0.0.1"
    assert server._transport_security() is None


@pytest.mark.parametrize("allowed_hosts", [None, "", "   ", ", ,"])
def test_non_loopback_host_without_allowed_hosts_exits_with_message(
    monkeypatch: pytest.MonkeyPatch,
    allowed_hosts: str | None,
) -> None:
    monkeypatch.setenv(HOST_ENV, "example.internal")
    if allowed_hosts is None:
        monkeypatch.delenv(ALLOWED_HOSTS_ENV, raising=False)
    else:
        monkeypatch.setenv(ALLOWED_HOSTS_ENV, allowed_hosts)

    with pytest.raises(SystemExit) as excinfo:
        server.create_serve_app()

    assert ALLOWED_HOSTS_ENV in str(excinfo.value)


def test_another_host_header_is_refused_and_bad_origin_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(HOST_ENV, "example.internal")
    monkeypatch.setenv(ALLOWED_HOSTS_ENV, "example.internal")
    monkeypatch.delenv(ALLOWED_ORIGINS_ENV, raising=False)
    app = server.create_serve_app()
    headers, body = _tools_list_request()

    async def scenario():
        async with app.router.lifespan_context(app):
            transport = httpx2.ASGITransport(app=app)
            async with httpx2.AsyncClient(
                transport=transport, base_url="http://evil.example"
            ) as client:
                refused_host = await client.post("/mcp", headers=headers, json=body)
            async with httpx2.AsyncClient(
                transport=transport, base_url="http://example.internal"
            ) as client:
                bad_origin = await client.post(
                    "/mcp",
                    headers={**headers, "origin": "https://evil.example"},
                    json=body,
                )
                allowed = await client.post("/mcp", headers=headers, json=body)
        return refused_host, bad_origin, allowed

    refused_host, bad_origin, allowed = asyncio.run(scenario())
    assert refused_host.status_code == 421
    assert bad_origin.status_code == 403
    assert allowed.status_code == 200


def test_allowed_origins_env_admits_matching_origin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(HOST_ENV, "example.internal")
    monkeypatch.setenv(ALLOWED_HOSTS_ENV, "example.internal")
    monkeypatch.setenv(ALLOWED_ORIGINS_ENV, "https://app.example.com")
    app = server.create_serve_app()
    headers, body = _tools_list_request()

    async def scenario():
        async with app.router.lifespan_context(app):
            transport = httpx2.ASGITransport(app=app)
            async with httpx2.AsyncClient(
                transport=transport, base_url="http://example.internal"
            ) as client:
                return await client.post(
                    "/mcp",
                    headers={**headers, "origin": "https://app.example.com"},
                    json=body,
                )

    response = asyncio.run(scenario())
    assert response.status_code == 200


def test_get_and_delete_on_mcp_return_405(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_transport_env(monkeypatch)
    app = server.create_serve_app()
    headers, _body = _tools_list_request()

    get_response, delete_response = asyncio.run(
        _serve_requests(
            app,
            requests_spec=[
                ("GET", "/mcp", headers, None),
                ("DELETE", "/mcp", headers, None),
            ],
        )
    )
    assert get_response.status_code == 405
    assert delete_response.status_code == 405


def test_discover_over_http_reports_modern_version_and_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_transport_env(monkeypatch)
    app = server.create_serve_app()
    headers, body = _modern_request("server/discover")
    response = asyncio.run(
        _serve_requests(app, requests_spec=[("POST", "/mcp", headers, body)])
    )[0]

    assert response.status_code == 200
    result = _result(response)
    assert PROTOCOL_VERSION in result["supportedVersions"]
    server_info = result["_meta"][SERVER_INFO_META_KEY]
    assert server_info["name"] == "practicepanther-mcp"
    assert server_info["version"]


def test_stateless_lifespan_runs_once_per_app_not_per_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The app lifespan enters at startup only; requests do not re-enter it."""
    _clear_transport_env(monkeypatch)
    lowlevel = server.mcp._lowlevel_server
    original = lowlevel.lifespan
    events: list[str] = []

    @asynccontextmanager
    async def counting_lifespan(server_instance):
        events.append("enter")
        async with original(server_instance) as state:
            yield state
        events.append("exit")

    monkeypatch.setattr(lowlevel, "lifespan", counting_lifespan)
    app = server.create_serve_app()
    first_headers, first_body = _tools_list_request(request_id=1)
    second_headers, second_body = _tools_list_request(request_id=2)
    first, second = asyncio.run(
        _serve_requests(
            app,
            requests_spec=[
                ("POST", "/mcp", first_headers, first_body),
                ("POST", "/mcp", second_headers, second_body),
            ],
        )
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert events == ["enter", "exit"]


def test_server_identity_is_fully_specified() -> None:
    """R8: name, title, and version are all set and none empty."""
    assert server.mcp.name == "practicepanther-mcp"
    assert server.mcp.title
    assert server.mcp.version == __version__
    assert __version__


def test_http_disconnect_cancels_an_in_flight_tool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_transport_env(monkeypatch)
    headers, body = _modern_request(
        "tools/call", {"name": "get_current_user", "arguments": {}}
    )

    async def scenario() -> None:
        started = asyncio.Event()
        cancelled = asyncio.Event()

        async def pending_tool(*args, **kwargs):
            started.set()
            try:
                await asyncio.Future()
            finally:
                cancelled.set()

        monkeypatch.setattr(server.MCPServer, "call_tool", pending_tool)
        app = server.create_serve_app()
        request_sent = False

        async def receive():
            nonlocal request_sent
            if not request_sent:
                request_sent = True
                return {
                    "type": "http.request",
                    "body": json.dumps(body).encode(),
                    "more_body": False,
                }
            await started.wait()
            return {"type": "http.disconnect"}

        async def send(message):
            pass

        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/mcp",
            "raw_path": b"/mcp",
            "root_path": "",
            "query_string": b"",
            "headers": [
                (key.encode(), value.encode())
                for key, value in {**headers, "host": "127.0.0.1:8080"}.items()
            ],
            "server": ("127.0.0.1", 8080),
            "client": ("127.0.0.1", 12345),
        }
        async with app.router.lifespan_context(app):
            await asyncio.wait_for(app(scope, receive, send), timeout=2)
        assert started.is_set()
        assert cancelled.is_set()

    asyncio.run(scenario())
