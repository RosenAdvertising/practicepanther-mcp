"""Small CI guard for the repository's supported MCP protocol revision."""

from __future__ import annotations

import argparse

from mcp.types import LATEST_PROTOCOL_VERSION
from mcp_types.version import MODERN_PROTOCOL_VERSIONS


EXPECTED_PROTOCOL_VERSION = "2026-07-28"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mcp-only",
        action="store_true",
        help="Check only the MCP protocol pin (the only guard in this repository).",
    )
    parser.parse_args()

    errors: list[str] = []
    if LATEST_PROTOCOL_VERSION != EXPECTED_PROTOCOL_VERSION:
        errors.append(
            "SDK latest protocol is "
            f"{LATEST_PROTOCOL_VERSION}, expected {EXPECTED_PROTOCOL_VERSION}"
        )
    if MODERN_PROTOCOL_VERSIONS != (EXPECTED_PROTOCOL_VERSION,):
        errors.append(
            "SDK modern protocol set is "
            f"{MODERN_PROTOCOL_VERSIONS}, expected {(EXPECTED_PROTOCOL_VERSION,)}"
        )

    if errors:
        for error in errors:
            print(f"Spec check: FAIL: {error}")
        return 1

    print(f"Spec check: PASS (MCP {EXPECTED_PROTOCOL_VERSION})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
