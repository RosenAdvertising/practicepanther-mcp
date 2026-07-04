from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from conftest import DummyResponse


BASE_URL = "https://app.practicepanther.com/api/v2"


@dataclass(frozen=True)
class ExpectedCall:
    method: str
    path: str
    params: dict[str, Any] | None = None
    json: Any = None
    response: Any = None

    @property
    def url(self) -> str:
        return f"{BASE_URL}{self.path}"


@dataclass(frozen=True)
class ToolContract:
    name: str
    args: dict[str, Any]
    calls: tuple[ExpectedCall, ...]

    @property
    def final_response(self) -> Any:
        return self.calls[-1].response


TOOL_CONTRACTS: tuple[ToolContract, ...] = (
    ToolContract(
        "get_current_user",
        {},
        (ExpectedCall("GET", "/users/me", response={"tool": "get_current_user"}),),
    ),
    ToolContract(
        "list_users",
        {"email_address": "alex@example.com", "top": 7, "skip": 3},
        (
            ExpectedCall(
                "GET",
                "/users",
                params={
                    "$top": 7,
                    "$skip": 3,
                    "email_address": "alex@example.com",
                },
                response={"tool": "list_users", "items": [1]},
            ),
        ),
    ),
    ToolContract(
        "get_user",
        {"user_id": "user-1"},
        (ExpectedCall("GET", "/users/user-1", response={"id": "user-1"}),),
    ),
    ToolContract(
        "list_accounts",
        {
            "search_text": "smith",
            "assigned_to_user_id": "user-1",
            "account_tag": "vip",
            "top": 7,
            "skip": 3,
            "order_by": "updated_at desc",
        },
        (
            ExpectedCall(
                "GET",
                "/accounts",
                params={
                    "$top": 7,
                    "$skip": 3,
                    "$orderby": "updated_at desc",
                    "search_text": "smith",
                    "assigned_to_user_id": "user-1",
                    "account_tag": "vip",
                },
                response={"tool": "list_accounts", "items": [1]},
            ),
        ),
    ),
    ToolContract(
        "get_account",
        {"account_id": "account-1"},
        (ExpectedCall("GET", "/accounts/account-1", response={"id": "account-1"}),),
    ),
    ToolContract(
        "create_account",
        {
            "display_name": "Acme LLC",
            "company_name": "Acme",
            "address_city": "Bangkok",
            "tags": ["vip", "referral"],
            "primary_contact": {"first_name": "Alex", "email": "alex@example.com"},
        },
        (
            ExpectedCall(
                "POST",
                "/accounts",
                json={
                    "display_name": "Acme LLC",
                    "company_name": "Acme",
                    "address_city": "Bangkok",
                    "tags": ["vip", "referral"],
                    "primary_contact": {
                        "first_name": "Alex",
                        "email": "alex@example.com",
                    },
                },
                response={"created": "account-1", "display_name": "Acme LLC"},
            ),
        ),
    ),
    ToolContract(
        "update_account",
        {
            "account_id": "account-1",
            "account_data": {"display_name": "Acme Updated"},
        },
        (
            ExpectedCall(
                "GET",
                "/accounts/account-1",
                response={
                    "id": "account-1",
                    "display_name": "Acme",
                    "notes": "keep",
                },
            ),
            ExpectedCall(
                "PUT",
                "/accounts",
                params={"id": "account-1"},
                json={
                    "id": "account-1",
                    "display_name": "Acme Updated",
                    "notes": "keep",
                },
                response={"updated": "account-1", "display_name": "Acme Updated"},
            ),
        ),
    ),
    ToolContract(
        "list_contacts",
        {
            "account_id": "account-1",
            "status": "Active",
            "company_name": "Acme",
            "top": 7,
            "skip": 3,
        },
        (
            ExpectedCall(
                "GET",
                "/contacts",
                params={
                    "$top": 7,
                    "$skip": 3,
                    "account_id": "account-1",
                    "status": "Active",
                    "company_name": "Acme",
                },
                response={"tool": "list_contacts", "items": [1]},
            ),
        ),
    ),
    ToolContract(
        "get_contact",
        {"contact_id": "contact-1"},
        (ExpectedCall("GET", "/contacts/contact-1", response={"id": "contact-1"}),),
    ),
    ToolContract(
        "list_matters",
        {
            "account_id": "account-1",
            "status": "Open",
            "matter_tag": "litigation",
            "top": 7,
            "skip": 3,
            "order_by": "created_at asc",
        },
        (
            ExpectedCall(
                "GET",
                "/matters",
                params={
                    "$top": 7,
                    "$skip": 3,
                    "$orderby": "created_at asc",
                    "account_id": "account-1",
                    "status": "Open",
                    "matter_tag": "litigation",
                },
                response={"tool": "list_matters", "items": [1]},
            ),
        ),
    ),
    ToolContract(
        "get_matter",
        {"matter_id": "matter-1"},
        (ExpectedCall("GET", "/matters/matter-1", response={"id": "matter-1"}),),
    ),
    ToolContract(
        "create_matter",
        {
            "account_id": "account-1",
            "name": "Estate Planning",
            "status": "Pending",
            "notes": "Initial intake",
            "tags": ["estate"],
            "assigned_to_user_ids": ["user-1", "user-2"],
        },
        (
            ExpectedCall(
                "POST",
                "/matters",
                json={
                    "account_ref": {"id": "account-1"},
                    "name": "Estate Planning",
                    "status": "Pending",
                    "notes": "Initial intake",
                    "tags": ["estate"],
                    "assigned_to_users": [{"id": "user-1"}, {"id": "user-2"}],
                },
                response={"created": "matter-1", "name": "Estate Planning"},
            ),
        ),
    ),
    ToolContract(
        "update_matter",
        {"matter_id": "matter-1", "matter_data": {"name": "Updated Matter"}},
        (
            ExpectedCall(
                "GET",
                "/matters/matter-1",
                response={"id": "matter-1", "name": "Old Matter", "status": "Open"},
            ),
            ExpectedCall(
                "PUT",
                "/matters",
                params={"id": "matter-1"},
                json={
                    "id": "matter-1",
                    "name": "Updated Matter",
                    "status": "Open",
                },
                response={"updated": "matter-1", "name": "Updated Matter"},
            ),
        ),
    ),
    ToolContract(
        "list_tasks",
        {
            "account_id": "account-1",
            "matter_id": "matter-1",
            "status": "InProgress",
            "due_date_from": "2026-07-01T00:00:00+00:00",
            "top": 7,
            "skip": 3,
        },
        (
            ExpectedCall(
                "GET",
                "/tasks",
                params={
                    "$top": 7,
                    "$skip": 3,
                    "account_id": "account-1",
                    "matter_id": "matter-1",
                    "status": "InProgress",
                    "due_date_from": "2026-07-01T00:00:00+00:00",
                },
                response={"tool": "list_tasks", "items": [1]},
            ),
        ),
    ),
    ToolContract(
        "get_task",
        {"task_id": "task-1"},
        (ExpectedCall("GET", "/tasks/task-1", response={"id": "task-1"}),),
    ),
    ToolContract(
        "create_task",
        {
            "subject": "Draft agreement",
            "matter_id": "matter-1",
            "priority": "High",
            "notes": "Use latest template",
            "assigned_to_user_ids": ["user-1"],
        },
        (
            ExpectedCall(
                "POST",
                "/tasks",
                json={
                    "subject": "Draft agreement",
                    "matter_ref": {"id": "matter-1"},
                    "priority": "High",
                    "status": "NotCompleted",
                    "notes": "Use latest template",
                    "assigned_to_users": [{"id": "user-1"}],
                },
                response={"created": "task-1", "subject": "Draft agreement"},
            ),
        ),
    ),
    ToolContract(
        "update_task",
        {"task_id": "task-1", "task_data": {"priority": "Low"}},
        (
            ExpectedCall(
                "GET",
                "/tasks/task-1",
                response={
                    "id": "task-1",
                    "subject": "Draft agreement",
                    "priority": "High",
                    "status": "NotCompleted",
                },
            ),
            ExpectedCall(
                "PUT",
                "/tasks",
                params={"id": "task-1"},
                json={
                    "id": "task-1",
                    "subject": "Draft agreement",
                    "priority": "Low",
                    "status": "NotCompleted",
                },
                response={"updated": "task-1", "priority": "Low"},
            ),
        ),
    ),
    ToolContract(
        "complete_task",
        {"task_id": "task-1"},
        (
            ExpectedCall(
                "GET",
                "/tasks/task-1",
                response={
                    "id": "task-1",
                    "subject": "Draft agreement",
                    "priority": "High",
                    "status": "NotCompleted",
                },
            ),
            ExpectedCall(
                "PUT",
                "/tasks",
                params={"id": "task-1"},
                json={
                    "id": "task-1",
                    "subject": "Draft agreement",
                    "priority": "High",
                    "status": "Completed",
                },
                response={"updated": "task-1", "status": "Completed"},
            ),
        ),
    ),
    ToolContract(
        "list_events",
        {
            "account_id": "account-1",
            "matter_id": "matter-1",
            "date_from": "2026-07-01T00:00:00+00:00",
            "assigned_to_user_id": "user-1",
            "top": 7,
            "skip": 3,
        },
        (
            ExpectedCall(
                "GET",
                "/events",
                params={
                    "$top": 7,
                    "$skip": 3,
                    "account_id": "account-1",
                    "matter_id": "matter-1",
                    "date_from": "2026-07-01T00:00:00+00:00",
                    "assigned_to_user_id": "user-1",
                },
                response={"tool": "list_events", "items": [1]},
            ),
        ),
    ),
    ToolContract(
        "get_event",
        {"event_id": "event-1"},
        (ExpectedCall("GET", "/events/event-1", response={"id": "event-1"}),),
    ),
    ToolContract(
        "create_event",
        {
            "subject": "Client meeting",
            "start_date_time": "2026-07-04T09:00:00+00:00",
            "end_date_time": "2026-07-04T10:00:00+00:00",
            "matter_id": "matter-1",
            "location": "Conference room",
        },
        (
            ExpectedCall(
                "POST",
                "/events",
                json={
                    "subject": "Client meeting",
                    "start_date_time": "2026-07-04T09:00:00+00:00",
                    "end_date_time": "2026-07-04T10:00:00+00:00",
                    "is_all_day": False,
                    "matter_ref": {"id": "matter-1"},
                    "location": "Conference room",
                },
                response={"created": "event-1", "subject": "Client meeting"},
            ),
        ),
    ),
    ToolContract(
        "update_event",
        {"event_id": "event-1", "event_data": {"location": "Room 2"}},
        (
            ExpectedCall(
                "GET",
                "/events/event-1",
                response={
                    "id": "event-1",
                    "subject": "Client meeting",
                    "location": "Room 1",
                },
            ),
            ExpectedCall(
                "PUT",
                "/events",
                params={"id": "event-1"},
                json={
                    "id": "event-1",
                    "subject": "Client meeting",
                    "location": "Room 2",
                },
                response={"updated": "event-1", "location": "Room 2"},
            ),
        ),
    ),
    ToolContract(
        "list_notes",
        {
            "account_id": "account-1",
            "matter_id": "matter-1",
            "date_to": "2026-07-31T00:00:00+00:00",
            "top": 7,
            "skip": 3,
        },
        (
            ExpectedCall(
                "GET",
                "/notes",
                params={
                    "$top": 7,
                    "$skip": 3,
                    "account_id": "account-1",
                    "matter_id": "matter-1",
                    "date_to": "2026-07-31T00:00:00+00:00",
                },
                response={"tool": "list_notes", "items": [1]},
            ),
        ),
    ),
    ToolContract(
        "create_note",
        {"subject": "Intake note", "note": "Client called", "account_id": "account-1"},
        (
            ExpectedCall(
                "POST",
                "/notes",
                json={
                    "subject": "Intake note",
                    "note": "Client called",
                    "account_ref": {"id": "account-1"},
                },
                response={"created": "note-1", "subject": "Intake note"},
            ),
        ),
    ),
    ToolContract(
        "list_time_entries",
        {
            "matter_id": "matter-1",
            "user_id": "user-1",
            "date_from": "2026-07-01T00:00:00+00:00",
            "top": 7,
            "skip": 3,
        },
        (
            ExpectedCall(
                "GET",
                "/timeentries",
                params={
                    "$top": 7,
                    "$skip": 3,
                    "matter_id": "matter-1",
                    "user_id": "user-1",
                    "date_from": "2026-07-01T00:00:00+00:00",
                },
                response={"tool": "list_time_entries", "items": [1]},
            ),
        ),
    ),
    ToolContract(
        "create_time_entry",
        {
            "matter_id": "matter-1",
            "date": "2026-07-04T00:00:00+00:00",
            "hours": 1.5,
            "description": "Drafting",
            "is_billable": False,
        },
        (
            ExpectedCall(
                "GET",
                "/users/me",
                response={
                    "id": "user-1",
                    "display_name": "Alex Lawyer",
                    "email": "alex@example.com",
                },
            ),
            ExpectedCall(
                "POST",
                "/timeentries",
                json={
                    "matter_ref": {"id": "matter-1"},
                    "date": "2026-07-04T00:00:00+00:00",
                    "hours": 1.5,
                    "description": "Drafting",
                    "is_billable": False,
                    "billed_by_user_ref": {
                        "id": "user-1",
                        "display_name": "Alex Lawyer",
                        "email_address": "alex@example.com",
                    },
                },
                response={"created": "timeentry-1", "hours": 1.5},
            ),
        ),
    ),
    ToolContract(
        "list_expenses",
        {
            "account_id": "account-1",
            "matter_id": "matter-1",
            "date_from": "2026-07-01T00:00:00+00:00",
            "top": 7,
            "skip": 3,
        },
        (
            ExpectedCall(
                "GET",
                "/Expenses",
                params={
                    "$top": 7,
                    "$skip": 3,
                    "account_id": "account-1",
                    "matter_id": "matter-1",
                    "date_from": "2026-07-01T00:00:00+00:00",
                },
                response={"tool": "list_expenses", "items": [1]},
            ),
        ),
    ),
    ToolContract(
        "create_expense",
        {
            "matter_id": "matter-1",
            "date": "2026-07-04T00:00:00+00:00",
            "description": "Filing fee",
            "qty": 2.0,
            "price": 15.5,
            "expense_category_id": "category-1",
        },
        (
            ExpectedCall(
                "POST",
                "/Expenses",
                json={
                    "matter_ref": {"id": "matter-1"},
                    "date": "2026-07-04T00:00:00+00:00",
                    "description": "Filing fee",
                    "qty": 2.0,
                    "price": 15.5,
                    "amount": 31.0,
                    "is_billable": True,
                    "expense_category_ref": {"id": "category-1"},
                },
                response={"created": "expense-1", "amount": 31.0},
            ),
        ),
    ),
    ToolContract(
        "list_expense_categories",
        {},
        (
            ExpectedCall(
                "GET",
                "/ExpenseCategories",
                response={"tool": "list_expense_categories", "items": [1]},
            ),
        ),
    ),
    ToolContract(
        "list_flat_fees",
        {
            "account_id": "account-1",
            "matter_id": "matter-1",
            "date_to": "2026-07-31T00:00:00+00:00",
            "top": 7,
            "skip": 3,
        },
        (
            ExpectedCall(
                "GET",
                "/flatfees",
                params={
                    "$top": 7,
                    "$skip": 3,
                    "account_id": "account-1",
                    "matter_id": "matter-1",
                    "date_to": "2026-07-31T00:00:00+00:00",
                },
                response={"tool": "list_flat_fees", "items": [1]},
            ),
        ),
    ),
    ToolContract(
        "list_invoices",
        {
            "account_id": "account-1",
            "matter_id": "matter-1",
            "date_from": "2026-07-01T00:00:00+00:00",
            "top": 7,
            "skip": 3,
        },
        (
            ExpectedCall(
                "GET",
                "/invoices",
                params={
                    "$top": 7,
                    "$skip": 3,
                    "account_id": "account-1",
                    "matter_id": "matter-1",
                    "date_from": "2026-07-01T00:00:00+00:00",
                },
                response={"tool": "list_invoices", "items": [1]},
            ),
        ),
    ),
    ToolContract(
        "list_payments",
        {
            "account_id": "account-1",
            "matter_id": "matter-1",
            "date_to": "2026-07-31T00:00:00+00:00",
            "top": 7,
            "skip": 3,
        },
        (
            ExpectedCall(
                "GET",
                "/payments",
                params={
                    "$top": 7,
                    "$skip": 3,
                    "account_id": "account-1",
                    "matter_id": "matter-1",
                    "date_to": "2026-07-31T00:00:00+00:00",
                },
                response={"tool": "list_payments", "items": [1]},
            ),
        ),
    ),
    ToolContract(
        "list_call_logs",
        {
            "account_id": "account-1",
            "matter_id": "matter-1",
            "date_from": "2026-07-01T00:00:00+00:00",
            "top": 7,
            "skip": 3,
        },
        (
            ExpectedCall(
                "GET",
                "/calllogs",
                params={
                    "$top": 7,
                    "$skip": 3,
                    "account_id": "account-1",
                    "matter_id": "matter-1",
                    "date_from": "2026-07-01T00:00:00+00:00",
                },
                response={"tool": "list_call_logs", "items": [1]},
            ),
        ),
    ),
    ToolContract(
        "create_call_log",
        {
            "subject": "Client call",
            "matter_id": "matter-1",
            "duration": 0.25,
            "call_direction": "Outbound",
            "notes": "Left voicemail",
        },
        (
            ExpectedCall(
                "POST",
                "/calllogs",
                json={
                    "subject": "Client call",
                    "matter_ref": {"id": "matter-1"},
                    "duration": 0.25,
                    "call_direction": "Outbound",
                    "notes": "Left voicemail",
                },
                response={"created": "calllog-1", "subject": "Client call"},
            ),
        ),
    ),
    ToolContract(
        "list_custom_fields",
        {"field_type": "matter"},
        (
            ExpectedCall(
                "GET",
                "/customfields/matter",
                response={"tool": "list_custom_fields", "items": [1]},
            ),
        ),
    ),
    ToolContract(
        "list_tags",
        {"tag_type": "activity"},
        (
            ExpectedCall(
                "GET",
                "/tags/activity",
                response={"tool": "list_tags", "items": [1]},
            ),
        ),
    ),
)


