"""Guided measuring.

The display always asks for the next number: first the diameter of the next
segment, then its length. A bare number answers that question directly.
No model is called for it. Everything else goes to the interpreter as before.
"""

import re
from typing import Literal, Optional

from server.core.spec import ShaftSpec, fmt

Field = Literal["diameter", "length"]

_UNITS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
}
_TEENS = {
    "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
}
_TENS = {
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
}
_DIGITS = {"zero": "0", "oh": "0", **{word: str(n) for word, n in _UNITS.items()}}

_BEFORE = {"diameter": {"diameter", "dia", "phi", "ø"}, "length": {"length"}}
_AFTER = {"diameter": set(), "length": {"long"}}
_MM = {"mm", "millimeter", "millimeters", "millimetre", "millimetres"}


def _words_to_number(words: list[str]) -> Optional[float]:
    """Strict English number: [N hundred [and]] [tens] [unit] [point digit...]. None if anything else."""
    words = list(words)
    fraction = ""
    if "point" in words:
        at = words.index("point")
        tail = words[at + 1:]
        if not tail or any(w not in _DIGITS for w in tail):
            return None
        fraction = "".join(_DIGITS[w] for w in tail)
        words = words[:at]

    total = 0
    if "hundred" in words:
        at = words.index("hundred")
        head = words[:at]
        if head == ["a"] or not head:
            hundreds = 1
        elif len(head) == 1 and head[0] in _UNITS:
            hundreds = _UNITS[head[0]]
        else:
            return None
        total = hundreds * 100
        words = words[at + 1:]
        if words[:1] == ["and"]:
            words = words[1:]
            if not words:
                return None

    if len(words) == 1 and words[0] in _TEENS:
        total += _TEENS[words[0]]
    elif len(words) == 1 and words[0] in _UNITS:
        total += _UNITS[words[0]]
    elif len(words) == 1 and words[0] in _TENS:
        total += _TENS[words[0]]
    elif len(words) == 2 and words[0] in _TENS and words[1] in _UNITS:
        total += _TENS[words[0]] + _UNITS[words[1]]
    elif words:
        return None  # "fifteen fifty", "thirty forty": two numbers, or doubt

    if total == 0 and not fraction:
        return None
    return float(f"{total}.{fraction or '0'}")


def parse_number(text: str, field: Field) -> Optional[float]:
    """The value, if `text` is only a number that answers the asked field. Else None.

    Allowed around the number: the name of the asked field and "mm".
    Two numbers, a doubt, another field name or any other word give None.
    """
    s = text.strip().lower().rstrip(".!?").strip()
    s = re.sub(r"(?<=\d),(?=\d)", ".", s).replace(",", " ")
    s = re.sub(r"(?<=[a-z])-(?=[a-z])", " ", s)  # "twenty-five", but not "-5"
    s = re.sub(r"(?<=\d)(?=mm\b)", " ", s)
    words = s.split()

    if words and words[0] in _BEFORE[field]:
        words = words[1:]
    while words and (words[-1] in _MM or words[-1] in _AFTER[field]):
        words = words[:-1]
    if not words:
        return None

    if len(words) == 1 and re.fullmatch(r"\d{1,4}(\.\d{1,3})?", words[0]):
        value = float(words[0])
    else:
        value = _words_to_number(words)
    return value if value and value > 0 else None


_REJECTIONS = {
    "no", "nope", "no no", "wrong", "that's wrong", "that is wrong", "not that", "not right",
    "undo", "undo that", "go back", "cancel", "cancel that",
}


def is_rejection(text: str) -> bool:
    """True when the whole sentence only says "that was wrong". It means: undo the last entry."""
    s = re.sub(r"[.,!?]", " ", text.lower()).replace("’", "'")
    return " ".join(s.split()) in _REJECTIONS


def next_step(spec: ShaftSpec, pending_diameter: Optional[float]) -> dict:
    """What the display asks for next."""
    n = len(spec.segments) + 1
    if pending_diameter is None:
        return {"segment": n, "field": "diameter", "diameter": None, "text": f"Next: segment {n} diameter?"}
    return {
        "segment": n, "field": "length", "diameter": pending_diameter,
        "text": f"Next: segment {n} Ø{fmt(pending_diameter)} length?",
    }
