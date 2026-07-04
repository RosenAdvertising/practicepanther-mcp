# practicepanther-mcp

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-F59E0B.svg)](https://opensource.org/licenses/MIT)
[![MCP](https://img.shields.io/badge/MCP-compatible-7C3AED.svg)](https://modelcontextprotocol.io)

MCP server for PracticePanther KISS API v2: law practice management accounts,
contacts, matters, tasks, calendar events, notes, time entries, billing reads,
activity, and metadata.

## Requirements

- Python 3.10+
- A PracticePanther account with API access enabled
- OAuth Client ID and Client Secret from PracticePanther
- Claude Desktop or another MCP-compatible client

## API Access

PracticePanther grants API access case by case. Request access through the
PracticePanther in-app support chat: **Support** -> **Ask us Anything**. After
approval, PracticePanther provides or enables access to an OAuth Client ID and
Client Secret.

There is no documented sandbox. Verification uses the live account associated
with the OAuth grant.

## Installation

From this repository:

```bash
pip install -e .
```

From a built wheel:

```bash
pip install dist/practicepanther_mcp-0.1.0-py3-none-any.whl
```

## Setup

Register a redirect URI with PracticePanther. The default used by the setup
command is:

```text
http://localhost:8123/callback
```

Run the setup command:

```bash
practicepanther-mcp-setup
```

The setup command prompts for:

| Variable | Description |
| --- | --- |
| `PP_CLIENT_ID` | PracticePanther OAuth client ID |
| `PP_CLIENT_SECRET` | PracticePanther OAuth client secret |
| `PP_REDIRECT_URI` | Registered redirect URI; defaults to `http://localhost:8123/callback` |

It prints an authorization URL:

```text
https://app.practicepanther.com/oauth/authorize?response_type=code&client_id=...&redirect_uri=...&state=...
```

Open that URL, approve access, copy the `code` value from the redirect, and
paste it back into the setup prompt. Setup exchanges the code at
`https://app.practicepanther.com/oauth/token`, saves credentials and tokens, and
runs a live verification check.

## Credential Storage

All credentials and tokens are stored in:

```text
~/.practicepanther-mcp/.env
```

The file is written with mode `0600`; the directory is set to `0700` when
possible.

| Env var | Required | Notes |
| --- | --- | --- |
| `PP_CLIENT_ID` | Yes | OAuth app client ID |
| `PP_CLIENT_SECRET` | Yes | OAuth app client secret |
| `PP_REDIRECT_URI` | Yes | Registered redirect URI |
| `PP_ACCESS_TOKEN` | Yes | 24-hour access token |
| `PP_REFRESH_TOKEN` | Yes | Rotates on every refresh |

Process environment variables override values loaded from the `.env` file.

## Token Refresh

PracticePanther returns `400 {"error":"invalid_grant"}` when the access token
needs refresh. The client automatically exchanges the refresh token once,
persists both the new `PP_ACCESS_TOKEN` and new `PP_REFRESH_TOKEN`, updates the
bearer header, and retries the original request once.

Refresh tokens rotate on every refresh. Always keep the most recent
`PP_REFRESH_TOKEN`; older refresh tokens should be treated as spent.

The API documentation has a lifetime discrepancy: the main docs say refresh
tokens are valid for at least 14 days, while a support article describes up to
60 days or until used. This client assumes neither duration in code and tells
users to re-run setup if refresh fails.

## Verify

```bash
practicepanther-mcp-verify
```

Verification checks `/api/v2/users/me`, then performs non-destructive reads of
accounts and matters with `top=1`.

## Claude Desktop Config

Add this to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "practicepanther": {
      "command": "practicepanther-mcp"
    }
  }
}
```

Restart Claude Desktop after saving the config.

## Tools

The v0.1 scope intentionally excludes delete tools for legal and financial
records.

| Category | Tool | Description |
| --- | --- | --- |
| Identity | `get_current_user` | Get `/users/me` |
| Identity | `list_users` | List firm users by optional email |
| Identity | `get_user` | Get a user by UUID |
| Accounts | `list_accounts` | List client accounts with filters and OData pagination |
| Accounts | `get_account` | Get an account by UUID |
| Accounts | `create_account` | Create an account with optional company/contact fields |
| Accounts | `update_account` | Fetch, merge, and PUT full account body |
| Contacts | `list_contacts` | List/search contacts |
| Contacts | `get_contact` | Get a contact by UUID |
| Matters | `list_matters` | List matters with filters and OData pagination |
| Matters | `get_matter` | Get a matter by UUID |
| Matters | `create_matter` | Create a matter for an account |
| Matters | `update_matter` | Fetch, merge, and PUT full matter body |
| Tasks | `list_tasks` | List tasks with filters |
| Tasks | `get_task` | Get a task by UUID |
| Tasks | `create_task` | Create a task |
| Tasks | `update_task` | Fetch, merge, and PUT full task body |
| Tasks | `complete_task` | Mark a task completed |
| Events | `list_events` | List calendar events |
| Events | `get_event` | Get an event by UUID |
| Events | `create_event` | Create a calendar event |
| Events | `update_event` | Fetch, merge, and PUT full event body |
| Notes | `list_notes` | List notes |
| Notes | `create_note` | Create a note |
| Time & Billing | `list_time_entries` | List hourly time entries |
| Time & Billing | `create_time_entry` | Create a time entry |
| Time & Billing | `list_expenses` | List expenses using `/Expenses` |
| Time & Billing | `create_expense` | Create an expense using `/Expenses` |
| Time & Billing | `list_expense_categories` | List expense categories using `/ExpenseCategories` |
| Time & Billing | `list_flat_fees` | List flat fees |
| Time & Billing | `list_invoices` | List invoices, read-only |
| Time & Billing | `list_payments` | List payments, read-only |
| Activity | `list_call_logs` | List call logs |
| Activity | `create_call_log` | Create a call log |
| Metadata | `list_custom_fields` | List custom fields for `company`, `matter`, or `contact` |
| Metadata | `list_tags` | List tags for `account`, `matter`, or `activity` |

## API Notes

- Base URL: `https://app.practicepanther.com/api/v2/`
- OAuth token URL: `https://app.practicepanther.com/oauth/token`
- Scope: `full`
- Every API request uses `Authorization: Bearer <PP_ACCESS_TOKEN>`.
- List tools send OData pagination params as `$top`, `$skip`, and `$orderby`
  where supported by the tool.
- PUT endpoints pass the UUID as a query parameter: `PUT /api/v2/accounts?id=...`.
  The body is the full merged resource object.
- Mixed-case paths are preserved exactly: `/Expenses`, `/ExpenseCategories`,
  and API docs also define `/Items`.
- Dates should be ISO 8601 UTC with offset, for example
  `2018-03-12T00:00:00+00:00`.
- Rate limits are undocumented. The client handles `429` defensively with
  exponential backoff and up to three retries.
- Error body shapes beyond `{"error":"invalid_grant"}` are undocumented. The
  client surfaces the raw response body in API exceptions.
- CORS restrictions are irrelevant to this stdio MCP server; direct browser
  calls to PracticePanther should not be proxied through this package.

## Development

Tests mock all HTTP and must not call the live API.

```bash
uv run --with pytest pytest -q
uv build
```

MCP certification uses a private cert pack outside this public repo. From that
cert-pack directory, run the offline tiers:

```bash
uv run \
  --with-editable /Users/tobyrosen/Cowork/RA-Projects/mcp-test-kit \
  --with-editable /path/to/practicepanther-mcp \
  --with pytest \
  mcp-test-kit run --tier contract --config config.py

uv run \
  --with-editable /Users/tobyrosen/Cowork/RA-Projects/mcp-test-kit \
  --with-editable /path/to/practicepanther-mcp \
  --with pytest \
  mcp-test-kit run --tier static --config config.py

uv run \
  --with-editable /Users/tobyrosen/Cowork/RA-Projects/mcp-test-kit \
  --with-editable /path/to/practicepanther-mcp \
  --with pytest \
  mcp-test-kit run --tier secrets --config config.py

uv run \
  --with-editable /Users/tobyrosen/Cowork/RA-Projects/mcp-test-kit \
  --with-editable /path/to/practicepanther-mcp \
  --with pytest \
  mcp-test-kit run --tier coverage --config config.py
```

Smoke and write tiers are configured in the private cert pack but are not run
until live PracticePanther OAuth keys and seed data are available.

## License

MIT