def _invoke_tool(
    client: Any,
    monkeypatch: pytest.MonkeyPatch,
    contract: ToolContract,
) -> tuple[Any, list[dict[str, Any]]]:
    from practicepanther_mcp import server

    calls: list[dict[str, Any]] = []

    def fake_request(method: str, url: str, **kwargs: Any) -> DummyResponse:
        if len(calls) >= len(contract.calls):
            raise AssertionError(f"Unexpected extra request: {method} {url}")
        expected = contract.calls[len(calls)]
        calls.append(
            {
                "method": method,
                "url": url,
                "params": kwargs["params"],
                "json": kwargs["json"],
            }
        )
        return DummyResponse(200, expected.response)

    client.session.request = fake_request
    monkeypatch.setattr(server, "_client", lambda: client)

    result = getattr(server, contract.name)(**contract.args)
    return result, calls


@pytest.mark.parametrize("contract", TOOL_CONTRACTS, ids=lambda c: c.name)
def test_tool_http_method_path_and_serialization(
    client: Any,
    monkeypatch: pytest.MonkeyPatch,
    contract: ToolContract,
) -> None:
    _, calls = _invoke_tool(client, monkeypatch, contract)

    assert len(calls) == len(contract.calls)
    for actual, expected in zip(calls, contract.calls, strict=True):
        assert actual["method"] == expected.method
        assert actual["url"] == expected.url
        assert actual["params"] == expected.params
        assert actual["json"] == expected.json


