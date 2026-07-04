#!/usr/bin/env python3
"""Credential and token file handling for practicepanther-mcp.

All PracticePanther OAuth app credentials and rotating tokens are stored in a
single chmod-0600 `.env` file under `~/.practicepanther-mcp/`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

CONFIG_DIR_ENV = "PP_MCP_CONFIG_DIR"
DEFAULT_CONFIG_DIR = Path.home() / ".practicepanther-mcp"
DEFAULT_REDIRECT_URI = "http://localhost:8123/callback"

KNOWN_KEYS = [
    "PP_CLIENT_ID",
    "PP_CLIENT_SECRET",
    "PP_REDIRECT_URI",
    "PP_ACCESS_TOKEN",
    "PP_REFRESH_TOKEN",
]


@dataclass(frozen=True)
class PracticePantherCredentials:
    """Resolved PracticePanther OAuth configuration."""

    client_id: str
    client_secret: str
    redirect_uri: str
    access_token: str
    refresh_token: str


def config_dir() -> Path:
    """Return the active config directory.

    `PP_MCP_CONFIG_DIR` is a test/automation override; normal users should rely
    on the default `~/.practicepanther-mcp/`.
    """

    override = os.environ.get(CONFIG_DIR_ENV, "").strip()
    if override:
        return Path(override).expanduser()
    return DEFAULT_CONFIG_DIR


def env_file() -> Path:
    """Return the active `.env` credential file path."""

    return config_dir() / ".env"


def _parse_env_file(path: Path | None = None) -> dict[str, str]:
    """Parse simple KEY=VALUE lines from the PracticePanther `.env` file."""

    path = path or env_file()
    values: dict[str, str] = {}
    if not path.exists():
        return values

    with path.open() as fh:
        for raw_line in fh:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return values


def _write_env_file(values: dict[str, str], path: Path | None = None) -> None:
    """Write the `.env` file in stable order with restrictive permissions."""

    path = path or env_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.parent.chmod(0o700)
    except OSError:
        pass

    ordered_keys = [key for key in KNOWN_KEYS if key in values]
    ordered_keys.extend(key for key in values if key not in KNOWN_KEYS)
    lines = [f"{key}={values[key]}" for key in ordered_keys]
    path.write_text("\n".join(lines) + ("\n" if lines else ""))

    try:
        path.chmod(0o600)
    except OSError:
        pass


def load_into_environ(keys: list[str] | None = None) -> None:
    """Load configured values into `os.environ` without overriding exports."""

    path = env_file()
    if path.exists():
        load_dotenv(path, override=False)

    wanted = keys or KNOWN_KEYS
    file_values = _parse_env_file(path)
    for key in wanted:
        if os.environ.get(key):
            continue
        value = file_values.get(key)
        if value:
            os.environ[key] = value


def save_values(values: dict[str, str]) -> Path:
    """Persist updated credential/token values and mirror them into environ."""

    existing = _parse_env_file()
    for key, value in values.items():
        if value is None:
            continue
        existing[key] = str(value)
        os.environ[key] = str(value)

    if not existing.get("PP_REDIRECT_URI"):
        existing["PP_REDIRECT_URI"] = DEFAULT_REDIRECT_URI
        os.environ.setdefault("PP_REDIRECT_URI", DEFAULT_REDIRECT_URI)

    _write_env_file(existing)
    return env_file()


def load_credentials() -> PracticePantherCredentials:
    """Return PracticePanther credentials resolved from env and `.env`."""

    load_into_environ(KNOWN_KEYS)
    return PracticePantherCredentials(
        client_id=os.environ.get("PP_CLIENT_ID", ""),
        client_secret=os.environ.get("PP_CLIENT_SECRET", ""),
        redirect_uri=os.environ.get("PP_REDIRECT_URI", DEFAULT_REDIRECT_URI)
        or DEFAULT_REDIRECT_URI,
        access_token=os.environ.get("PP_ACCESS_TOKEN", ""),
        refresh_token=os.environ.get("PP_REFRESH_TOKEN", ""),
    )


def missing_keys(keys: list[str] | None = None) -> list[str]:
    """Return required keys that are currently unset."""

    load_into_environ(KNOWN_KEYS)
    wanted = keys or KNOWN_KEYS
    return [key for key in wanted if not os.environ.get(key)]
