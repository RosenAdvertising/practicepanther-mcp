# MCP specification delta: 2025-11-25 to 2026-07-28

> Integration note (2026-09-28): This is the spec branch's historical delta.
> The integrated `v2-2026-09-28` branch preserves main's
> `mcp>=1.28.1` requirement and resolves `mcp==2.2.0` in `uv.lock`.
> The pre-migration dependency and pin statements below describe the original
> spec branch, not the integrated branch.

Research date: 2026-08-09. Sources are limited to the official MCP
specification and the official MCP Python SDK documentation.

## Current target and migration release

The repository currently targets MCP `2025-11-25`:

- `pyproject.toml` declares an unbounded `mcp>=1.0.0` dependency. The existing
  local lockfile resolves MCP Python SDK `1.28.1`, whose latest protocol is
  `2025-11-25`.
- `practicepanther_mcp/server.py` imports and constructs the v1 `FastMCP`
  surface without overriding protocol negotiation, so the SDK default is
  authoritative.
- The only configured production transport is stdio through `mcp.run()`.
  There is no hosted HTTP entry point, protocol-version guard, or raw-wire
  protocol test.

The official changelog says `2026-07-28` follows `2025-11-25`
([spec changelog](https://modelcontextprotocol.io/specification/2026-07-28/changelog)).
The official SDK migration guide identifies the v2 API changes used below
([Python SDK v1-to-v2 migration guide](https://py.sdk.modelcontextprotocol.io/migration/)).
This migration pins the first SDK v2 release exactly: `mcp==2.0.0`.

Verdicts below mean:

- **AFFECTS-US**: this server exposes or relies on the changed surface. The SDK
  may implement the wire behavior, but the migration must still pin, configure,
  or test it.
- **NOT-APPLICABLE**: the feature or direction is not implemented here. It will
  not be adopted merely because the new revision permits it.

## Protocol negotiation and lifecycle

| Normative change | Verdict | Why |
| --- | --- | --- |
| Protocol-level sessions and `Mcp-Session-Id` are removed for the modern revision; cross-call state must use explicit handles. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#major-changes) | **AFFECTS-US** | The server is request-scoped and derives its PracticePanther client from persisted OAuth credentials on every tool/resource call. It has no MCP session state. Modern conformance must prove no session-header dependency. |
| `initialize` / `notifications/initialized` are removed for modern requests. Each request carries protocol version, client capabilities, and optional client identity in `_meta`; version mismatch uses `UnsupportedProtocolVersionError`. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#major-changes) | **AFFECTS-US** | The stdio server must accept modern self-describing requests. SDK v2 supplies dual-era dispatch, which must retain legacy negotiation. |
| Servers MUST implement `server/discover`, advertising supported versions, capabilities, and identity. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#major-changes) | **AFFECTS-US** | Every modern server needs discovery. The result must describe the existing prompts, resources, and tools without inventing extensions. |
| Every result requires `resultType`, normally `"complete"` or `"input_required"` for MRTR. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#major-changes) | **AFFECTS-US** | Tool, resource, prompt, discovery, and list results are all returned by this server. |
| Server-initiated requests are replaced by Multi Round-Trip Requests (MRTR) using `InputRequiredResult`, `inputRequests`, and retry `inputResponses`. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#major-changes) | **NOT-APPLICABLE** | No tool, prompt, or resource uses sampling, roots, elicitation, or another server-to-client request. |
| `ping`, `logging/setLevel`, and `notifications/roots/list_changed` are removed. Per-request `_meta` log level replaces connection-level protocol logging. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#major-changes) | **NOT-APPLICABLE** | The application implements none of these protocol methods and emits no MCP logging notifications. |

## Transports and notifications

| Normative change | Verdict | Why |
| --- | --- | --- |
| Streamable HTTP POST requests require `Mcp-Method`, plus `Mcp-Name` for named operations; `x-mcp-header` can map selected tool parameters to HTTP headers. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#minor-changes) | **NOT-APPLICABLE** | Production exposes stdio only. Migration tests still exercise the SDK's temporary ASGI app and required routing headers so future HTTP enablement cannot silently regress. No tool parameter adopts `x-mcp-header`. |
| Standalone HTTP GET and resource subscribe/unsubscribe are replaced by opt-in `subscriptions/listen`; request-scoped notifications remain on their request stream. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#major-changes) | **NOT-APPLICABLE** | There is no production HTTP transport, publisher, subscription bus, or custom event store. SDK-managed capability declarations are preserved without adding those features. |
| SSE resumability and redelivery (`Last-Event-ID` and SSE event IDs) are removed. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#major-changes) | **NOT-APPLICABLE** | The server has no SSE transport or event store. |
| Legacy HTTP+SSE is formally deprecated. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#deprecated) | **NOT-APPLICABLE** | The server exposes stdio only. |

## Capabilities and extensions

| Normative change | Verdict | Why |
| --- | --- | --- |
| `ClientCapabilities` and `ServerCapabilities` gain an `extensions` field. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#minor-changes) | **AFFECTS-US** | Discovery exposes the capability model. The server adds no extension and must not advertise one. |
| Experimental core tasks move to `io.modelcontextprotocol/tasks`, replacing `tasks/result` with `tasks/get`, adding `tasks/update`, and removing `tasks/list`. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#major-changes) | **NOT-APPLICABLE** | There are PracticePanther record tools named `list_tasks` and `get_task`, but they are ordinary domain tools, not MCP protocol Tasks handlers. |
| Roots, Sampling, and Logging are deprecated. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#deprecated) | **NOT-APPLICABLE** | None is declared or used. |
| Sampling `includeContext` values `"thisServer"` and `"allServers"` are deprecated. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#deprecated) | **NOT-APPLICABLE** | Sampling is not used. |

## Tools, resources, prompts, and cache semantics

| Normative change | Verdict | Why |
| --- | --- | --- |
| `tools/list`, `prompts/list`, `resources/list`, `resources/templates/list`, and `resources/read` results require `ttlMs` and `cacheScope`. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#minor-changes) | **AFFECTS-US** | The server exposes tools, prompts, and resources. SDK v2's conservative private, zero-TTL defaults preserve the current no-cache posture. |
| Servers SHOULD return `tools/list` in deterministic order. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#minor-changes) | **AFFECTS-US** | The server publishes 36 tools. Existing registration order is stable and will be tested across repeated listings. |
| Tool schemas accept all JSON Schema 2020-12 keywords; structured content may be any JSON value. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#minor-changes) | **AFFECTS-US** | Decorators generate schemas for all 36 tools. SDK v2 owns revised validation; tests must prove object schemas, bounded list inputs, and ordinary JSON tool results still serialize correctly. The server does not opt into structured tool output merely to demonstrate the newly generalized shape. |
| Resource-not-found changes from `-32002` to Invalid Params `-32602`. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#minor-changes) | **AFFECTS-US** | An unknown `practicepanther://` URI must now produce `-32602`. |
| URL-mode elicitation removes its completion notification and `elicitationId`; retries use application `requestState`. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#minor-changes) | **NOT-APPLICABLE** | The server performs no elicitation. |
| Generated schema numeric minimum/maximum/default types are corrected from integer-only to number. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#other-schema-changes) | **NOT-APPLICABLE** | The repository neither vendors the protocol schema nor validates directly against that generated meta-schema. SDK v2 absorbs the correction. |

## Authorization and security

| Normative change | Verdict | Why |
| --- | --- | --- |
| Authorization servers SHOULD return RFC 9207 `iss`, and MCP clients MUST validate it before code redemption. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#minor-changes) | **NOT-APPLICABLE** | This process is a local stdio MCP server. Its separate downstream PracticePanther OAuth setup is not MCP transport authorization. |
| MCP clients performing Dynamic Client Registration must send an appropriate `application_type`. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#minor-changes) | **NOT-APPLICABLE** | This code does not dynamically register an MCP client. |
| Persisted MCP client credentials must be keyed to the authorization-server issuer and never reused at another issuer. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#minor-changes) | **NOT-APPLICABLE** | The server stores only downstream PracticePanther application credentials/tokens, not MCP client registrations. |
| Dynamic Client Registration is deprecated in favor of Client ID Metadata Documents. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#deprecated) | **NOT-APPLICABLE** | The server neither hosts DCR nor acts as a dynamically registered MCP client. |

## Errors, metadata, and observability

| Normative change | Verdict | Why |
| --- | --- | --- |
| MCP reserves `-32020..-32099`; header mismatch, missing capability, and unsupported version are `-32020`, `-32021`, and `-32022`; unknown methods use `-32601`. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#minor-changes) | **AFFECTS-US** | The SDK dispatcher must produce current codes. Raw-wire tests cover reachable header mismatch, unsupported version, unknown method, and resource-not-found paths. |
| `_meta` formally carries W3C `traceparent`, `tracestate`, and `baggage`. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#minor-changes) | **NOT-APPLICABLE** | The application has no MCP `_meta` tracing integration and this migration does not add an observability feature. |

The changelog's governance and SEP-process changes impose no runtime server
requirement and are intentionally omitted from the verdict tables. The formal
feature lifecycle is respected by not adopting deprecated Roots, Sampling,
Logging, HTTP+SSE, or DCR.
