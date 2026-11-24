"""The .env reader of the server."""

import logging
import os

from server.main import _load_env_file

NAMES = ("ANTHROPIC_API_KEY", "INTERPRETER", "REVIEWER", "CLAUDE_MODEL")


def load(tmp_path, monkeypatch, text, **before):
    monkeypatch.delenv("SAYCAD_SKIP_DOTENV", raising=False)
    for name in NAMES:
        monkeypatch.delenv(name, raising=False)
    for name, value in before.items():
        monkeypatch.setenv(name, value)
    path = tmp_path / ".env"
    path.write_text(text, encoding="utf-8")
    _load_env_file(path)


def test_the_file_wins_over_an_old_system_variable(tmp_path, monkeypatch, caplog):
    with caplog.at_level(logging.WARNING, logger="saycad"):
        load(tmp_path, monkeypatch, "# note\nANTHROPIC_API_KEY=new-key\nINTERPRETER = api\n", ANTHROPIC_API_KEY="old-key")
    assert os.environ["ANTHROPIC_API_KEY"] == "new-key" and os.environ["INTERPRETER"] == "api"
    assert "ANTHROPIC_API_KEY" in caplog.text
    assert "new-key" not in caplog.text and "old-key" not in caplog.text  # the log never has a value


def test_an_empty_value_in_the_file_changes_nothing(tmp_path, monkeypatch):
    load(tmp_path, monkeypatch, "ANTHROPIC_API_KEY=\nREVIEWER=\n", ANTHROPIC_API_KEY="from-the-shell")
    assert os.environ["ANTHROPIC_API_KEY"] == "from-the-shell" and "REVIEWER" not in os.environ


def test_quotes_and_a_byte_order_mark_are_handled(tmp_path, monkeypatch):
    load(tmp_path, monkeypatch, "﻿CLAUDE_MODEL=\"claude-haiku-5-5\"\nANTHROPIC_API_KEY='k'\n")
    assert os.environ["CLAUDE_MODEL"] == "claude-haiku-5-5" and os.environ["ANTHROPIC_API_KEY"] == "k"


def test_the_switch_for_tests_skips_the_file(tmp_path, monkeypatch):
    load(tmp_path, monkeypatch, "")
    monkeypatch.setenv("SAYCAD_SKIP_DOTENV", "1")
    path = tmp_path / ".env"
    path.write_text("ANTHROPIC_API_KEY=x\n", encoding="utf-8")
    _load_env_file(path)
    assert "ANTHROPIC_API_KEY" not in os.environ
