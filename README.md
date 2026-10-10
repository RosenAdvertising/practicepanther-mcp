# PracticePanther MCP server

[![CI](https://github.com/RosenAdvertising/practicepanther-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/RosenAdvertising/practicepanther-mcp/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-F59E0B.svg)](LICENSE)
[![MCP 2026-07-28](https://img.shields.io/badge/MCP-2026--07--28-7C3AED.svg)](https://modelcontextprotocol.io)

Connect Claude and other MCP clients to PracticePanther to manage accounts, matters, tasks, calendar events, and time and billing.

PracticePanther MCP server is a [Model Context Protocol](https://modelcontextprotocol.io) server for PracticePanther, the law practice management platform (KISS API v2). It registers 36 tools that read and write PracticePanther data. It runs over stdio by default, for desktop clients such as Claude Desktop, and offers an opt-in stateless Streamable HTTP mode that implements MCP specification 2026-07-28. PracticePanther credentials stay on the machine that runs the server: they come from the setup command and a private file in your home directory, never from the client. The server intentionally registers no delete tools for legal and financial records.

## Features

- **Accounts and contacts**: list, look up, create and update client accounts, and list and look up contacts.
- **Matters**: list, look up, create and update matters.
- **Tasks**: list, look up, create, update and complete tasks.
- **Calendar**: list, look up, create and update events.
- **Notes**: list and create notes.
- **Time and billing**: list and create time entries and expenses, and list expense categories, flat fees, invoices and payments (invoices and payments are read-only).
- **Activity and metadata**: list and create call logs, and list firm users, custom fields and tags.

## Tools

The server registers 36 tools.

<details>
<summary>All 36 tools</summary>

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

</details>

### Prompts and resources

The server also registers three prompts and three resources.

- Prompt `daily_docket_review` reviews today's and overdue tasks, today's events, and matters needing attention.
- Prompt `new_client_intake(client_name, matter_description)` guides duplicate-safe account and matter intake with initial follow-up work.
- Prompt `billing_hygiene_check` checks recent billing activity for unbilled work, stale WIP, invoices, and payments.
- Resource `practicepanther://users` returns firm users as JSON reference data.
- Resource `practicepanther://reference-data` returns company, matter, and contact custom fields plus account, matter, and activity tags as JSON.
- Resource `practicepanther://security-notes` documents data sensitivity, write scope, OAuth token handling, and prompt-injection risks.

## Requirements

- Python 3.10 or later.
- A PracticePanther account with API access enabled (see [API access](#api-access)).
- An OAuth client ID and client secret from PracticePanther.
- An MCP client such as Claude Desktop.

## Installation

Install [uv](https://docs.astral.sh/uv/), then clone the repository and install its locked dependencies:

```bash
git clone https://github.com/RosenAdvertising/practicepanther-mcp.git
cd practicepanther-mcp
uv sync --locked
```

## Configuration

Register a redirect URI with PracticePanther. The default used by the setup command is:

```text
http://localhost:8123/callback
```

Run the setup command:

```bash
uv run practicepanther-mcp-setup
```

It prompts for your OAuth client ID, client secret and redirect URI (default `http://localhost:8123/callback`), then prints an authorization URL:

```text
https://app.practicepanther.com/oauth/authorize?response_type=code&client_id=...&redirect_uri=...&state=...
```

Open that URL, approve access, and paste the full redirect URL, including its `code` and `state` query parameters, back into the setup prompt. Setup checks that the returned `state` matches the browser authorization flow before it exchanges the code at `https://app.practicepanther.com/oauth/token`; a code alone is rejected. It then saves the credentials and tokens and runs a live verification check.

Check the connection at any time:

```bash
uv run practicepanther-mcp-verify
```

Verification checks `/api/v2/users/me`, then performs non-destructive reads of accounts and matters with `top=1`.

Server messages that say to run `practicepanther-mcp-setup` mean `uv run practicepanther-mcp-setup` from your clone.

Credentials and tokens are stored in `~/.practicepanther-mcp/.env`. The file is written with mode `0600`, and the directory is set to `0700` when possible. On Windows, the file is stored in the user's profile and protected by Windows' default per-user access rules. On POSIX, files are created with `0600` permissions and writes fail closed if private permissions cannot be established.

The server reads these variables. Values set in the process environment take precedence over the file.

| Variable | Required | Default | Purpose |
| --- | --- | --- | --- |
| `PP_CLIENT_ID` | Yes (saved by setup) | From `~/.practicepanther-mcp/.env` | OAuth app client ID. |
| `PP_CLIENT_SECRET` | Yes (saved by setup) | From `~/.practicepanther-mcp/.env` | OAuth app client secret. |
| `PP_ACCESS_TOKEN` | Yes (saved by setup) | From `~/.practicepanther-mcp/.env` | 24-hour access token. |
| `PP_REFRESH_TOKEN` | Yes (saved by setup) | From `~/.practicepanther-mcp/.env` | Refresh token; rotates on every refresh (see [Token refresh](#token-refresh)). |
| `PP_REDIRECT_URI` | No (saved by setup) | `http://localhost:8123/callback` | Registered redirect URI. |
| `PP_MCP_CONFIG_DIR` | No | `~/.practicepanther-mcp` | Directory that holds the `.env` file. |

## Usage with Claude Desktop

Add the server to Claude Desktop's configuration file (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS, `%APPDATA%\Claude\claude_desktop_config.json` on Windows):

```json
{
  "mcpServers": {
    "practicepanther": {
      "command": "uv",
      "args": ["run", "--locked", "--directory", "/absolute/path/to/practicepanther-mcp", "practicepanther-mcp"]
    }
  }
}
```

Replace `/absolute/path/to/practicepanther-mcp` with the path of your clone, then restart Claude Desktop. Any other stdio MCP client uses the same command and arguments.

## HTTP mode

Stdio is the default. Set `PRACTICEPANTHER_MCP_TRANSPORT=streamable-http` to serve the stateless Streamable HTTP transport from MCP specification 2026-07-28 at `/mcp`. Each request stands alone: no initialization handshake and no `Mcp-Session-Id`. Clients on earlier protocol versions are served on the same endpoint.

> **Security: this endpoint has no authentication and no TLS.** Anyone who can reach the port can run every tool, including write tools, with this server's vendor credentials. Keep the default loopback bind (`127.0.0.1`), or put the server behind an authenticating TLS proxy on a private network. `PRACTICEPANTHER_MCP_ALLOWED_HOSTS` and `PRACTICEPANTHER_MCP_ALLOWED_ORIGINS` protect against browser DNS rebinding, not against direct callers. A proxy in front of it needs connection and idle timeouts: a legacy-style `GET /mcp` with `Accept: text/event-stream` holds a stream open until the client disconnects.

| Variable | Default | Purpose |
| --- | --- | --- |
| `PRACTICEPANTHER_MCP_TRANSPORT` | `stdio` | `stdio` or `streamable-http`. An empty value selects `stdio`. |
| `PRACTICEPANTHER_MCP_HOST` | `127.0.0.1` | Bind address. An empty value selects `127.0.0.1`. `127.0.0.1`, `localhost` and `::1` use the SDK's built-in Host and Origin checks; any other value requires `PRACTICEPANTHER_MCP_ALLOWED_HOSTS`. |
| `PORT` | `8080` | Port; must be an integer. |
| `PRACTICEPANTHER_MCP_ALLOWED_HOSTS` | unset | Comma-separated `Host` header values accepted on a non-loopback bind, such as `mcp.example.com:8080` or `mcp.example.com:*`. |
| `PRACTICEPANTHER_MCP_ALLOWED_ORIGINS` | unset | Comma-separated `Origin` values accepted on a non-loopback bind, such as `https://client.example.com`. Requests without an `Origin` header are accepted. |

PracticePanther credentials come from the same configuration as stdio (see [Configuration](#configuration)), never from the request.

```bash
PRACTICEPANTHER_MCP_TRANSPORT=streamable-http PORT=8080 uv run --locked practicepanther-mcp
```

Point the MCP client at `http://127.0.0.1:8080/mcp`. Responses use the SDK's default streaming mode, so a client that disconnects cancels its request.

## Error handling

A failed tool call returns an MCP error result (`isError`) with a fixed message. The server never passes a PracticePanther response body, a request URL, a credential or a rejected input value back to the client.

| Situation | What the tool returns |
| --- | --- |
| Credentials missing | "PracticePanther credentials are missing. Set PP_CLIENT_ID, PP_CLIENT_SECRET, PP_ACCESS_TOKEN, and PP_REFRESH_TOKEN, or run: practicepanther-mcp-setup" |
| Access token expired (HTTP 400 `invalid_grant`) | The server exchanges the refresh token once and repeats the request once. If the refresh fails: "PracticePanther authorization failed. Re-run setup with: practicepanther-mcp-setup". If the repeated request is rejected again: "PracticePanther authorization was rejected. Re-run setup with: practicepanther-mcp-setup" |
| Authorization rejected (HTTP 401) | "PracticePanther authorization was rejected. Re-run setup with: practicepanther-mcp-setup" |
| Access denied (HTTP 403) | "PracticePanther access denied: the connected account lacks permission for this action (or the authorization expired; re-run practicepanther-mcp-setup if so)." |
| Rate limited (HTTP 429) | After the retries below: "PracticePanther rate limit reached. Retry after N seconds." |
| Record not found (HTTP 404) | "PracticePanther record was not found (HTTP 404). Check the record ID." |
| Any other HTTP error | "PracticePanther request failed (HTTP 500: request rejected)." The status varies, and the reason is a fixed phrase such as "invalid request" or "service unavailable". |
| Response that is not valid JSON | "PracticePanther request failed (HTTP 200: response was not valid JSON)." (or "response had an invalid format"). |
| Timeout or connection failure on a read | "PracticePanther request timed out. This read can be retried." or "Could not connect to PracticePanther. This read can be retried." |
| Timeout or connection failure on a write | "PracticePanther request timed out. The outcome of this write is unknown; check whether it completed before retrying." (or "Could not connect to PracticePanther." with the same second sentence). |
| Invalid arguments | A message such as "Invalid argument 'top'; expected an integer from 1 to 200." |
| Anything else | "Error executing tool" followed by the tool name, with no detail. |

Every PracticePanther request has a 30-second timeout. On HTTP 429 the server waits for the `Retry-After` interval (1, 2 and 4 seconds when the header is missing) and retries, up to 3 times per request and 60 seconds of total waiting; if the next wait would exceed what is left, the tool returns the rate-limit message at once. The server does not retry timeouts, connection failures or 5xx responses. A failed resource read returns the same classified message, or "PracticePanther resource read failed."

At startup the server exits with a message on stderr and a non-zero status when `PRACTICEPANTHER_MCP_TRANSPORT` is neither `stdio` nor `streamable-http`, when `PORT` is not an integer, or when a non-loopback `PRACTICEPANTHER_MCP_HOST` is set without `PRACTICEPANTHER_MCP_ALLOWED_HOSTS`.

## API access

PracticePanther grants API access case by case. Request access through the PracticePanther in-app support chat: **Support**, then **Ask us Anything**. After approval, PracticePanther provides or enables access to an OAuth Client ID and Client Secret.

Verification uses the account associated with the OAuth grant.

## Token refresh

PracticePanther returns `400 {"error":"invalid_grant"}` when the access token needs refresh. The client exchanges the refresh token once, saves the new `PP_ACCESS_TOKEN` and `PP_REFRESH_TOKEN`, updates the bearer header, and retries the original request once.

Refresh tokens rotate on every refresh. Always keep the most recent `PP_REFRESH_TOKEN`; older refresh tokens are spent.

The API documentation has a lifetime discrepancy: the main docs say refresh tokens are valid for at least 14 days, while a support article describes up to 60 days or until used. The client assumes neither duration in code; if a refresh fails, re-run setup.

## API notes

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
  client reports status and safe reason text without exposing response bodies.
- CORS restrictions are irrelevant to this server; direct browser calls to PracticePanther should not be proxied through this package.

## Testing

The test suite runs offline and needs no PracticePanther account: every PracticePanther API call is answered by a test double for the `requests` session, and the suite blocks real network calls. It covers each tool's request and response contract, the fetch-merge-update flow, OData paging limits, token refresh and rate-limit handling, input and path-identifier validation, error handling, credential file handling, the stdio server, and the Streamable HTTP transport including the 2026-07-28 wire format, Host and Origin checks and stateless requests.

```bash
uv sync --locked
uv run --locked pytest -q
```

CI runs the suite on every push and pull request to `main`.

The tools follow PracticePanther's published API documentation and have not yet been run against a live PracticePanther account.

## License

MIT. See [LICENSE](LICENSE).
