from __future__ import annotations

import pytest

from practicepanther_mcp import credentials
from practicepanther_mcp.client import REAUTH_MESSAGE

from conftest import DummyResponse


def test_bearer_header_on_requests(client):
    calls = []

    def fake_request(method, url, **kwargs):
        calls.append(
            {
                "method": method,
                "url": url,
                "headers": dict(client.session.headers),
                "kwargs": kwargs,
            }
        )
        return DummyResponse(200, {"ok": True})

    client.session.request = fake_request

    assert client.get("/users/me") == {"ok": True}
    assert calls[0]["headers"]["Authorization"] == "Bearer old-access"
    assert calls[0]["headers"]["Accept"] == "application/json"


def test_odata_params_serialized(client):
    calls = []

    def fake_request(method, url, **kwargs):
        calls.append({"url": url, "params": kwargs["params"]})
        return DummyResponse(200, [])

    client.session.request = fake_request

    client.list_accounts(
        search_text="smith",
        top=25,
        skip=50,
        order_by="updated_at desc",
    )

    assert calls[0]["url"].endswith("/api/v2/accounts")
    assert calls[0]["params"] == {
        "$top": 25,
        "$skip": 50,
        "$orderby": "updated_at desc",
        "search_text": "smith",
    }


def test_put_sends_id_query_param_and_full_body(client):
    calls = []
    body = {"id": "account-1", "display_name": "Acme"}

    def fake_request(method, url, **kwargs):
        calls.append(
            {
                "method": method,
                "url": url,
                "params": kwargs["params"],
                "json": kwargs["json"],
            }
        )
        return DummyResponse(200, {"updated": True})

    client.session.request = fake_request

    assert client.put_with_id("/accounts", "account-1", body) == {"updated": True}
    assert calls[0]["method"] == "PUT"
    assert calls[0]["url"].endswith("/api/v2/accounts")
    assert calls[0]["params"] == {"id": "account-1"}
    assert calls[0]["json"] == body


def test_invalid_grant_refresh_persists_rotated_tokens_and_retries(
    client, monkeypatch
):
    calls = []

    def fake_request(method, url, **kwargs):
        calls.append(
            {
                "url": url,
                "auth": client.session.headers["Authorization"],
                "params": kwargs["params"],
            }
        )
        if len(calls) == 1:
            return DummyResponse(400, {"error": "invalid_grant"})
        return DummyResponse(200, {"retried": True})

    refresh_calls = []

    def fake_post(url, data, timeout):
        refresh_calls.append({"url": url, "data": data, "timeout": timeout})
        return DummyResponse(
            200,
            {
                "access_token": "new-access",
                "refresh_token": "new-refresh",
                "token_type": "bearer",
                "expires_in": 86399,
            },
        )

    client.session.request = fake_request
    monkeypatch.setattr("practicepanther_mcp.client.requests.post", fake_post)

    assert client.get("/users/me", params={"x": "y"}) == {"retried": True}
    assert len(calls) == 2
    assert calls[0]["auth"] == "Bearer old-access"
    assert calls[1]["auth"] == "Bearer new-access"
    assert calls[1]["params"] == {"x": "y"}
    assert refresh_calls[0]["data"]["grant_type"] == "refresh_token"
    assert refresh_calls[0]["data"]["refresh_token"] == "old-refresh"

    saved = credentials._parse_env_file()
    assert saved["PP_ACCESS_TOKEN"] == "new-access"
    assert saved["PP_REFRESH_TOKEN"] == "new-refresh"


def test_refresh_failure_raises_rerun_setup_error(client, monkeypatch):
    def fake_request(method, url, **kwargs):
        return DummyResponse(400, {"error": "invalid_grant"})

    def fake_post(url, data, timeout):
        return DummyResponse(400, {"error": "invalid_grant"}, text="bad refresh")

    client.session.request = fake_request
    monkeypatch.setattr("practicepanther_mcp.client.requests.post", fake_post)

    with pytest.raises(RuntimeError, match="practicepanther-mcp-setup") as exc:
        client.get("/users/me")
    assert REAUTH_MESSAGE in str(exc.value)


def test_fetch_merge_put_overlay_logic(client):
    calls = []

    def fake_request(method, url, **kwargs):
        calls.append(
            {
                "method": method,
                "url": url,
                "params": kwargs["params"],
                "json": kwargs["json"],
            }
        )
        if method == "GET":
            return DummyResponse(
                200,
                {
                    "id": "matter-1",
                    "name": "Old name",
                    "status": "Open",
                    "notes": "keep",
                },
            )
        return DummyResponse(200, kwargs["json"])

    client.session.request = fake_request

    result = client.update_matter("matter-1", {"name": "New name"})

    assert result == {
        "id": "matter-1",
        "name": "New name",
        "status": "Open",
        "notes": "keep",
    }
    assert calls[0]["method"] == "GET"
    assert calls[0]["url"].endswith("/api/v2/matters/matter-1")
    assert calls[1]["method"] == "PUT"
    assert calls[1]["url"].endswith("/api/v2/matters")
    assert calls[1]["params"] == {"id": "matter-1"}


def test_mixed_case_paths_are_exact(client):
    urls = []

    def fake_request(method, url, **kwargs):
        urls.append((method, url))
        return DummyResponse(200, [])

    client.session.request = fake_request

    client.list_expenses(top=1)
    client.create_expense("matter-1", "2026-07-04T00:00:00+00:00", "Filing")
    client.list_expense_categories()

    assert urls[0] == ("GET", "https://app.practicepanther.com/api/v2/Expenses")
    assert urls[1] == ("POST", "https://app.practicepanther.com/api/v2/Expenses")
    assert urls[2] == (
        "GET",
        "https://app.practicepanther.com/api/v2/ExpenseCategories",
    )


def test_enum_validation_blocks_invalid_values_before_http(client):
    with pytest.raises(ValueError, match="priority"):
        client.create_task("Draft", priority="Urgent")

    with pytest.raises(ValueError, match="status"):
        client.update_task("task-1", {"status": "Done"})

    with pytest.raises(ValueError, match="field_type"):
        client.list_custom_fields("case")

    with pytest.raises(ValueError, match="tag_type"):
        client.list_tags("contact")
