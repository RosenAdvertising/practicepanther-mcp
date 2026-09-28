# MCP 2026-07-28 migration

PracticePanther MCP targets protocol revision `2026-07-28` with the Python MCP
SDK requirement `mcp>=2.2,<3`. The committed `uv.lock` resolves `mcp` and
`mcp-types` to 2.2.0. The detailed protocol mapping and source citations are in
[the spec delta](SPEC-DELTA-2026-07-28.md).

## Implementation

- The server uses SDK `MCPServer` and retains its stdio entry point, 36 tools,
  three prompts, and three resources. It creates a PracticePanther client for
  each tool or resource call and retains downstream OAuth token refresh.
- Modern clients negotiate `2026-07-28`; SDK legacy mode still negotiates
  `2025-11-25`. Modern discovery, request metadata, result types, private
  zero-TTL cache hints, routing headers, and error codes are covered by
  in-process protocol tests. The package does not expose an HTTP entry point.
- Paginated list tools bound `top` to 1–200, require nonnegative `skip`, expose
  `$orderby`, and default to `id asc`. Each call makes one API request; the
  client does not auto-paginate. Provider rejection logs and exceptions omit
  response bodies and rejected values.
- The application does not implement MCP transport authorization, elicitation,
  subscriptions, or server-initiated requests. Its separate PracticePanther
  OAuth flow is downstream API authorization.

## Reproduce the offline checks

Install the locked development environment, then run the commands below from
the repository root. The test suite blocks `requests` network calls and uses
fake credentials under a temporary config directory.

```bash
uv sync --locked --offline --group dev
test_config_dir=$(mktemp -d)
env -u PP_CLIENT_ID -u PP_CLIENT_SECRET -u PP_REDIRECT_URI \
  -u PP_ACCESS_TOKEN -u PP_REFRESH_TOKEN \
  PP_MCP_CONFIG_DIR="$test_config_dir" .venv/bin/python -m pytest -q
rm -rf "$test_config_dir"
.venv/bin/python tests/spec_check.py --mcp-only
.venv/bin/ruff check .
uv lock --check --offline
```

These checks cover mocked PracticePanther calls and in-process MCP protocol
behavior. They do not establish live API behavior or deployed transport
behavior. The lock checks SDK 2.2.0; other versions permitted by the range
have not been tested here.

## Open product decision

MCP 2.2.0 masks client-visible messages from tool exceptions other than
`ToolError` or `ResourceError`. Keeping that masking limits leakage from
provider and validation failures; explicitly safe `ToolError` messages could
give clients more actionable feedback. Toby should decide which errors, if any,
merit safe client-visible messages. Existing exception handling is unchanged.
