from __future__ import annotations

import asyncio
import logging
from typing import Any, cast

import pytest
import requests
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import CallToolRequestParams

from conftest import DummyResponse


def _call(name: str, arguments: dict):
    from practicepanther_mcp.server import mcp

    return asyncio.run(
        mcp._handle_call_tool(
            cast(Any, None), CallToolRequestParams(name=name, arguments=arguments)
        )
    )


def test_missing_credentials_is_actionable_and_error(token_env, monkeypatch):
    from practicepanther_mcp import server
    from practicepanther_mcp import credentials

    for key in credentials.KNOWN_KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(credentials, "_parse_env_file", lambda *args: {})
    monkeypatch.setattr(
        server,
        "_client",
        lambda: __import__(
            "practicepanther_mcp.client", fromlist=["PracticePantherClient"]
        ).PracticePantherClient(),
    )
    result = _call("get_current_user", {})
    assert result.is_error is True
    assert (
        result.content[0].text
        == "PracticePanther credentials are missing. Set PP_CLIENT_ID, PP_CLIENT_SECRET, PP_ACCESS_TOKEN, and PP_REFRESH_TOKEN, or run: practicepanther-mcp-setup"
    )


@pytest.mark.parametrize(
    ("status", "payload", "expected"),
    [
        (
            401,
            {"error": "unauthorized"},
            "PracticePanther authorization was rejected. Re-run setup with: practicepanther-mcp-setup",
        ),
        (
            403,
            {"error": "forbidden"},
            "PracticePanther authorization was rejected. Re-run setup with: practicepanther-mcp-setup",
        ),
        (
            404,
            {"error": "not_found"},
            "PracticePanther record was not found (HTTP 404). Check the record ID.",
        ),
        (
            503,
            {"error": "SENSITIVE_TOKEN https://attacker.invalid PII"},
            "PracticePanther request failed (HTTP 503: request rejected).",
        ),
    ],
)
def test_http_status_classification_reaches_tool_result(
    client, status, payload, expected
):
    client.session.request = lambda *a, **k: DummyResponse(status, payload)
    from practicepanther_mcp import server

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(server, "_client", lambda: client)
    try:
        result = _call("get_current_user", {})
    finally:
        monkeypatch.undo()
    assert result.is_error is True
    assert result.content[0].text == expected
    assert "SENSITIVE_TOKEN" not in result.content[0].text


def test_rate_limit_retry_after_is_capped_and_arbitrary_text_hidden(
    client, monkeypatch
):
    import practicepanther_mcp.client as client_module
    from practicepanther_mcp import server

    client.session.request = lambda *a, **k: DummyResponse(
        429, {"error": "unsafe"}, headers={"Retry-After": "999999 SECRET"}
    )
    monkeypatch.setattr(client_module.time, "sleep", lambda _: None)
    monkeypatch.setattr(server, "_client", lambda: client)
    result = _call("get_current_user", {})
    assert result.is_error is True
    assert (
        result.content[0].text
        == "PracticePanther rate limit reached. Retry after 8 seconds."
    )
    assert "SECRET" not in result.content[0].text


def test_argument_validation_uses_schema_name_not_attacker_key():
    sentinel = "ARGUMENT_SECRET_VALUE"
    result = _call("list_accounts", {"top": sentinel, "attacker_key": sentinel})
    text = result.content[0].text
    assert result.is_error is True
    assert text == "Invalid argument 'top'; expected integer from 1 to 200."
    assert "attacker_key" not in text and sentinel not in text


def test_unknown_exception_is_masked_and_not_logged(caplog, monkeypatch):
    from practicepanther_mcp import server

    sentinel = "UNKNOWN_SECRET_SENTINEL"
    monkeypatch.setattr(
        server,
        "_client",
        lambda: type(
            "Fake",
            (),
            {
                "get_current_user": lambda self: (_ for _ in ()).throw(
                    RuntimeError(sentinel)
                )
            },
        )(),
    )
    caplog.set_level(logging.INFO)
    result = _call("get_current_user", {})
    assert result.is_error is True
    assert result.content[0].text == "Error executing tool get_current_user"
    assert sentinel not in caplog.text
    assert "Traceback" not in caplog.text


