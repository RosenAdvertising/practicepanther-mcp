# MCP 2026-07-28 migration report

## Result

`practicepanther-mcp` now targets MCP `2026-07-28`, up from `2025-11-25`.
The direct Python SDK dependency changed from an unbounded `mcp>=1.0.0`
constraint (locally locked to `1.28.1`) to the exact migration release
`mcp==2.0.0`. The committed lockfile includes the SDK v2 dependency split,
including `mcp-types==2.0.0`.

The authoritative per-change classification and citations are in
[`SPEC-DELTA-2026-07-28.md`](SPEC-DELTA-2026-07-28.md). This was a migration,
not a no-op: the repository used the v1 `FastMCP` class and had no protocol
guard or modern wire tests before this branch.

No deployment, live PracticePanther account, credential store, or external
service was touched. Nothing was pushed.

## Implementation

- Replaced the v1 `FastMCP` surface with SDK v2 `MCPServer` while preserving
  the existing 36 tools, three prompts, three resources, and stdio entry point.
- Preserved the request-scoped PracticePanther client, downstream OAuth token
  refresh/persistence, stateless application behavior, and no-cache posture.
- Pinned `mcp==2.0.0`, refreshed and committed `uv.lock`, and installed the
  migrated environment from the lock.
- Added a locked development group for pytest and Ruff, with a Python 3.10 core
  Ruff policy matching the package's declared floor. The pre-existing
  multiline f-string in the OAuth setup CLI was mechanically rewritten so it
  parses on Python 3.10; its generated authorization URL is unchanged.
- Kept SDK v2's dual-era behavior: modern clients negotiate `2026-07-28`, and
  legacy-mode clients continue to negotiate `2025-11-25`.
- Kept production transport scope at stdio. The modern Streamable HTTP wire
  behavior is tested through an in-process SDK ASGI app but is not exposed by
  the package entry point.

## AFFECTS-US handling

| Item | Handling |
| --- | --- |
| Modern stateless requests and removal of modern initialize | SDK v2 dual-era dispatcher; modern raw requests require per-request version/capability metadata, while a legacy client regression retains the older negotiation path. |
| Required `server/discover` | Raw-wire test asserts version, server identity, existing capabilities, private zero-TTL cache hints, and no unused extension. |
| Required `resultType` | Discovery, all list categories, resource reads, and tool calls assert `resultType: complete`. |
| Modern HTTP routing headers | Temporary ASGI wire tests require `MCP-Protocol-Version`, `Mcp-Method`, and `Mcp-Name`, and assert header mismatch `-32020`. Production remains stdio-only. |
| Cacheable list/read results | SDK v2 private `ttlMs: 0` defaults are asserted for tools, prompts, resources, templates, discovery, and resource reads. |
| Deterministic tools | Two independent `tools/list` requests return the same 36 names in registration order. |
| JSON Schema 2020-12 | Generated object input schemas and the bounded list controls are asserted. The server keeps ordinary JSON tool results and does not add structured-output behavior solely to demonstrate the generalized optional shape. |
| Resource-not-found `-32602` | Unknown `practicepanther://` URI regression asserts Invalid Params. |
| New reserved error allocation | Header mismatch `-32020`, unsupported version `-32022`, unknown method `-32601`, and resource invalid params `-32602` are asserted on the wire. No repository operation requires a new optional client capability, so `-32021` is not manufactured. |

## Canary checks

### A. List-tool limit and order — FIXED

Thirteen paginated list tools previously exposed unbounded integer `top`
parameters. Eleven of them also lacked an ordering control; accounts and
matters exposed one but defaulted to the vendor order. There is no client-side
auto-pagination in this repository, so `top` already maps to exactly one API
request rather than becoming a page size across multiple pages.

The migration now:

- schema-enforces `top` from 1 through 200 and `skip >= 0`;
- re-validates those bounds in the direct client path;
- exposes and forwards `$orderby` on all thirteen paginated tools;
- defaults each paginated call to deterministic `id asc`; and
- tests schemas, invalid values, custom order forwarding, one-request behavior,
  and every existing tool HTTP contract.

`list_expense_categories`, `list_custom_fields`, and `list_tags` are vendor
reference endpoints with no pagination arguments or client auto-pagination,
so there was no limit/order surface to repair.

### B. Silent rejections — FIXED

Enum guards, list bounds, missing credentials, malformed/non-JSON provider
responses, failed token refresh, upstream API rejection, and invalid update
source shapes now emit a reason-category log before rejecting. Logs contain
only static reason text, safe field labels, event labels, and status codes;
they do not include rejected values, resource IDs, response bodies, names,
emails, or tokens. The interactive setup CLI's existing validation paths
continue to print explicit PII-free reasons before exit.

### C. Origin/CSP ceremony — N/A

This repository exposes stdio only and serves no browser page or hosted setup
ceremony, so the Sec-Fetch-Site fallback and CSP handoff patterns do not apply.

### D. PII in logs — FIXED

The sweep found three output risks:

- setup verification printed the authenticated user's display name or email;
- incomplete token exchange output printed the entire token response; and
- provider response bodies were embedded in exceptions that could reach SDK
  error logging.

Verification now reports only that authentication succeeded, setup failures
do not print token response bodies, and client errors/logs retain only safe
status/reason data. Regression tests inject name/email text into rejected
values and provider bodies and prove it reaches neither logs nor exceptions.

## Verification

- Before migration: `uv run --frozen pytest -q` — **99 passed**.
- After migration: `uv run --frozen pytest -q` — **139 passed**.
- Protocol guard: `uv run --frozen python tests/spec_check.py --mcp-only` —
  **PASS**, exact revision `2026-07-28`.
- Ruff: `uv run --frozen ruff check .` — **all checks passed**.
- Python bytecode compilation for package and tests — **passed**.

The seven modern protocol tests cover the SDK/spec guard, discovery,
sessionless modern requests, modern and legacy negotiation, all cacheable list
categories, deterministic tools and input schemas, resource read/not-found,
ordinary JSON tool results, required HTTP routing headers, and current error
codes. Canary regressions cover all thirteen paginated tools and PII-free
rejection behavior.

## Remaining verification boundary

No live PracticePanther credentials were required or used. OAuth refresh and
API method/serialization behavior are covered by offline mocks, but this branch
was not live-tested against a PracticePanther account. Live account smoke
testing remains an owner handoff item.

The runtime sandbox denied writes to the repository's original `.git`
directory. Commits were therefore built in the authorized alternate Git
database. A verified portable bundle is exported separately and must be
imported to install the local `spec-2026-07-28` branch in the original Git
database.
