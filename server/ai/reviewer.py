"""Reviewer: a second model call that looks at the finished shaft and gives short hints.

It is a second pair of eyes, not a check. It cannot change the drawing, it cannot
approve it, and it cannot block the files. Its text is shown on the phone page only,
marked as AI hints. If the call fails or the answer is not valid, there are no hints.
"""

import json
import logging
import os
import re
from typing import Callable, Optional, Protocol

from pydantic import BaseModel, Field, ValidationError, field_validator

from server.ai.prompt import describe_spec
from server.core.spec import ShaftSpec
from server.core.validation import Report

log = logging.getLogger("evencad")

MAX_NOTES = 3
MAX_NOTE_CHARS = 90

REVIEW_PROMPT = f"""You look at a stepped shaft that a person described by voice, with the part in the hand.
You are a second pair of eyes for the engineer who will check the drawing later.

You get the shaft data and the results of the automatic checks.
Point out things that look unusual for a turned shaft and that the engineer should look at again.
Good hints are about: a number that may be misheard (15 or 50, 13 or 30), a missing chamfer on a sharp end,
a fit or roughness that is missing on a seat that has a keyway, a very thin or very short section,
a material that is not set.

Rules:
- You cannot change, approve or reject anything. You only give hints.
- At most {MAX_NOTES} hints. Each hint is one short sentence under {MAX_NOTE_CHARS} characters, in simple English.
- Do not repeat the automatic check results.
- Do not invent numbers, standards or tolerances. Use only the data you get.
- If nothing stands out, give no hints. That is a good answer.

Answer with one JSON object and nothing else:
{{"notes": ["hint", "hint"]}}    or    {{"notes": []}}"""


class ReviewResult(BaseModel):
    notes: list[str] = Field(default_factory=list, max_length=MAX_NOTES)

    @field_validator("notes")
    @classmethod
    def _short_plain_lines(cls, notes: list[str]) -> list[str]:
        clean = [" ".join(n.split()) for n in notes if n and n.strip()]
        # A hint that is too long for the page is dropped. The other hints stay. A cut hint could mislead.
        return [n for n in clean if len(n) <= MAX_NOTE_CHARS]


class Reviewer(Protocol):
    def review(self, spec: ShaftSpec, report: Report) -> list[str]: ...


def build_review_message(spec: ShaftSpec, report: Report) -> str:
    checks = [f"error: {m.text}" for m in report.errors] + [f"warning: {m.text}" for m in report.warnings]
    return f"Shaft:\n{describe_spec(spec)}\n\nAutomatic checks:\n" + ("\n".join(checks) or "no findings")


def parse_review(raw: str) -> list[str]:
    """Model text -> validated notes. Raises ValueError if it is not valid."""
    text = raw.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.DOTALL)
    if fenced:
        text = fenced.group(1)
    try:
        return ReviewResult.model_validate(json.loads(text)).notes
    except (json.JSONDecodeError, ValidationError) as e:
        raise ValueError(str(e)) from e


class ModelReviewer:
    """`complete(system, user)` is the same call that the interpreter adapters use."""

    def __init__(self, complete: Callable[[str, str], str]):
        self._complete = complete

    def review(self, spec: ShaftSpec, report: Report) -> list[str]:
        try:
            return parse_review(self._complete(REVIEW_PROMPT, build_review_message(spec, report)))
        except Exception as e:  # a hint must never break a finish
            log.warning("review failed: %s", e)
            return []


def get_reviewer(interpreter) -> Optional[Reviewer]:
    """A reviewer on the same model as the interpreter. None when REVIEWER=off or there is no model."""
    if os.environ.get("REVIEWER", "on").lower() in ("off", "0", "no", "false"):
        return None
    complete = getattr(interpreter, "_complete", None)
    return ModelReviewer(complete) if callable(complete) else None
