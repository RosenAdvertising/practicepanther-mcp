#!/usr/bin/env python3
"""Post-setup verification for practicepanther-mcp."""

from __future__ import annotations

import sys

from practicepanther_mcp import credentials


def check_config() -> bool:
    """Verify the `.env` file contains the required OAuth values."""

    missing = credentials.missing_keys()
    if missing:
        print(f"Missing PracticePanther config: {', '.join(missing)}")
        print(f"Expected file: {credentials.env_file()}")
        print("Run: practicepanther-mcp-setup")
        return False

    print(f"Config found: {credentials.env_file()}")
    return True


def check_api() -> bool:
    """Verify auth and basic non-destructive reads."""

    try:
        from practicepanther_mcp.client import PracticePantherClient

        client = PracticePantherClient()
        me = client.get_current_user()
        name = me.get("display_name") or me.get("email") or "unknown user"
        print(f"Authenticated as: {name}")

        accounts = client.list_accounts(top=1)
        matters = client.list_matters(top=1)
        account_count = len(accounts) if isinstance(accounts, list) else "unknown"
        matter_count = len(matters) if isinstance(matters, list) else "unknown"
        print(f"Accounts readable: {account_count} returned (limit 1)")
        print(f"Matters readable: {matter_count} returned (limit 1)")
        return True
    except Exception as exc:  # noqa: BLE001 - CLI should surface any failure
        print(f"API check failed: {exc}")
        return False


def main() -> None:
    """Run setup verification and exit non-zero on failure."""

    print("=== practicepanther-mcp Verification ===\n")
    ok = check_config() and check_api()
    if ok:
        print("\nAll checks passed. practicepanther-mcp is ready.")
    else:
        print("\nSetup incomplete. Check errors above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
