from __future__ import annotations

import json
import re
from unittest.mock import Mock, call

import pytest


EXPECTED_TOOLS = {
    "get_current_user",
    "list_users",
    "get_user",
    "list_accounts",
    "get_account",
    "create_account",
    "update_account",
    "list_contacts",
    "get_contact",
    "list_matters",
    "get_matter",
    "create_matter",
    "update_matter",
    "list_tasks",
    "get_task",
    "create_task",
    "update_task",
    "complete_task",
    "list_events",
    "get_event",
    "create_event",
    "update_event",
    "list_notes",
    "create_note",
    "list_time_entries",
    "create_time_entry",
    "list_expenses",
    "create_expense",
    "list_expense_categories",
    "list_flat_fees",
    "list_invoices",
    "list_payments",
    "list_call_logs",
    "create_call_log",
    "list_custom_fields",
    "list_tags",
}

EXPECTED_RESOURCES = {
    "practicepanther://users",
    "practicepanther://reference-data",
    "practicepanther://security-notes",
}

EXPECTED_PROMPTS = {
    "daily_docket_review",
    "new_client_intake",
    "billing_hygiene_check",
}


def test_server_imports_and_registers_all_named_tools():
    from practicepanther_mcp import server

    tools = set(server.mcp._tool_manager._tools)
    assert tools == EXPECTED_TOOLS
    assert len(tools) == 36


def test_registered_tools_have_docstrings_and_typed_parameters():
    from inspect import signature

    from practicepanther_mcp import server

    for tool_name, tool in server.mcp._tool_manager._tools.items():
        assert tool.fn.__doc__, tool_name
        for parameter in signature(tool.fn).parameters.values():
            assert parameter.annotation is not parameter.empty, (
                tool_name,
                parameter.name,
            )


def test_server_registers_exactly_three_resources_and_three_prompts():
    from practicepanther_mcp import server

    resources = server.mcp._resource_manager._resources
    prompts = server.mcp._prompt_manager._prompts

    assert set(resources) == EXPECTED_RESOURCES
    assert len(resources) == 3
    assert not server.mcp._resource_manager._templates
    assert set(prompts) == EXPECTED_PROMPTS
    assert len(prompts) == 3


def test_users_resource_returns_json_and_lists_users(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from practicepanther_mcp import server

    client = Mock()
    client.list_users.return_value = {"results": [{"id": "user-1"}]}
    monkeypatch.setattr(server, "_client", lambda: client)

    result = json.loads(server.users_resource())

    assert result == {"results": [{"id": "user-1"}]}
    client.list_users.assert_called_once_with(top=100, skip=0)


def test_reference_data_resource_returns_all_metadata_as_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from practicepanther_mcp import server

    client = Mock()
    client.list_custom_fields.side_effect = lambda field_type: [
        {"type": field_type}
    ]
    client.list_tags.side_effect = lambda tag_type: [{"type": tag_type}]
    monkeypatch.setattr(server, "_client", lambda: client)

    result = json.loads(server.reference_data_resource())

    assert result == {
        "custom_fields": {
            "company": [{"type": "company"}],
            "matter": [{"type": "matter"}],
            "contact": [{"type": "contact"}],
        },
        "tags": {
            "account": [{"type": "account"}],
            "matter": [{"type": "matter"}],
            "activity": [{"type": "activity"}],
        },
    }
    assert client.list_custom_fields.call_args_list == [
        call("company"),
        call("matter"),
        call("contact"),
    ]
    assert client.list_tags.call_args_list == [
        call("account"),
        call("matter"),
        call("activity"),
    ]


@pytest.mark.parametrize(
    "prompt_text",
    [
        pytest.param(lambda server: server.daily_docket_review(), id="daily-docket"),
        pytest.param(
            lambda server: server.new_client_intake("Example Client", "Contract dispute"),
            id="new-client-intake",
        ),
        pytest.param(
            lambda server: server.billing_hygiene_check(), id="billing-hygiene"
        ),
    ],
)
def test_prompts_are_nonempty_and_only_reference_registered_tools(prompt_text) -> None:
    from practicepanther_mcp import server

    text = prompt_text(server)
    mentioned_tools = set(
        re.findall(r"\b(?:get|list|create|update|complete)_[a-z_]+\b", text)
    )

    assert text.strip()
    assert mentioned_tools
    assert mentioned_tools <= set(server.mcp._tool_manager._tools)