@pytest.mark.parametrize("contract", TOOL_CONTRACTS, ids=lambda c: c.name)
def test_tool_response_passthrough(
    client: Any,
    monkeypatch: pytest.MonkeyPatch,
    contract: ToolContract,
) -> None:
    result, _ = _invoke_tool(client, monkeypatch, contract)

    assert result == contract.final_response


@pytest.mark.parametrize(
    ("method_name", "path", "resource_id", "current", "overlay", "expected_body"),
    [
        (
            "update_account",
            "/accounts",
            "account-1",
            {"id": "account-1", "display_name": "Old", "notes": "keep"},
            {"display_name": "New"},
            {"id": "account-1", "display_name": "New", "notes": "keep"},
        ),
        (
            "update_matter",
            "/matters",
            "matter-1",
            {"id": "matter-1", "name": "Old", "status": "Open"},
            {"name": "New"},
            {"id": "matter-1", "name": "New", "status": "Open"},
        ),
        (
            "update_task",
            "/tasks",
            "task-1",
            {
                "id": "task-1",
                "subject": "Old",
                "priority": "Medium",
                "status": "NotCompleted",
            },
            {"subject": "New", "priority": "High"},
            {
                "id": "task-1",
                "subject": "New",
                "priority": "High",
                "status": "NotCompleted",
            },
        ),
        (
            "update_event",
            "/events",
            "event-1",
            {"id": "event-1", "subject": "Old", "location": "Room 1"},
            {"location": "Room 2"},
            {"id": "event-1", "subject": "Old", "location": "Room 2"},
        ),
    ],
)
def test_fetch_merge_put_overlay_for_each_update_tool(
    client: Any,
    method_name: str,
    path: str,
    resource_id: str,
    current: dict[str, Any],
    overlay: dict[str, Any],
    expected_body: dict[str, Any],
) -> None:
    calls: list[dict[str, Any]] = []

    def fake_request(method: str, url: str, **kwargs: Any) -> DummyResponse:
        calls.append(
            {
                "method": method,
                "url": url,
                "params": kwargs["params"],
                "json": kwargs["json"],
            }
        )
        if method == "GET":
            return DummyResponse(200, current)
        return DummyResponse(200, {"api": "put-response"})

    client.session.request = fake_request

    assert getattr(client, method_name)(resource_id, overlay) == {"api": "put-response"}
    assert calls == [
        {
            "method": "GET",
            "url": f"{BASE_URL}{path}/{resource_id}",
            "params": None,
            "json": None,
        },
        {
            "method": "PUT",
            "url": f"{BASE_URL}{path}",
            "params": {"id": resource_id},
            "json": expected_body,
        },
    ]


