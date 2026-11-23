"""Test setup: tests never read the developer's .env and never reach real services."""

import os

import pytest

# Must be set before server.main is imported: it builds the default app at import time.
os.environ["EVENCAD_SKIP_DOTENV"] = "1"

_KEEP_FOR_LIVE = {"INTERPRETER", "ANTHROPIC_API_KEY", "CLAUDE_MODEL", "CLAUDE_CLI_MODEL"}
_SERVICE_VARS = [
    "INTERPRETER", "ANTHROPIC_API_KEY", "CLAUDE_MODEL", "CLAUDE_CLI_MODEL",
    "GOOGLE_DRIVE_FOLDER_ID", "GOOGLE_TOKEN_FILE", "GOOGLE_OAUTH_CLIENT_FILE",
    "STT_PROVIDER", "STT_MODEL", "STT_LANGUAGE", "DATA_DIR", "CORS_ALLOW_ORIGINS",
]


@pytest.fixture(autouse=True)
def _clean_service_env(request, monkeypatch):
    live = request.node.get_closest_marker("live") is not None
    for name in _SERVICE_VARS:
        if live and name in _KEEP_FOR_LIVE:
            continue
        monkeypatch.delenv(name, raising=False)
