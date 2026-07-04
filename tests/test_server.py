from __future__ import annotations


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
