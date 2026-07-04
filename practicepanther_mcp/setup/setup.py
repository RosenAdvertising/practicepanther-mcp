#!/usr/bin/env python3
"""Interactive OAuth setup for practicepanther-mcp."""

from __future__ import annotations

import getpass
import secrets
import sys
from urllib.parse import urlencode

import requests

from practicepanther_mcp import credentials
from practicepanther_mcp.client import TOKEN_URL

AUTH_URL = "https://app.practicepanther.com/oauth/authorize"


def main() -> None:
    """Collect OAuth app credentials, exchange an authorization code, and save tokens."""

    print("=== practicepanther-mcp OAuth Setup ===\n")
    print(
        "PracticePanther API access is granted by support request. If you do not "
        "have a Client ID and Client Secret yet, request API access from "
        "PracticePanther support first.\n"
    )

    client_id = input("PracticePanther Client ID: ").strip()
    client_secret = getpass.getpass("PracticePanther Client Secret: ").strip()
    redirect_uri = (
        input(
            f"Redirect URI [{credentials.DEFAULT_REDIRECT_URI}]: "
        ).strip()
        or credentials.DEFAULT_REDIRECT_URI
    )

    if not client_id or not client_secret or not redirect_uri:
        print("Error: Client ID, Client Secret, and Redirect URI are required.")
        sys.exit(1)

    state = secrets.token_urlsafe(24)
    authorize_url = f"{AUTH_URL}?{urlencode({
        'response_type': 'code',
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'state': state,
    })}"

    print("\nOpen this URL in a browser, approve access, then paste the code from the redirect:")
    print(authorize_url)
    code = input("\nAuthorization code: ").strip()
    if not code:
        print("Error: Authorization code is required.")
        sys.exit(1)

    print("Exchanging authorization code for tokens...")
    resp = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
        },
        timeout=30,
    )
    if not resp.ok:
        print(f"Token exchange failed ({resp.status_code}): {resp.text}")
        sys.exit(1)

    tokens = resp.json()
    access_token = tokens.get("access_token", "")
    refresh_token = tokens.get("refresh_token", "")
    if not access_token or not refresh_token:
        print(f"Token exchange response was incomplete: {tokens}")
        sys.exit(1)

    path = credentials.save_values(
        {
            "PP_CLIENT_ID": client_id,
            "PP_CLIENT_SECRET": client_secret,
            "PP_REDIRECT_URI": redirect_uri,
            "PP_ACCESS_TOKEN": access_token,
            "PP_REFRESH_TOKEN": refresh_token,
        }
    )
    print(f"Saved credentials and tokens to {path}")

    print("\nRunning verification...")
    from practicepanther_mcp.setup.verify import check_api

    if not check_api():
        sys.exit(1)
    print("\nSetup complete. practicepanther-mcp is ready.")


if __name__ == "__main__":
    main()
