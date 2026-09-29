"""Regressions for the fleet canary checks applied during migration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from conftest import DummyResponse
from practicepanther_mcp import credentials, server
from practicepanther_mcp.client import PracticePantherClient


PAGINATED_LIST_TOOLS = (
    "list_users",
    "list_accounts",
    "list_contacts",
    "list_matters",
    "list_tasks",
    "list_events",
    "list_notes",
    "list_time_entries",
    "list_expenses",
    "list_flat_fees",
    "list_invoices",
    "list_payments",
    "list_call_logs",
)


def _list_tool_schemas() -> dict[str, dict[str, Any]]:
    return {
        tool.name: tool.input_schema
        for tool in asyncio.run(server.mcp.list_tools())
        if tool.name in PAGINATED_LIST_TOOLS
    }


def test_paginated_list_schemas_bound_top_and_expose_deterministic_order() -> None:
    schemas = _list_tool_schemas()

    assert set(schemas) == set(PAGINATED_LIST_TOOLS)
    for name in PAGINATED_LIST_TOOLS:
        properties = schemas[name]["properties"]
        assert properties["top"]["default"] == 50
        assert properties["top"]["minimum"] == 1
        assert properties["top"]["maximum"] == 200
        assert properties["skip"]["default"] == 0
        assert properties["skip"]["minimum"] == 0
        assert properties["order_by"]["default"] == "id asc"


@pytest.mark.parametrize("top", [0, 201])
@pytest.mark.parametrize("tool_name", PAGINATED_LIST_TOOLS)
def test_paginated_list_tools_reject_out_of_range_top(
    tool_name: str,
    top: int,
) -> None:
    async def run_tool() -> None:
        tool = server.mcp._tool_manager.get_tool(tool_name)
        assert tool is not None
        with pytest.raises(ToolError, match="validation error"):
            await tool.run({"top": top}, None)

    asyncio.run(run_tool())


def test_list_request_forwards_total_top_skip_and_custom_order(client) -> None:
    calls: list[dict[str, Any]] = []

    def fake_request(method: str, url: str, **kwargs: Any) -> DummyResponse:
        calls.append({"method": method, "url": url, "params": kwargs["params"]})
        return DummyResponse(200, [{"id": "note-1"}])

    client.session.request = fake_request

    result = client.list_notes(
        top=17,
        skip=4,
        order_by="updated_at desc",
    )

    assert result == [{"id": "note-1"}]
    assert len(calls) == 1
    assert calls[0]["params"] == {
        "$top": 17,
        "$skip": 4,
        "$orderby": "updated_at desc",
    }


def test_rejected_list_limit_has_pii_free_reason_log(client, caplog) -> None:
    caplog.set_level(logging.WARNING)

    with pytest.raises(
        ValueError, match="Invalid argument.*top.*integer from 1 to 200"
    ):
        client.list_notes(top=201)

    assert "Rejected PracticePanther list request" in caplog.text
    assert "201" not in caplog.text


def test_rejected_enum_has_pii_free_reason_log(client, caplog) -> None:
    rejected_value = "private-client-name@example.com"
    caplog.set_level(logging.WARNING)

    with pytest.raises(ValueError, match="priority"):
        client.create_task("Draft", priority=rejected_value)

    assert "unsupported enum value" in caplog.text
    assert rejected_value not in caplog.text
    assert "Draft" not in caplog.text


def test_upstream_rejection_omits_pii_from_log_and_exception(client, caplog) -> None:
    upstream_pii = "Private Client private-client-name@example.com"
    caplog.set_level(logging.WARNING)

    def fake_request(method: str, url: str, **kwargs: Any) -> DummyResponse:
        return DummyResponse(403, text=upstream_pii)

    client.session.request = fake_request

    with pytest.raises(RuntimeError, match="PracticePanther access denied") as exc:
        client.get("/users/me")

    assert upstream_pii not in caplog.text
    assert upstream_pii not in str(exc.value)
    assert "provider returned an error" in caplog.text


def test_missing_credentials_rejection_is_logged_without_values(
    monkeypatch, caplog
) -> None:
    caplog.set_level(logging.WARNING)
    monkeypatch.setattr(
        credentials,
        "load_credentials",
        lambda: credentials.PracticePantherCredentials("", "", "", "", ""),
    )

    with pytest.raises(RuntimeError, match="credentials are missing"):
        PracticePantherClient()

    assert "credentials incomplete" in caplog.text


def test_setup_verification_does_not_print_authenticated_name_or_email(
    monkeypatch,
    capsys,
) -> None:
    from practicepanther_mcp.setup import verify

    class StubClient:
        def get_current_user(self) -> dict[str, str]:
            return {
                "display_name": "Private Client",
                "email": "private-client-name@example.com",
            }

        def list_accounts(self, top: int) -> list[Any]:
            return []

        def list_matters(self, top: int) -> list[Any]:
            return []

    monkeypatch.setattr(
        "practicepanther_mcp.client.PracticePantherClient",
        StubClient,
    )

    assert verify.check_api() is True
    output = capsys.readouterr().out
    assert "Authentication verified." in output
    assert "Private Client" not in output
    assert "private-client-name@example.com" not in output
