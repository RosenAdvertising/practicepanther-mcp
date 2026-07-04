#!/usr/bin/env python3
"""PracticePanther API v2 client with OAuth refresh and retry handling."""

from __future__ import annotations

import sys
import time
from typing import Any

import requests

from practicepanther_mcp import credentials

BASE_URL = "https://app.practicepanther.com/api/v2"
TOKEN_URL = "https://app.practicepanther.com/oauth/token"

REAUTH_MESSAGE = (
    "PracticePanther OAuth refresh failed. Re-run setup with: "
    "practicepanther-mcp-setup"
)

TASK_PRIORITIES = {"Low", "Medium", "High"}
TASK_STATUSES = {"NotCompleted", "InProgress", "Completed", "Conditional"}
MATTER_STATUSES = {"Closed", "Pending", "Open", "Archived"}
CALL_DIRECTIONS = {"Inbound", "Outbound"}
CUSTOM_FIELD_TYPES = {"company", "matter", "contact"}
TAG_TYPES = {"account", "matter", "activity"}


def _json_response(resp: requests.Response) -> Any:
    try:
        return resp.json()
    except ValueError as exc:
        raise RuntimeError(
            f"PracticePanther API returned non-JSON ({resp.status_code}): "
            f"{resp.text[:400]}"
        ) from exc


def _retry_after_seconds(resp: requests.Response, attempt: int) -> float:
    retry_after = resp.headers.get("Retry-After")
    if retry_after:
        try:
            return float(retry_after)
        except ValueError:
            pass
    return float(2**attempt)


def _ref(resource_id: str) -> dict[str, str]:
    return {"id": resource_id}


def _user_ref(user: dict[str, Any]) -> dict[str, str]:
    ref = {"id": user.get("id", "")}
    display_name = user.get("display_name")
    email = user.get("email_address") or user.get("email")
    if display_name:
        ref["display_name"] = display_name
    if email:
        ref["email_address"] = email
    return {key: value for key, value in ref.items() if value}


def _validate(value: str, allowed: set[str], field_name: str) -> None:
    if value and value not in allowed:
        valid = ", ".join(sorted(allowed))
        raise ValueError(f"{field_name} must be one of: {valid}")


def _compact(values: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in values.items()
        if value is not None
        and value != ""
        and value != []
        and not (isinstance(value, dict) and not value)
    }


