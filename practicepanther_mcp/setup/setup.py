#!/usr/bin/env python3
"""Interactive OAuth setup for practicepanther-mcp."""

from __future__ import annotations

import getpass
import secrets
import sys
from urllib.parse import parse_qs, urlencode, urlsplit

import requests

from practicepanther_mcp import credentials
from practicepanther_mcp.client import ACCESS_DENIED_MESSAGE, TOKEN_URL

AUTH_URL = "https://app.practicepanther.com/oauth/authorize"


def main() -> None:
    """Collect OAuth app credentials, exchange an authorization code, and save tokens."""

    print("=== practicepanther-mcp OAuth Setup ===\n")
    print(
        "PracticePanther API access is granted by support request. If you do not "
        "have a Client ID and Client Secret yet, request API access from "
        "PracticePanther support first.\n"
    )

    try:
        client_id = input("PracticePanther Client ID: ").strip()
        if not client_id:
            print(
                "Error: Client ID is required. Obtain API access from PracticePanther support."
            )
            sys.exit(1)
        client_secret = getpass.getpass("PracticePanther Client Secret: ").strip()
        if not client_secret:
            print(
                "Error: Client Secret is required. Obtain API access from PracticePanther support."
            )
            sys.exit(1)
        redirect_uri = (
            input(f"Redirect URI [{credentials.DEFAULT_REDIRECT_URI}]: ").strip()
            or credentials.DEFAULT_REDIRECT_URI
        )
    except EOFError:
        print("Error: Setup input ended before the required OAuth values were entered.")
        sys.exit(1)

    if not client_id or not client_secret or not redirect_uri:
        print("Error: Client ID, Client Secret, and Redirect URI are required.")
        sys.exit(1)

    state = secrets.token_urlsafe(24)
    authorize_params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "state": state,
    }
    authorize_url = f"{AUTH_URL}?{urlencode(authorize_params)}"

    print(
        "\nOpen this URL in a browser, approve access, then paste the full redirect URL:"
    )
    print(authorize_url)
    try:
        returned_url = input("\nFull redirect URL: ").strip()
    except EOFError:
        print("Error: Authorization code is required to finish setup.")
        sys.exit(1)
    try:
        returned = urlsplit(returned_url)
        expected = urlsplit(redirect_uri)
        params = parse_qs(returned.query, keep_blank_values=True)
        states = params.get("state", [])
        codes = params.get("code", [])
        valid = (
            (returned.scheme, returned.netloc, returned.path)
            == (expected.scheme, expected.netloc, expected.path)
            and not returned.fragment
            and len(states) == 1
            and secrets.compare_digest(states[0], state)
            and len(codes) == 1
            and bool(codes[0])
            and "error" not in params
        )
    except (ValueError, TypeError):
        valid = False
    if not valid:
        print(
            "Error: Redirect URL must contain the matching OAuth state and authorization code."
        )
        sys.exit(1)
    code = codes[0]

    print("Exchanging authorization code for tokens...")
    try:
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
    except requests.Timeout:
        print(
            "Token exchange timed out; the outcome is unknown. Check whether authorization completed before retrying setup."
        )
        sys.exit(1)
    except requests.ConnectionError:
        print(
            "Token exchange lost its connection; the outcome is unknown. Check whether authorization completed before retrying setup."
        )
        sys.exit(1)
    except requests.RequestException:
        print(
            "Token exchange failed due to a network error. Check connectivity and try setup again."
        )
        sys.exit(1)
    if not resp.ok:
        if resp.status_code == 401:
            print(
                "Token exchange failed (401). Check the client credentials and authorization code."
            )
        elif resp.status_code == 403:
            print(ACCESS_DENIED_MESSAGE)
        else:
            print(
                f"Token exchange failed (HTTP {resp.status_code}). Check the OAuth values and try setup again."
            )
        sys.exit(1)

    try:
        tokens = resp.json()
    except (ValueError, TypeError):
        print(
            "Token exchange response was invalid. Check the OAuth values and try setup again."
        )
        sys.exit(1)
    if not isinstance(tokens, dict):
        print(
            "Token exchange response was invalid. Check the OAuth values and try setup again."
        )
        sys.exit(1)
    access_token = tokens.get("access_token", "")
    refresh_token = tokens.get("refresh_token", "")
    if not access_token or not refresh_token:
        print("Token exchange response was incomplete.")
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
