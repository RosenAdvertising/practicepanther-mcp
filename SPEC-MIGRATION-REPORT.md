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

## Error behavior

Tool calls return expected credential, authorization, validation, not-found,
vendor rejection, rate-limit, and transport failures as MCP tool errors. The
server exposes only fixed or explicitly safe client messages; unexpected
exception text and provider response prose are masked. Resource read failures
are converted to safe resource errors before the SDK logs them. Timeout and
connection failures for writes explain that completion is unknown and advise
checking the result before retrying; read failures can be retried. HTTP 403
reports missing account permission or expired authorization, while HTTP 401
directs the user to reauthorize.
