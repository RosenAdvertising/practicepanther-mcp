"""Daybreak review probes at the registered MCP or real setup/storage boundary."""

import asyncio
import os
import stat
from unittest.mock import Mock

import pytest
from mcp.types import CallToolRequestParams

from practicepanther_mcp import credentials, server


def invoke(name, arguments):
    return asyncio.run(
        server.mcp._handle_call_tool(
            None, CallToolRequestParams(name=name, arguments=arguments)
        )
    )


def text(result):
    return " ".join(part.text for part in result.content if hasattr(part, "text"))


@pytest.mark.parametrize("existing", [False, True])
@pytest.mark.parametrize("failure", [None, "chmod", "fchmod", "replace"])
def test_setup_secret_file_is_private_and_atomic(
    monkeypatch, tmp_path, existing, failure
):
    target = tmp_path / ".env"
    if existing:
        target.write_text("PROBE=old\n")
        target.chmod(0o644)
    monkeypatch.setenv(credentials.CONFIG_DIR_ENV, str(tmp_path))

    def save():
        credentials.save_values({"PROBE": "synthetic-value"})

    original_open = os.open
    original_replace = os.replace
    seen_modes = []

    def checked_open(path, flags, mode=0o777, *args, **kwargs):
        fd = original_open(path, flags, mode, *args, **kwargs)
        if str(path).endswith(".tmp"):
            seen_modes.append(stat.S_IMODE(os.fstat(fd).st_mode))
            assert mode == 0o600
            assert os.fstat(fd).st_size == 0
        return fd

    def fail(*args, **kwargs):
        raise PermissionError("simulated permission failure")

    def checked_replace(source, dest):
        assert stat.S_IMODE(source.stat().st_mode) == 0o600
        assert "synthetic-value" in source.read_text()
        assert target.read_text() == "PROBE=old\n" if existing else not target.exists()
        return original_replace(source, dest)

    monkeypatch.setattr(os, "open", checked_open)
    monkeypatch.setattr(os, "replace", checked_replace)
    if failure == "chmod":
        monkeypatch.setattr(os, "chmod", fail)
    elif failure == "fchmod":
        monkeypatch.setattr(os, "fchmod", fail)
    elif failure == "replace":
        monkeypatch.setattr(os, "replace", fail)
    previous = os.umask(0o022)
    try:
        if failure in {"fchmod", "replace"}:
            with pytest.raises(PermissionError):
                save()
            assert (
                target.read_text() == "PROBE=old\n" if existing else not target.exists()
            )
        else:
            save()
            assert stat.S_IMODE(target.stat().st_mode) == 0o600
            assert "synthetic-value" in target.read_text()
    finally:
        os.umask(previous)
    assert seen_modes == [0o600]
    assert not list(tmp_path.glob(".*.tmp"))


@pytest.mark.parametrize(
    "suffix",
    [
        "?code=probe",
        "?code=probe&state=wrong",
        "?code=probe&state=",
        "?code=probe&state=expected&state=wrong",
        "?state=expected",
        "?code=probe&state=expected#fragment",
    ],
)
def test_oauth_state_rejected_before_exchange(monkeypatch, suffix):
    from practicepanther_mcp.setup import setup

    answers = iter(["synthetic-id", "", credentials.DEFAULT_REDIRECT_URI + suffix])
    monkeypatch.setattr("builtins.input", lambda *a: next(answers))
    monkeypatch.setattr(setup.getpass, "getpass", lambda *a: "synthetic-value")
    monkeypatch.setattr(setup.secrets, "token_urlsafe", lambda *a: "expected")
    post = Mock()
    save = Mock()
    monkeypatch.setattr(setup.requests, "post", post)
    monkeypatch.setattr(credentials, "save_values", save)
    with pytest.raises(SystemExit) as caught:
        setup.main()
    assert caught.value.code == 1
    post.assert_not_called()
    save.assert_not_called()


@pytest.mark.parametrize("permission_failure", [False, True])
def test_setup_matching_state_and_private_storage(
    monkeypatch, tmp_path, permission_failure
):
    from practicepanther_mcp.setup import setup, verify

    monkeypatch.setenv(credentials.CONFIG_DIR_ENV, str(tmp_path))
    answers = iter(
        [
            "synthetic-id",
            "",
            credentials.DEFAULT_REDIRECT_URI + "?code=probe&state=expected",
        ]
    )
    monkeypatch.setattr("builtins.input", lambda *a: next(answers))
    monkeypatch.setattr(setup.getpass, "getpass", lambda *a: "synthetic-value")
    monkeypatch.setattr(setup.secrets, "token_urlsafe", lambda *a: "expected")
    post = Mock(
        return_value=Mock(
            ok=True,
            json=lambda: {
                "access_token": "synthetic-value",
                "refresh_token": "synthetic-value",
            },
        )
    )
    monkeypatch.setattr(setup.requests, "post", post)
    check = Mock(return_value=True)
    monkeypatch.setattr(verify, "check_api", check)
    if permission_failure:
        monkeypatch.setattr(os, "fchmod", Mock(side_effect=PermissionError("denied")))
        with pytest.raises(PermissionError):
            setup.main()
        assert not credentials.env_file().exists()
        check.assert_not_called()
    else:
        setup.main()
        assert stat.S_IMODE(credentials.env_file().stat().st_mode) == 0o600
        check.assert_called_once()
    assert post.call_args.kwargs["data"]["code"] == "probe"
