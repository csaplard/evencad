"""Interpreter: spoken text -> typed operations (EVENCAD_SPEC.md, sections 4a and 5).

Every answer is checked against the Pydantic schema. An invalid answer is retried
once. After that the user gets a question. Unvalidated output is never applied.
"""

import json
import os
import re
import shutil
import subprocess
import tempfile
from typing import Callable, Optional, Protocol

from pydantic import ValidationError

from server.ai.prompt import RETRY_NOTE, SYSTEM_PROMPT, build_user_message
from server.core.ops import InterpreterResult
from server.core.spec import ShaftSpec

NOT_UNDERSTOOD = "I did not understand, please say it again"


class InterpreterError(RuntimeError):
    """The model could not be reached at all."""


class Interpreter(Protocol):
    def interpret(self, spec: ShaftSpec, utterance: str) -> InterpreterResult: ...


def parse_result(raw: str) -> InterpreterResult:
    """Model text -> validated result. Raises ValueError if it is not valid."""
    text = raw.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.DOTALL)
    if fenced:
        text = fenced.group(1)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        # The model may write a note first. Take the JSON object at the very end of the text.
        tail = re.sub(r"\s*```\s*$", "", text)
        start = tail.rfind('{"ops"')
        if start < 0:
            raise ValueError(f"not JSON: {e}") from e
        try:
            data = json.loads(tail[start:])
        except json.JSONDecodeError as e2:
            raise ValueError(f"not JSON: {e2}") from e2
    if not isinstance(data, dict):
        raise ValueError("not a JSON object")
    if not data.get("ask"):
        data["ask"] = None
    for op in data.get("ops") or []:
        # The prompt allows explicit nulls for optional fields.
        if isinstance(op, dict):
            for key in [k for k, v in op.items() if v is None]:
                del op[key]
    try:
        return InterpreterResult.model_validate(data)
    except ValidationError as e:
        raise ValueError(str(e)) from e


def interpret_with(complete: Callable[[str, str], str], spec: ShaftSpec, utterance: str) -> InterpreterResult:
    """Shared flow of all adapters. `complete(system, user)` returns the model text."""
    user = build_user_message(spec, utterance)
    for attempt in range(2):
        raw = complete(SYSTEM_PROMPT, user if attempt == 0 else user + RETRY_NOTE)
        try:
            return parse_result(raw)
        except ValueError:
            continue
    return InterpreterResult(ops=[], ask=NOT_UNDERSTOOD)


class RecordedInterpreter:
    """Replays recorded model answers. Used by the golden tests and for offline demos."""

    def __init__(self, answers: dict[str, str]):
        self._answers = answers

    def interpret(self, spec: ShaftSpec, utterance: str) -> InterpreterResult:
        if utterance not in self._answers:
            return InterpreterResult(ops=[], ask=NOT_UNDERSTOOD)
        return interpret_with(lambda system, user: self._answers[utterance], spec, utterance)


class ClaudeCliInterpreter:
    """Development only: calls Claude through the Claude Code CLI in headless mode.

    Flags were checked against `claude --help` (version 2.1.246):
    no tools, no MCP servers, no settings files, no saved session, no skills.
    It runs in an empty temp folder, so no project memory file is found.
    `--bare` is not used: it skips the keychain, which the subscription login needs.
    """

    def __init__(self, model: Optional[str] = None, timeout: float = 90):
        self.model = model or os.environ.get("CLAUDE_CLI_MODEL", "haiku")
        self.timeout = timeout
        self._exe = shutil.which("claude")

    def _complete(self, system: str, user: str) -> str:
        if not self._exe:
            raise InterpreterError("The claude CLI is not on PATH")
        cmd = [
            self._exe, "-p",
            "--output-format", "json",
            "--model", self.model,
            "--system-prompt-file", "system.txt",
            "--tools", "",
            "--strict-mcp-config",
            "--setting-sources", "",
            "--no-session-persistence",
            "--disable-slash-commands",
        ]
        with tempfile.TemporaryDirectory() as cwd:
            # The prompt goes through a file: on Windows a multi-line argument
            # is cut at the first line break by the `claude.cmd` wrapper.
            with open(os.path.join(cwd, "system.txt"), "w", encoding="utf-8") as f:
                f.write(system)
            try:
                done = subprocess.run(cmd, input=user, capture_output=True, text=True, encoding="utf-8", cwd=cwd, timeout=self.timeout)
            except subprocess.TimeoutExpired as e:
                raise InterpreterError("The claude CLI timed out") from e
        if done.returncode != 0:
            raise InterpreterError(f"The claude CLI failed: {done.stderr.strip()[:300] or done.stdout.strip()[:300]}")
        try:
            envelope = json.loads(done.stdout)
        except json.JSONDecodeError as e:
            raise InterpreterError("The claude CLI did not return JSON") from e
        if envelope.get("is_error"):
            raise InterpreterError(f"The claude CLI reported an error: {str(envelope.get('result'))[:300]}")
        return str(envelope.get("result", ""))

    def interpret(self, spec: ShaftSpec, utterance: str) -> InterpreterResult:
        return interpret_with(self._complete, spec, utterance)


