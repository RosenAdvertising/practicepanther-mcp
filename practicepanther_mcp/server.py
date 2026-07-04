#!/usr/bin/env python3
"""PracticePanther MCP server — law practice management via KISS API v2."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from practicepanther_mcp.client import PracticePantherClient

mcp = FastMCP(
    "practicepanther-mcp",
    instructions=(
        "Access PracticePanther matters, accounts, contacts, tasks, calendar, "
        "notes, time entries, expenses, invoices, payments, activity, and metadata."
    ),
)


def _client() -> PracticePantherClient:
    return PracticePantherClient()


# Identity


@mcp.tool()
def get_current_user() -> dict:
    """Return the currently authenticated PracticePanther user."""

    return _client().get_current_user()


@mcp.tool()
def list_users(email_address: str = "", top: int = 50, skip: int = 0) -> dict:
    """List firm users, optionally filtered by email address."""

    return _client().list_users(email_address=email_address, top=top, skip=skip)


@mcp.tool()
def get_user(user_id: str) -> dict:
    """Get a firm user by UUID."""

    return _client().get_user(user_id)


# Accounts


@mcp.tool()
def list_accounts(
    search_text: str = "",
    assigned_to_user_id: str = "",
    account_tag: str = "",
    created_since: str = "",
    updated_since: str = "",
    top: int = 50,
    skip: int = 0,
    order_by: str = "",
) -> dict:
    """List client accounts with optional filters and OData pagination."""

    return _client().list_accounts(
        search_text=search_text,
        assigned_to_user_id=assigned_to_user_id,
        account_tag=account_tag,
        created_since=created_since,
        updated_since=updated_since,
        top=top,
        skip=skip,
        order_by=order_by,
    )


@mcp.tool()
def get_account(account_id: str) -> dict:
    """Get a client account by UUID."""

    return _client().get_account(account_id)


@mcp.tool()
def create_account(
    display_name: str,
    company_name: str = "",
    address_street_1: str = "",
    address_street_2: str = "",
    address_city: str = "",
    address_state: str = "",
    address_country: str = "",
    address_zip_code: str = "",
    notes: str = "",
    tags: list[str] | None = None,
    primary_contact: dict[str, Any] | None = None,
) -> dict:
    """Create a client account, optionally with company details and a primary contact."""

    return _client().create_account(
        display_name=display_name,
        company_name=company_name,
        address_street_1=address_street_1,
        address_street_2=address_street_2,
        address_city=address_city,
        address_state=address_state,
        address_country=address_country,
        address_zip_code=address_zip_code,
        notes=notes,
        tags=tags,
        primary_contact=primary_contact,
    )


@mcp.tool()
def update_account(account_id: str, account_data: dict) -> dict:
    """Update an account by fetching the current object, overlaying fields, and PUTting the full body."""

    return _client().update_account(account_id, account_data)


# Contacts


@mcp.tool()
def list_contacts(
    account_id: str = "",
    search_text: str = "",
    status: str = "",
    company_name: str = "",
    top: int = 50,
    skip: int = 0,
) -> dict:
    """List contacts with optional account, search, status, and company filters."""

    return _client().list_contacts(
        account_id=account_id,
        search_text=search_text,
        status=status,
        company_name=company_name,
        top=top,
        skip=skip,
    )


@mcp.tool()
def get_contact(contact_id: str) -> dict:
    """Get a contact by UUID."""

    return _client().get_contact(contact_id)


# Matters


@mcp.tool()
def list_matters(
    account_id: str = "",
    status: str = "",
    search_text: str = "",
    assigned_to_user_id: str = "",
    matter_tag: str = "",
    top: int = 50,
    skip: int = 0,
    order_by: str = "",
) -> dict:
    """List legal matters with optional filters and OData pagination."""

    return _client().list_matters(
        account_id=account_id,
        status=status,
        search_text=search_text,
        assigned_to_user_id=assigned_to_user_id,
        matter_tag=matter_tag,
        top=top,
        skip=skip,
        order_by=order_by,
    )


@mcp.tool()
def get_matter(matter_id: str) -> dict:
    """Get a legal matter by UUID."""

    return _client().get_matter(matter_id)


@mcp.tool()
def create_matter(
    account_id: str,
    name: str,
    status: str = "Open",
    notes: str = "",
    rate: str = "",
    open_date: str = "",
    close_date: str = "",
    statute_of_limitation_date: str = "",
    tags: list[str] | None = None,
    assigned_to_user_ids: list[str] | None = None,
) -> dict:
    """Create a matter for an account. status: Closed, Pending, Open, or Archived."""

    return _client().create_matter(
        account_id=account_id,
        name=name,
        status=status,
        notes=notes,
        rate=rate,
        open_date=open_date,
        close_date=close_date,
        statute_of_limitation_date=statute_of_limitation_date,
        tags=tags,
        assigned_to_user_ids=assigned_to_user_ids,
    )


@mcp.tool()
def update_matter(matter_id: str, matter_data: dict) -> dict:
    """Update a matter by fetching the current object, overlaying fields, and PUTting the full body."""

    return _client().update_matter(matter_id, matter_data)


# Tasks


@mcp.tool()
def list_tasks(
    account_id: str = "",
    matter_id: str = "",
    status: str = "",
    assigned_to_user_id: str = "",
    due_date_from: str = "",
    due_date_to: str = "",
    top: int = 50,
    skip: int = 0,
) -> dict:
    """List tasks with optional filters. status: NotCompleted, InProgress, Completed, or Conditional."""

    return _client().list_tasks(
        account_id=account_id,
        matter_id=matter_id,
        status=status,
        assigned_to_user_id=assigned_to_user_id,
        due_date_from=due_date_from,
        due_date_to=due_date_to,
        top=top,
        skip=skip,
    )


@mcp.tool()
def get_task(task_id: str) -> dict:
    """Get a task by UUID."""

    return _client().get_task(task_id)


@mcp.tool()
def create_task(
    subject: str,
    matter_id: str = "",
    account_id: str = "",
    due_date: str = "",
    priority: str = "Medium",
    notes: str = "",
    assigned_to_user_ids: list[str] | None = None,
) -> dict:
    """Create a task. priority: Low, Medium, or High."""

    return _client().create_task(
        subject=subject,
        matter_id=matter_id,
        account_id=account_id,
        due_date=due_date,
        priority=priority,
        notes=notes,
        assigned_to_user_ids=assigned_to_user_ids,
    )


@mcp.tool()
def update_task(task_id: str, task_data: dict) -> dict:
    """Update a task by fetching the current object, overlaying fields, and PUTting the full body."""

    return _client().update_task(task_id, task_data)


@mcp.tool()
def complete_task(task_id: str) -> dict:
    """Mark a task as completed."""

    return _client().complete_task(task_id)


# Events


@mcp.tool()
def list_events(
    account_id: str = "",
    matter_id: str = "",
    date_from: str = "",
    date_to: str = "",
    assigned_to_user_id: str = "",
    top: int = 50,
    skip: int = 0,
) -> dict:
    """List calendar events with optional matter, account, date, and user filters."""

    return _client().list_events(
        account_id=account_id,
        matter_id=matter_id,
        date_from=date_from,
        date_to=date_to,
        assigned_to_user_id=assigned_to_user_id,
        top=top,
        skip=skip,
    )


@mcp.tool()
def get_event(event_id: str) -> dict:
    """Get a calendar event by UUID."""

    return _client().get_event(event_id)


@mcp.tool()
def create_event(
    subject: str,
    start_date_time: str,
    end_date_time: str,
    is_all_day: bool = False,
    matter_id: str = "",
    account_id: str = "",
    location: str = "",
    notes: str = "",
) -> dict:
    """Create a calendar event using ISO 8601 date-time values."""

    return _client().create_event(
        subject=subject,
        start_date_time=start_date_time,
        end_date_time=end_date_time,
        is_all_day=is_all_day,
        matter_id=matter_id,
        account_id=account_id,
        location=location,
        notes=notes,
    )


@mcp.tool()
def update_event(event_id: str, event_data: dict) -> dict:
    """Update an event by fetching the current object, overlaying fields, and PUTting the full body."""

    return _client().update_event(event_id, event_data)


# Notes


@mcp.tool()
def list_notes(
    account_id: str = "",
    matter_id: str = "",
    date_from: str = "",
    date_to: str = "",
    top: int = 50,
    skip: int = 0,
) -> dict:
    """List notes with optional matter, account, and date filters."""

    return _client().list_notes(
        account_id=account_id,
        matter_id=matter_id,
        date_from=date_from,
        date_to=date_to,
        top=top,
        skip=skip,
    )


@mcp.tool()
def create_note(
    subject: str,
    note: str,
    matter_id: str = "",
    account_id: str = "",
) -> dict:
    """Create a note linked to a matter or account."""

    return _client().create_note(
        subject=subject,
        note=note,
        matter_id=matter_id,
        account_id=account_id,
    )


# Time entries and billing reads


@mcp.tool()
def list_time_entries(
    account_id: str = "",
    matter_id: str = "",
    user_id: str = "",
    date_from: str = "",
    date_to: str = "",
    top: int = 50,
    skip: int = 0,
) -> dict:
    """List hourly time entries with optional account, matter, user, and date filters."""

    return _client().list_time_entries(
        account_id=account_id,
        matter_id=matter_id,
        user_id=user_id,
        date_from=date_from,
        date_to=date_to,
        top=top,
        skip=skip,
    )


@mcp.tool()
def create_time_entry(
    matter_id: str,
    date: str,
    hours: float,
    description: str,
    rate: float | None = None,
    is_billable: bool = True,
) -> dict:
    """Create a billable or non-billable hourly time entry for a matter."""

    return _client().create_time_entry(
        matter_id=matter_id,
        date=date,
        hours=hours,
        description=description,
        rate=rate,
        is_billable=is_billable,
    )


@mcp.tool()
def list_expenses(
    account_id: str = "",
    matter_id: str = "",
    date_from: str = "",
    date_to: str = "",
    top: int = 50,
    skip: int = 0,
) -> dict:
    """List expenses using the mixed-case PracticePanther Expenses path."""

    return _client().list_expenses(
        account_id=account_id,
        matter_id=matter_id,
        date_from=date_from,
        date_to=date_to,
        top=top,
        skip=skip,
    )


@mcp.tool()
def create_expense(
    matter_id: str,
    date: str,
    description: str,
    qty: float = 1.0,
    price: float = 0.0,
    is_billable: bool = True,
    expense_category_id: str = "",
) -> dict:
    """Create an expense for a matter using the mixed-case PracticePanther Expenses path."""

    return _client().create_expense(
        matter_id=matter_id,
        date=date,
        description=description,
        qty=qty,
        price=price,
        is_billable=is_billable,
        expense_category_id=expense_category_id,
    )


@mcp.tool()
def list_expense_categories() -> dict:
    """List expense categories using the mixed-case ExpenseCategories path."""

    return _client().list_expense_categories()


@mcp.tool()
def list_flat_fees(
    account_id: str = "",
    matter_id: str = "",
    date_from: str = "",
    date_to: str = "",
    top: int = 50,
    skip: int = 0,
) -> dict:
    """List fixed-fee billing entries."""

    return _client().list_flat_fees(
        account_id=account_id,
        matter_id=matter_id,
        date_from=date_from,
        date_to=date_to,
        top=top,
        skip=skip,
    )


@mcp.tool()
def list_invoices(
    account_id: str = "",
    matter_id: str = "",
    date_from: str = "",
    date_to: str = "",
    top: int = 50,
    skip: int = 0,
) -> dict:
    """List invoices. Invoices are read-only in this MCP server."""

    return _client().list_invoices(
        account_id=account_id,
        matter_id=matter_id,
        date_from=date_from,
        date_to=date_to,
        top=top,
        skip=skip,
    )


@mcp.tool()
def list_payments(
    account_id: str = "",
    matter_id: str = "",
    date_from: str = "",
    date_to: str = "",
    top: int = 50,
    skip: int = 0,
) -> dict:
    """List payments. Payments are read-only in this MCP server."""

    return _client().list_payments(
        account_id=account_id,
        matter_id=matter_id,
        date_from=date_from,
        date_to=date_to,
        top=top,
        skip=skip,
    )


# Activity and metadata


@mcp.tool()
def list_call_logs(
    account_id: str = "",
    matter_id: str = "",
    date_from: str = "",
    date_to: str = "",
    top: int = 50,
    skip: int = 0,
) -> dict:
    """List phone call activity records."""

    return _client().list_call_logs(
        account_id=account_id,
        matter_id=matter_id,
        date_from=date_from,
        date_to=date_to,
        top=top,
        skip=skip,
    )


@mcp.tool()
def create_call_log(
    subject: str,
    matter_id: str = "",
    account_id: str = "",
    date: str = "",
    duration: float = 0.0,
    call_direction: str = "Inbound",
    notes: str = "",
) -> dict:
    """Create a phone call activity record. call_direction: Inbound or Outbound."""

    return _client().create_call_log(
        subject=subject,
        matter_id=matter_id,
        account_id=account_id,
        date=date,
        duration=duration,
        call_direction=call_direction,
        notes=notes,
    )


@mcp.tool()
def list_custom_fields(field_type: str) -> dict:
    """List custom fields for field_type: company, matter, or contact."""

    return _client().list_custom_fields(field_type)


@mcp.tool()
def list_tags(tag_type: str) -> dict:
    """List tags for tag_type: account, matter, or activity."""

    return _client().list_tags(tag_type)


def main() -> None:
    """Run the PracticePanther MCP server over stdio."""

    mcp.run()


if __name__ == "__main__":
    main()