class PracticePantherClient:
    """Small requests-based client for the PracticePanther KISS API v2."""

    def __init__(self) -> None:
        self.creds = credentials.load_credentials()
        if (
            not self.creds.client_id
            or not self.creds.client_secret
            or not self.creds.access_token
            or not self.creds.refresh_token
        ):
            raise RuntimeError(
                "PracticePanther credentials not found. Run: practicepanther-mcp-setup"
            )

        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {self.creds.access_token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )

    def _url(self, path: str) -> str:
        clean = path.lstrip("/")
        if clean.startswith("api/v2/"):
            clean = clean[len("api/v2/") :]
        return f"{BASE_URL}/{clean}"

    def _is_invalid_grant(self, resp: requests.Response) -> bool:
        if resp.status_code != 400:
            return False
        try:
            body = resp.json()
        except ValueError:
            return False
        return body.get("error") == "invalid_grant"

    def _refresh_tokens(self) -> None:
        resp = requests.post(
            TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": self.creds.refresh_token,
                "client_id": self.creds.client_id,
                "client_secret": self.creds.client_secret,
            },
            timeout=30,
        )

        if not resp.ok:
            raise RuntimeError(f"{REAUTH_MESSAGE}. Response: {resp.text[:400]}")

        token_data = _json_response(resp)
        access_token = token_data.get("access_token", "")
        refresh_token = token_data.get("refresh_token", "")
        if not access_token or not refresh_token:
            raise RuntimeError(f"{REAUTH_MESSAGE}. Token response was incomplete.")

        credentials.save_values(
            {
                "PP_CLIENT_ID": self.creds.client_id,
                "PP_CLIENT_SECRET": self.creds.client_secret,
                "PP_REDIRECT_URI": self.creds.redirect_uri,
                "PP_ACCESS_TOKEN": access_token,
                "PP_REFRESH_TOKEN": refresh_token,
            }
        )
        self.creds = credentials.load_credentials()
        self.session.headers["Authorization"] = f"Bearer {self.creds.access_token}"

    def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json_body: Any = None,
        retry_auth: bool = True,
        rate_retries: int = 0,
    ) -> Any:
        resp = self.session.request(
            method,
            self._url(path),
            params=params,
            json=json_body,
            timeout=30,
        )

        if self._is_invalid_grant(resp) and retry_auth:
            self._refresh_tokens()
            return self._request(
                method,
                path,
                params=params,
                json_body=json_body,
                retry_auth=False,
                rate_retries=rate_retries,
            )

        if resp.status_code == 429 and rate_retries < 3:
            wait = _retry_after_seconds(resp, rate_retries)
            print(f"Rate limited. Waiting {wait:g}s...", file=sys.stderr)
            time.sleep(wait)
            return self._request(
                method,
                path,
                params=params,
                json_body=json_body,
                retry_auth=retry_auth,
                rate_retries=rate_retries + 1,
            )

        if not resp.ok:
            raise RuntimeError(
                f"PracticePanther API error {resp.status_code}: {resp.text[:400]}"
            )

        if resp.status_code == 204 or not resp.text:
            return {"success": True}
        return _json_response(resp)

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return self._request("GET", path, params=params)

    def post(self, path: str, body: Any = None) -> Any:
        return self._request("POST", path, json_body=body)

    def put(
        self,
        path: str,
        body: Any = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        return self._request("PUT", path, params=params, json_body=body)

    def put_with_id(self, path: str, resource_id: str, body: dict[str, Any]) -> Any:
        return self.put(path, body=body, params={"id": resource_id})

    def _odata(
        self, top: int = 50, skip: int = 0, order_by: str = ""
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"$top": top, "$skip": skip}
        if order_by:
            params["$orderby"] = order_by
        return params

    def _merge_put(
        self, path: str, resource_id: str, overlay: dict[str, Any]
    ) -> Any:
        current = self.get(f"{path}/{resource_id}")
        if not isinstance(current, dict):
            raise RuntimeError(
                f"Expected object from PracticePanther GET {path}/{resource_id}"
            )
        body = {**current, **overlay}
        return self.put_with_id(path, resource_id, body)

    # Identity

    def get_current_user(self) -> Any:
        return self.get("/users/me")

    def list_users(self, email_address: str = "", top: int = 50, skip: int = 0) -> Any:
        params = self._odata(top=top, skip=skip)
        params.update(_compact({"email_address": email_address}))
        return self.get("/users", params=params)

    def get_user(self, user_id: str) -> Any:
        return self.get(f"/users/{user_id}")

    # Accounts

    def list_accounts(
        self,
        search_text: str = "",
        assigned_to_user_id: str = "",
        account_tag: str = "",
        created_since: str = "",
        updated_since: str = "",
        top: int = 50,
        skip: int = 0,
        order_by: str = "",
    ) -> Any:
        params = self._odata(top=top, skip=skip, order_by=order_by)
        params.update(
            _compact(
                {
                    "search_text": search_text,
                    "assigned_to_user_id": assigned_to_user_id,
                    "account_tag": account_tag,
                    "created_since": created_since,
                    "updated_since": updated_since,
                }
            )
        )
        return self.get("/accounts", params=params)

    def get_account(self, account_id: str) -> Any:
        return self.get(f"/accounts/{account_id}")

    def create_account(
        self,
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
    ) -> Any:
        body = _compact(
            {
                "display_name": display_name,
                "company_name": company_name,
                "address_street_1": address_street_1,
                "address_street_2": address_street_2,
                "address_city": address_city,
                "address_state": address_state,
                "address_country": address_country,
                "address_zip_code": address_zip_code,
                "notes": notes,
                "tags": tags or [],
                "primary_contact": primary_contact,
            }
        )
        return self.post("/accounts", body)

    def update_account(self, account_id: str, account_data: dict[str, Any]) -> Any:
        return self._merge_put("/accounts", account_id, account_data)

    # Contacts

    def list_contacts(
        self,
        account_id: str = "",
        search_text: str = "",
        status: str = "",
        company_name: str = "",
        top: int = 50,
        skip: int = 0,
    ) -> Any:
        params = self._odata(top=top, skip=skip)
        params.update(
            _compact(
                {
                    "account_id": account_id,
                    "search_text": search_text,
                    "status": status,
                    "company_name": company_name,
                }
            )
        )
        return self.get("/contacts", params=params)

    def get_contact(self, contact_id: str) -> Any:
        return self.get(f"/contacts/{contact_id}")

    # Matters

    def list_matters(
        self,
        account_id: str = "",
        status: str = "",
        search_text: str = "",
        assigned_to_user_id: str = "",
        matter_tag: str = "",
        top: int = 50,
        skip: int = 0,
        order_by: str = "",
    ) -> Any:
        if status:
            _validate(status, MATTER_STATUSES, "status")
        params = self._odata(top=top, skip=skip, order_by=order_by)
        params.update(
            _compact(
                {
                    "account_id": account_id,
                    "status": status,
                    "search_text": search_text,
                    "assigned_to_user_id": assigned_to_user_id,
                    "matter_tag": matter_tag,
                }
            )
        )
        return self.get("/matters", params=params)

    def get_matter(self, matter_id: str) -> Any:
        return self.get(f"/matters/{matter_id}")

    def create_matter(
        self,
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
    ) -> Any:
        _validate(status, MATTER_STATUSES, "status")
        body = _compact(
            {
                "account_ref": _ref(account_id),
                "name": name,
                "status": status,
                "notes": notes,
                "rate": rate,
                "open_date": open_date,
                "close_date": close_date,
                "statute_of_limitation_date": statute_of_limitation_date,
                "tags": tags or [],
                "assigned_to_users": [
                    _ref(user_id) for user_id in (assigned_to_user_ids or [])
                ],
            }
        )
        return self.post("/matters", body)

    def update_matter(self, matter_id: str, matter_data: dict[str, Any]) -> Any:
        if "status" in matter_data:
            _validate(str(matter_data["status"]), MATTER_STATUSES, "status")
        return self._merge_put("/matters", matter_id, matter_data)

    # Tasks

    def list_tasks(
        self,
        account_id: str = "",
        matter_id: str = "",
        status: str = "",
        assigned_to_user_id: str = "",
        due_date_from: str = "",
        due_date_to: str = "",
        top: int = 50,
        skip: int = 0,
    ) -> Any:
        if status:
            _validate(status, TASK_STATUSES, "status")
        params = self._odata(top=top, skip=skip)
        params.update(
            _compact(
                {
                    "account_id": account_id,
                    "matter_id": matter_id,
                    "status": status,
                    "assigned_to_user_id": assigned_to_user_id,
                    "due_date_from": due_date_from,
                    "due_date_to": due_date_to,
                }
            )
        )
        return self.get("/tasks", params=params)

    def get_task(self, task_id: str) -> Any:
        return self.get(f"/tasks/{task_id}")

    def create_task(
        self,
        subject: str,
        matter_id: str = "",
        account_id: str = "",
        due_date: str = "",
        priority: str = "Medium",
        notes: str = "",
        assigned_to_user_ids: list[str] | None = None,
    ) -> Any:
        _validate(priority, TASK_PRIORITIES, "priority")
        body = _compact(
            {
                "subject": subject,
                "matter_ref": _ref(matter_id) if matter_id else None,
                "account_ref": _ref(account_id) if account_id else None,
                "due_date": due_date,
                "priority": priority,
                "status": "NotCompleted",
                "notes": notes,
                "assigned_to_users": [
                    _ref(user_id) for user_id in (assigned_to_user_ids or [])
                ],
            }
        )
        return self.post("/tasks", body)

    def update_task(self, task_id: str, task_data: dict[str, Any]) -> Any:
        if "priority" in task_data:
            _validate(str(task_data["priority"]), TASK_PRIORITIES, "priority")
        if "status" in task_data:
            _validate(str(task_data["status"]), TASK_STATUSES, "status")
        return self._merge_put("/tasks", task_id, task_data)

    def complete_task(self, task_id: str) -> Any:
        return self.update_task(task_id, {"status": "Completed"})

    # Events

    def list_events(
        self,
        account_id: str = "",
        matter_id: str = "",
        date_from: str = "",
        date_to: str = "",
        assigned_to_user_id: str = "",
        top: int = 50,
        skip: int = 0,
    ) -> Any:
        params = self._odata(top=top, skip=skip)
        params.update(
            _compact(
                {
                    "account_id": account_id,
                    "matter_id": matter_id,
                    "date_from": date_from,
                    "date_to": date_to,
                    "assigned_to_user_id": assigned_to_user_id,
                }
            )
        )
        return self.get("/events", params=params)

    def get_event(self, event_id: str) -> Any:
        return self.get(f"/events/{event_id}")

    def create_event(
        self,
        subject: str,
        start_date_time: str,
        end_date_time: str,
        is_all_day: bool = False,
        matter_id: str = "",
        account_id: str = "",
        location: str = "",
        notes: str = "",
    ) -> Any:
        body = _compact(
            {
                "subject": subject,
                "start_date_time": start_date_time,
                "end_date_time": end_date_time,
                "is_all_day": is_all_day,
                "matter_ref": _ref(matter_id) if matter_id else None,
                "account_ref": _ref(account_id) if account_id else None,
                "location": location,
                "notes": notes,
            }
        )
        return self.post("/events", body)

    def update_event(self, event_id: str, event_data: dict[str, Any]) -> Any:
        return self._merge_put("/events", event_id, event_data)

    # Notes

    def list_notes(
        self,
        account_id: str = "",
        matter_id: str = "",
        date_from: str = "",
        date_to: str = "",
        top: int = 50,
        skip: int = 0,
    ) -> Any:
        params = self._odata(top=top, skip=skip)
        params.update(
            _compact(
                {
                    "account_id": account_id,
                    "matter_id": matter_id,
                    "date_from": date_from,
                    "date_to": date_to,
                }
            )
        )
        return self.get("/notes", params=params)

    def create_note(
        self, subject: str, note: str, matter_id: str = "", account_id: str = ""
    ) -> Any:
        body = _compact(
            {
                "subject": subject,
                "note": note,
                "matter_ref": _ref(matter_id) if matter_id else None,
                "account_ref": _ref(account_id) if account_id else None,
            }
        )
        return self.post("/notes", body)

    # Time entries and billing

    def list_time_entries(
        self,
        account_id: str = "",
        matter_id: str = "",
        user_id: str = "",
        date_from: str = "",
        date_to: str = "",
        top: int = 50,
        skip: int = 0,
    ) -> Any:
        params = self._odata(top=top, skip=skip)
        params.update(
            _compact(
                {
                    "account_id": account_id,
                    "matter_id": matter_id,
                    "user_id": user_id,
                    "date_from": date_from,
                    "date_to": date_to,
                }
            )
        )
        return self.get("/timeentries", params=params)

    def create_time_entry(
        self,
        matter_id: str,
        date: str,
        hours: float,
        description: str,
        rate: float | None = None,
        is_billable: bool = True,
    ) -> Any:
        current_user = self.get_current_user()
        body = _compact(
            {
                "matter_ref": _ref(matter_id),
                "date": date,
                "hours": hours,
                "description": description,
                "rate": rate,
                "is_billable": is_billable,
                "billed_by_user_ref": _user_ref(current_user),
            }
        )
        return self.post("/timeentries", body)

    def list_expenses(
        self,
        account_id: str = "",
        matter_id: str = "",
        date_from: str = "",
        date_to: str = "",
        top: int = 50,
        skip: int = 0,
    ) -> Any:
        params = self._odata(top=top, skip=skip)
        params.update(
            _compact(
                {
                    "account_id": account_id,
                    "matter_id": matter_id,
                    "date_from": date_from,
                    "date_to": date_to,
                }
            )
        )
        return self.get("/Expenses", params=params)

    def create_expense(
        self,
        matter_id: str,
        date: str,
        description: str,
        qty: float = 1.0,
        price: float = 0.0,
        is_billable: bool = True,
        expense_category_id: str = "",
    ) -> Any:
        body = _compact(
            {
                "matter_ref": _ref(matter_id),
                "date": date,
                "description": description,
                "qty": qty,
                "price": price,
                "amount": qty * price,
                "is_billable": is_billable,
                "expense_category_ref": _ref(expense_category_id)
                if expense_category_id
                else None,
            }
        )
        return self.post("/Expenses", body)

    def list_expense_categories(self) -> Any:
        return self.get("/ExpenseCategories")

    def list_flat_fees(
        self,
        account_id: str = "",
        matter_id: str = "",
        date_from: str = "",
        date_to: str = "",
        top: int = 50,
        skip: int = 0,
    ) -> Any:
        params = self._odata(top=top, skip=skip)
        params.update(
            _compact(
                {
                    "account_id": account_id,
                    "matter_id": matter_id,
                    "date_from": date_from,
                    "date_to": date_to,
                }
            )
        )
        return self.get("/flatfees", params=params)

    def list_invoices(
        self,
        account_id: str = "",
        matter_id: str = "",
        date_from: str = "",
        date_to: str = "",
        top: int = 50,
        skip: int = 0,
    ) -> Any:
        params = self._odata(top=top, skip=skip)
        params.update(
            _compact(
                {
                    "account_id": account_id,
                    "matter_id": matter_id,
                    "date_from": date_from,
                    "date_to": date_to,
                }
            )
        )
        return self.get("/invoices", params=params)

    def list_payments(
        self,
        account_id: str = "",
        matter_id: str = "",
        date_from: str = "",
        date_to: str = "",
        top: int = 50,
        skip: int = 0,
    ) -> Any:
        params = self._odata(top=top, skip=skip)
        params.update(
            _compact(
                {
                    "account_id": account_id,
                    "matter_id": matter_id,
                    "date_from": date_from,
                    "date_to": date_to,
                }
            )
        )
        return self.get("/payments", params=params)

    # Activity and metadata

    def list_call_logs(
        self,
        account_id: str = "",
        matter_id: str = "",
        date_from: str = "",
        date_to: str = "",
        top: int = 50,
        skip: int = 0,
    ) -> Any:
        params = self._odata(top=top, skip=skip)
        params.update(
            _compact(
                {
                    "account_id": account_id,
                    "matter_id": matter_id,
                    "date_from": date_from,
                    "date_to": date_to,
                }
            )
        )
        return self.get("/calllogs", params=params)

    def create_call_log(
        self,
        subject: str,
        matter_id: str = "",
        account_id: str = "",
        date: str = "",
        duration: float = 0.0,
        call_direction: str = "Inbound",
        notes: str = "",
    ) -> Any:
        _validate(call_direction, CALL_DIRECTIONS, "call_direction")
        body = _compact(
            {
                "subject": subject,
                "matter_ref": _ref(matter_id) if matter_id else None,
                "account_ref": _ref(account_id) if account_id else None,
                "date": date,
                "duration": duration,
                "call_direction": call_direction,
                "notes": notes,
            }
        )
        return self.post("/calllogs", body)

    def list_custom_fields(self, field_type: str) -> Any:
        _validate(field_type, CUSTOM_FIELD_TYPES, "field_type")
        return self.get(f"/customfields/{field_type}")

    def list_tags(self, tag_type: str) -> Any:
        _validate(tag_type, TAG_TYPES, "tag_type")
        return self.get(f"/tags/{tag_type}")