@pytest.mark.parametrize(
    ("status", "body", "expected"),
    [
        (
            422,
            {"error": {"code": "validation_error", "message": "PRIVATE"}},
            "PracticePanther request failed (HTTP 422: invalid request).",
        ),
        (
            400,
            ["PRIVATE"],
            "PracticePanther request failed (HTTP 400: request rejected).",
        ),
        (
            503,
            {"code": ["PRIVATE"]},
            "PracticePanther request failed (HTTP 503: request rejected).",
        ),
    ],
)
def test_vendor_reason_codes_and_malformed_payloads(
    client, monkeypatch, status, body, expected
):
    from practicepanther_mcp import server

    client.session.request = lambda *a, **k: DummyResponse(status, body)
    monkeypatch.setattr(server, "_client", lambda: client)
    result = _call("get_current_user", {})
    assert result.is_error is True
    assert result.content[0].text == expected


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (
            400,
            "PracticePanther authorization failed. Re-run setup with: practicepanther-mcp-setup",
        ),
        (429, "PracticePanther rate limit reached. Retry after 11 seconds."),
        (503, "PracticePanther request failed (HTTP 503: service unavailable)."),
    ],
)
def test_oauth_refresh_classifies_provider_failure(
    client, monkeypatch, status, expected
):
    from practicepanther_mcp import server

    client.session.request = lambda *a, **k: DummyResponse(
        400, {"error": "invalid_grant"}
    )
    monkeypatch.setattr(
        requests,
        "post",
        lambda *a, **k: DummyResponse(
            status,
            {"error": "service_unavailable", "message": "PRIVATE"},
            headers={"Retry-After": "11"},
        ),
    )
    monkeypatch.setattr(server, "_client", lambda: client)
    result = _call("get_current_user", {})
    assert result.is_error is True
    assert result.content[0].text == expected


def test_repeated_invalid_grant_requires_reauthorization(client, monkeypatch):
    from practicepanther_mcp import server

    client.session.request = lambda *a, **k: DummyResponse(
        400, {"error": "invalid_grant"}
    )
    monkeypatch.setattr(
        requests,
        "post",
        lambda *a, **k: DummyResponse(
            200, {"access_token": "fake-new", "refresh_token": "fake-refresh"}
        ),
    )
    monkeypatch.setattr(server, "_client", lambda: client)
    result = _call("get_current_user", {})
    assert result.is_error is True
    assert (
        result.content[0].text
        == "PracticePanther authorization was rejected. Re-run setup with: practicepanther-mcp-setup"
    )


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (
            requests.Timeout("PRIVATE"),
            "PracticePanther request timed out. Retry shortly.",
        ),
        (
            requests.ConnectionError("PRIVATE"),
            "Could not connect to PracticePanther. Check connectivity and retry.",
        ),
        (ValueError("PRIVATE"), "Error executing tool get_current_user"),
        (ToolError("PRIVATE"), "Error executing tool get_current_user"),
    ],
)
def test_transport_and_unknown_errors(client, monkeypatch, caplog, error, expected):
    from practicepanther_mcp import server

    def fail(*_a, **_k):
        raise error

    client.session.request = fail
    monkeypatch.setattr(server, "_client", lambda: client)
    caplog.set_level(logging.INFO)
    result = _call("get_current_user", {})
    assert result.is_error is True
    assert result.content[0].text == expected
    assert "PRIVATE" not in caplog.text
    assert "Traceback" not in caplog.text


@pytest.mark.parametrize(
    ("arguments", "expected"),
    [
        ({"top": 201}, "Invalid argument 'top'; expected integer from 1 to 200."),
        ({"skip": -1}, "Invalid argument 'skip'; expected integer >= 0."),
    ],
)
def test_range_guidance(arguments, expected):
    result = _call("list_accounts", arguments)
    assert result.is_error is True
    assert result.content[0].text == expected


def test_local_enum_validation_is_actionable(client, monkeypatch):
    from practicepanther_mcp import server

    monkeypatch.setattr(server, "_client", lambda: client)
    result = _call("create_task", {"subject": "test", "priority": "PRIVATE"})
    assert result.is_error is True
    assert (
        result.content[0].text
        == "Invalid argument 'priority'; expected one of: High, Low, Medium."
    )


@pytest.mark.parametrize(
    ("header", "seconds"), [("90", "60"), ("NaN", "8"), ("-2", "0"), ("1.5", "1.5")]
)
def test_numeric_retry_hints_are_bounded(client, monkeypatch, header, seconds):
    from practicepanther_mcp import server
    import practicepanther_mcp.client as client_module

    client.session.request = lambda *a, **k: DummyResponse(
        429, {}, headers={"Retry-After": header}
    )
    monkeypatch.setattr(server, "_client", lambda: client)
    monkeypatch.setattr(client_module.time, "sleep", lambda _seconds: None)
    result = _call("get_current_user", {})
    assert result.is_error is True
    assert (
        result.content[0].text
        == f"PracticePanther rate limit reached. Retry after {seconds} seconds."
    )


def test_invalid_json_response_has_safe_reason(client, monkeypatch, caplog):
    from practicepanther_mcp import server

    client.session.request = lambda *a, **k: DummyResponse(200, ValueError("PRIVATE"))
    monkeypatch.setattr(server, "_client", lambda: client)
    result = _call("get_current_user", {})
    assert result.is_error is True
    assert (
        result.content[0].text
        == "PracticePanther request failed (HTTP 200: response was not valid JSON)."
    )
    assert "PRIVATE" not in caplog.text