def test_non_200_error_surfaces_response_body(client: Any) -> None:
    def fake_request(method: str, url: str, **kwargs: Any) -> DummyResponse:
        return DummyResponse(500, {"ignored": True}, text="upstream exploded")

    client.session.request = fake_request

    with pytest.raises(RuntimeError, match="500: upstream exploded"):
        client.get("/users/me")


@pytest.mark.parametrize(
    ("method_name", "args", "message"),
    [
        ("list_matters", {"status": "Resolved"}, "status"),
        ("create_matter", {"account_id": "account-1", "name": "X", "status": "Done"}, "status"),
        ("create_task", {"subject": "X", "priority": "Urgent"}, "priority"),
        ("create_call_log", {"subject": "X", "call_direction": "Sideways"}, "call_direction"),
        ("list_tags", {"tag_type": "contact"}, "tag_type"),
    ],
)
def test_enum_validation_rejects_before_http(
    client: Any,
    method_name: str,
    args: dict[str, Any],
    message: str,
) -> None:
    calls = 0

    def fake_request(method: str, url: str, **kwargs: Any) -> DummyResponse:
        nonlocal calls
        calls += 1
        return DummyResponse(200, {})

    client.session.request = fake_request

    with pytest.raises(ValueError, match=message):
        getattr(client, method_name)(**args)
    assert calls == 0