DEFAULT_API_MODEL = "claude-haiku-5-5"  # the spec asks for a fast model; override with CLAUDE_MODEL


class AnthropicApiInterpreter:
    """Default adapter: the Anthropic API through the official SDK.

    Same prompt and same JSON as the CLI adapter. Tuned for speed:
    thinking off, low effort, a short output limit, a short timeout.
    No sampling parameters are sent: current models reject non-default values.
    """

    def __init__(self, model: Optional[str] = None, client=None, timeout: float = 20.0):
        import anthropic  # imported here so the CLI adapter works without the package

        self._anthropic = anthropic
        self.model = model or os.environ.get("CLAUDE_MODEL") or DEFAULT_API_MODEL
        self.last_usage: Optional[dict] = None
        if client is not None:
            self._client = client
        else:
            try:
                # Reads ANTHROPIC_API_KEY (or another configured credential) from the environment.
                self._client = anthropic.Anthropic(timeout=timeout, max_retries=1)
            except anthropic.AnthropicError as e:
                raise InterpreterError(f"Anthropic API is not set up (set ANTHROPIC_API_KEY in .env): {e}") from e

    def _complete(self, system: str, user: str) -> str:
        a = self._anthropic
        try:
            response = self._client.messages.create(
                model=self.model,
                max_tokens=1024,  # the answer is a few short operations
                system=system,
                thinking={"type": "disabled"},
                output_config={"effort": "low"},
                messages=[{"role": "user", "content": user}],
            )
        except TypeError as e:
            # The SDK raises this when it finds no credential at request time.
            raise InterpreterError(f"Anthropic API is not set up (set ANTHROPIC_API_KEY in .env): {e}") from e
        except a.AuthenticationError as e:
            raise InterpreterError("Anthropic API key is missing or not valid (ANTHROPIC_API_KEY)") from e
        except a.PermissionDeniedError as e:
            raise InterpreterError("The Anthropic API key may not use this model") from e
        except a.NotFoundError as e:
            raise InterpreterError(f"Unknown model: {self.model} (CLAUDE_MODEL)") from e
        except a.RateLimitError as e:
            raise InterpreterError("Anthropic API rate limit reached, try again") from e
        except a.APIStatusError as e:
            raise InterpreterError(f"Anthropic API error {e.status_code}") from e
        except a.APIConnectionError as e:  # includes timeouts
            raise InterpreterError("Cannot reach the Anthropic API") from e

        usage = getattr(response, "usage", None)
        if usage is not None:
            self.last_usage = {"input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens}
        # A refusal or a cut-off answer is not valid output. The shared flow retries once, then asks.
        if response.stop_reason != "end_turn":
            return ""
        return "".join(block.text for block in response.content if block.type == "text")

    def interpret(self, spec: ShaftSpec, utterance: str) -> InterpreterResult:
        return interpret_with(self._complete, spec, utterance)


def get_interpreter(kind: Optional[str] = None) -> Interpreter:
    kind = (kind or os.environ.get("INTERPRETER") or "api").lower()
    if kind == "cli":
        return ClaudeCliInterpreter()
    if kind == "api":
        return AnthropicApiInterpreter()
    raise InterpreterError(f"Unknown INTERPRETER value: {kind}")
