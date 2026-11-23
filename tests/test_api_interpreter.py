"""Anthropic API adapter. A fake client stands in for the network.

The real API is exercised by `pytest -m live` with INTERPRETER=api (test_interpreter.py).
"""

import json
from pathlib import Path
from types import SimpleNamespace

import anthropic
import httpx2
import pytest

from server.ai.interpreter import (
    DEFAULT_API_MODEL,
    NOT_UNDERSTOOD,
    AnthropicApiInterpreter,
    InterpreterError,
    get_interpreter,
)
from server.ai.prompt import SYSTEM_PROMPT
from server.core.ops import parse_op
from server.core.spec import Segment, ShaftSpec

GOLDEN = json.loads((Path(__file__).parent.parent / "samples" / "golden.json").read_text(encoding="utf-8"))


def message(text, stop_reason="end_turn"):
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text)],
        stop_reason=stop_reason,
        usage=SimpleNamespace(input_tokens=700, output_tokens=40),
    )


class FakeClient:
    """Looks like `anthropic.Anthropic()` for the one call we make."""

    def __init__(self, *answers):
        self.answers = list(answers)
        self.calls = []
        self.messages = self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


def spec_of(before=()):
    return ShaftSpec(id="s_20261123_aaaaaa", segments=[Segment(diameter=d, length=length) for d, length in before])


def status_error(cls, status):
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    return cls("boom", response=httpx2.Response(status, request=request), body=None)


def test_request_shape():
    client = FakeClient(message('{"ops": [{"op": "undo"}], "ask": null}'))
    api = AnthropicApiInterpreter(client=client)
    result = api.interpret(spec_of([[30, 40]]), "undo")
    assert result.ops[0].op == "undo"
    call = client.calls[0]
    assert call["model"] == DEFAULT_API_MODEL == "claude-haiku-5-5"
    assert call["system"] == SYSTEM_PROMPT
    assert call["thinking"] == {"type": "disabled"}
    assert call["output_config"] == {"effort": "low"}
    assert call["messages"][0]["role"] == "user" and "1: diameter 30, length 40" in call["messages"][0]["content"]
    # Current models reject sampling parameters and assistant prefill.
    assert not {"temperature", "top_p", "top_k"} & set(call)
    assert len(call["messages"]) == 1
    assert api.last_usage == {"input_tokens": 700, "output_tokens": 40}


def test_model_comes_from_the_environment(monkeypatch):
    monkeypatch.setenv("CLAUDE_MODEL", "claude-sonnet-5-5")
    assert AnthropicApiInterpreter(client=FakeClient()).model == "claude-sonnet-5-5"


@pytest.mark.parametrize("case", GOLDEN, ids=[c["name"] for c in GOLDEN])
def test_same_json_as_the_cli_adapter(case):
    """The recorded answers pass through the API adapter exactly as through the CLI adapter."""
    api = AnthropicApiInterpreter(client=FakeClient(message(case["recorded"])))
    result = api.interpret(spec_of(case["before"]), case["utterance"])
    if case["expect"].get("ask"):
        assert result.ops == [] and result.ask
    else:
        assert result.ops == [parse_op(op) for op in case["expect"]["ops"]]


def test_invalid_answer_is_retried_once_then_asks():
    client = FakeClient(message("Here you go!"), message("Still not JSON"))
    result = AnthropicApiInterpreter(client=client).interpret(spec_of(), "hello")
    assert len(client.calls) == 2
    assert result.ops == [] and result.ask == NOT_UNDERSTOOD


@pytest.mark.parametrize("stop_reason", ["refusal", "max_tokens"])
def test_refusal_or_cut_off_answer_is_never_applied(stop_reason):
    half = '{"ops": [{"op": "finish"}], "ask": null}'
    client = FakeClient(message(half, stop_reason), message(half, stop_reason))
    result = AnthropicApiInterpreter(client=client).interpret(spec_of(), "finish")
    assert result.ops == [] and result.ask == NOT_UNDERSTOOD


@pytest.mark.parametrize(
    "error, text",
    [
        (status_error(anthropic.AuthenticationError, 401), "API key"),
        (status_error(anthropic.PermissionDeniedError, 403), "may not use"),
        (status_error(anthropic.NotFoundError, 404), "Unknown model"),
        (status_error(anthropic.RateLimitError, 429), "rate limit"),
        (status_error(anthropic.InternalServerError, 500), "error 500"),
        (anthropic.APIConnectionError(request=httpx2.Request("POST", "https://api.anthropic.com")), "Cannot reach"),
    ],
)
def test_api_failures_become_interpreter_errors(error, text):
    api = AnthropicApiInterpreter(client=FakeClient(error))
    with pytest.raises(InterpreterError, match=text):
        api.interpret(spec_of(), "undo")


def test_missing_credentials_give_a_clear_error(monkeypatch):
    for name in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_PROFILE"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(InterpreterError, match="ANTHROPIC_API_KEY|API key"):
        AnthropicApiInterpreter().interpret(spec_of(), "undo")


def test_factory_picks_the_adapter(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
    monkeypatch.delenv("INTERPRETER", raising=False)
    assert isinstance(get_interpreter(), AnthropicApiInterpreter)  # api is the default
    assert isinstance(get_interpreter("api"), AnthropicApiInterpreter)
    assert type(get_interpreter("cli")).__name__ == "ClaudeCliInterpreter"
    with pytest.raises(InterpreterError):
        get_interpreter("gpt")
