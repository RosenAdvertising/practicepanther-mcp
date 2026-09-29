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
            "PracticePanther access denied: the connected account lacks permission for this action (or the authorization expired; re-run practicepanther-mcp-setup if so).",
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
            "PracticePanther request timed out. This read can be retried.",
        ),
        (
            requests.ConnectionError("PRIVATE"),
            "Could not connect to PracticePanther. This read can be retried.",
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
    ("header", "seconds"), [("90", "90"), ("NaN", "8"), ("-2", "0"), ("1.5", "1.5")]
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


def test_retry_after_aggregate_wait_is_capped_without_shortening_hint(
    client, monkeypatch
):
    from practicepanther_mcp import server
    import practicepanther_mcp.client as client_module

    calls = []
    sleeps = []

    def fake_request(method, *_args, **_kwargs):
        calls.append(1)
        if len(calls) in {1, 3}:
            return DummyResponse(429, {}, headers={"Retry-After": "35"})
        return DummyResponse(200, {"id": "matter-1", "name": "Old"})

    client.session.request = fake_request
    monkeypatch.setattr(client_module.time, "sleep", sleeps.append)
    monkeypatch.setattr(server, "_client", lambda: client)
    result = _call(
        "update_matter", {"matter_id": "matter-1", "matter_data": {"name": "New"}}
    )
    assert result.is_error is True
    assert (
        result.content[0].text
        == "PracticePanther rate limit reached. Retry after 35 seconds."
    )
    assert sleeps == [35.0]
    assert len(calls) == 3


def test_request_timeout_is_set_for_oauth_refresh(client, monkeypatch):
    refresh_calls = []

    def fake_request(*_args, **_kwargs):
        return DummyResponse(400, {"error": "invalid_grant"})

    def fake_post(*_args, **kwargs):
        refresh_calls.append(kwargs)
        return DummyResponse(400, {"error": "invalid_grant"})

    client.session.request = fake_request
    monkeypatch.setattr(requests, "post", fake_post)
    with pytest.raises(Exception):
        client.get("/users/me")
    assert refresh_calls[0]["timeout"] == 30


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


@pytest.mark.parametrize("body", ["VENDOR_PROSE_SENTINEL", 42, True])
def test_malformed_success_envelope_is_safe_tool_error(client, monkeypatch, body):
    from practicepanther_mcp import server

    client.session.request = lambda *a, **k: DummyResponse(200, body)
    monkeypatch.setattr(server, "_client", lambda: client)
    result = _call("get_current_user", {})
    assert result.is_error is True
    assert (
        result.content[0].text
        == "PracticePanther request failed (HTTP 200: response had an invalid format)."
    )
    assert "VENDOR_PROSE_SENTINEL" not in result.content[0].text


def test_empty_failure_body_is_not_reported_as_success(client):
    from practicepanther_mcp import server

    client.session.request = lambda *a, **k: DummyResponse(
        500, None, text="PRIVATE_EMPTY_BODY_SENTINEL"
    )
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(server, "_client", lambda: client)
    try:
        result = _call("get_current_user", {})
    finally:
        monkeypatch.undo()
    assert result.is_error is True
    assert (
        result.content[0].text
        == "PracticePanther request failed (HTTP 500: request rejected)."
    )
    assert "PRIVATE_EMPTY_BODY_SENTINEL" not in result.content[0].text


@pytest.mark.parametrize(
    "error", [requests.Timeout("hidden"), requests.ConnectionError("hidden")]
)
def test_write_transport_error_warns_outcome_is_unknown(client, monkeypatch, error):
    from practicepanther_mcp import server

    client.session.request = lambda *a, **k: (_ for _ in ()).throw(error)
    monkeypatch.setattr(server, "_client", lambda: client)
    result = _call("create_account", {"display_name": "Example"})
    assert result.is_error is True
    expected_prefix = (
        "PracticePanther request timed out."
        if isinstance(error, requests.Timeout)
        else "Could not connect to PracticePanther."
    )
    assert result.content[0].text == (
        expected_prefix
        + " The outcome of this write is unknown; check whether it completed before retrying."
    )
    assert "hidden" not in result.content[0].text


def test_resource_unknown_failure_is_masked_before_sdk_logging(
    token_env, monkeypatch, caplog
):
    import logging
    from mcp_types import ReadResourceRequestParams
    from practicepanther_mcp.server import mcp

    sentinel = "RESOURCE_PRIVATE_SENTINEL"

    def fail():
        raise RuntimeError(sentinel)

    monkeypatch.setattr("practicepanther_mcp.server._client", fail)
    caplog.set_level(logging.INFO)
    with pytest.raises(Exception) as caught:
        asyncio.run(
            mcp._handle_read_resource(
                cast(Any, None),
                ReadResourceRequestParams(uri="practicepanther://users"),
            )
        )
    assert sentinel not in str(caught.value)
    assert sentinel not in caplog.text
    assert "Traceback" not in caplog.text


def test_verify_entrypoint_without_credentials_is_actionable(
    token_env, monkeypatch, capsys
):
    from practicepanther_mcp import credentials
    from practicepanther_mcp.setup import verify

    for key in credentials.KNOWN_KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(credentials, "_parse_env_file", lambda *args: {})
    with pytest.raises(SystemExit) as exited:
        verify.main()
    output = capsys.readouterr().out
    assert exited.value.code == 1
    assert "Missing PracticePanther config" in output
    assert "practicepanther-mcp-setup" in output
    assert "Traceback" not in output


def test_verify_entrypoint_fake_bad_key_is_actionable(token_env, monkeypatch, capsys):
    from practicepanther_mcp import client as client_module
    from practicepanther_mcp.setup import verify

    class FakeBadKeyClient:
        def __init__(self):
            pass

        def get_current_user(self):
            from practicepanther_mcp.client import ReauthorizationError

            raise ReauthorizationError(
                "PracticePanther authorization was rejected. Re-run setup with: practicepanther-mcp-setup"
            )

    monkeypatch.setattr(client_module, "PracticePantherClient", FakeBadKeyClient)
    with pytest.raises(SystemExit) as exited:
        verify.main()
    output = capsys.readouterr().out
    assert exited.value.code == 1
    assert "authorization was rejected" in output
    assert "practicepanther-mcp-setup" in output
    assert "Traceback" not in output


def test_setup_entrypoint_empty_input_fails_without_authorize_url(monkeypatch, capsys):
    from practicepanther_mcp.setup import setup

    monkeypatch.setattr("builtins.input", lambda _prompt="": "")
    with pytest.raises(SystemExit) as exited:
        setup.main()
    output = capsys.readouterr().out
    assert exited.value.code == 1
    assert "Client ID is required" in output
    assert "oauth/authorize" not in output
    assert "Traceback" not in output


def test_setup_entrypoint_eof_fails_clearly(monkeypatch, capsys):
    from practicepanther_mcp.setup import setup

    def eof(_prompt=""):
        raise EOFError

    monkeypatch.setattr("builtins.input", eof)
    with pytest.raises(SystemExit) as exited:
        setup.main()
    output = capsys.readouterr().out
    assert exited.value.code == 1
    assert "input ended" in output
    assert "Traceback" not in output


def test_setup_entrypoint_fake_bad_key_has_safe_failure(monkeypatch, capsys):
    from practicepanther_mcp.setup import setup

    answers = iter(["fake-client", "http://localhost/callback", "fake-code"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))
    monkeypatch.setattr("getpass.getpass", lambda _prompt="": "fake-secret")
    calls = []

    def fake_post(*args, **kwargs):
        calls.append(kwargs)
        return DummyResponse(401, {"message": "PRIVATE_VENDOR_BODY"})

    monkeypatch.setattr(setup.requests, "post", fake_post)
    with pytest.raises(SystemExit) as exited:
        setup.main()
    output = capsys.readouterr().out
    assert exited.value.code == 1
    assert "Token exchange failed (401)" in output
    assert "PRIVATE_VENDOR_BODY" not in output
    assert "Traceback" not in output
    assert calls[0]["timeout"] == 30


def test_unexpected_outer_exception_does_not_expose_safe_cause(monkeypatch):
    from practicepanther_mcp import server
    from practicepanther_mcp.client import MissingCredentialsError

    def fail():
        raise RuntimeError("PRIVATE_OUTER") from MissingCredentialsError(
            "PRIVATE_CAUSE"
        )

    monkeypatch.setattr(server, "_client", fail)
    result = _call("get_current_user", {})
    assert result.is_error is True
    assert result.content[0].text == "Error executing tool get_current_user"


@pytest.mark.parametrize("failure", [requests.Timeout, requests.ConnectionError])
def test_setup_transport_failure_warns_of_unknown_outcome(monkeypatch, capsys, failure):
    from practicepanther_mcp.setup import setup

    answers = iter(["fake-client", "", "fake-code"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))
    monkeypatch.setattr("getpass.getpass", lambda _prompt="": "fake-secret")
    monkeypatch.setattr(
        setup.requests,
        "post",
        lambda *a, **k: (_ for _ in ()).throw(failure("PRIVATE")),
    )
    with pytest.raises(SystemExit) as stopped:
        setup.main()
    output = capsys.readouterr().out
    expected = (
        "Token exchange timed out"
        if failure is requests.Timeout
        else "Token exchange lost its connection"
    )
    assert stopped.value.code == 1
    assert output.endswith(
        expected
        + "; the outcome is unknown. Check whether authorization completed before retrying setup.\n"
    )
    assert "PRIVATE" not in output


@pytest.mark.parametrize("timed_out", [True, False])
def test_verify_refresh_transport_failure_preserves_unknown_outcome(
    client, monkeypatch, capsys, timed_out
):
    from practicepanther_mcp import client as client_module
    from practicepanther_mcp.setup import verify

    def failed_refresh(*args, **kwargs):
        raise client_module.TransportError("POST", timed_out=timed_out)

    monkeypatch.setattr(client, "get_current_user", failed_refresh)
    monkeypatch.setattr(client_module, "PracticePantherClient", lambda: client)
    assert verify.check_api() is False
    assert capsys.readouterr().out == (
        "API check failed: PracticePanther authorization request failed; the outcome is unknown. "
        "Check whether authorization completed before retrying verification.\n"
    )
