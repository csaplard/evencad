"""Guided measuring.

The display always asks for the next number: first the diameter of the next
segment, then its length. A bare number answers that question directly.
No model is called for it. Everything else goes to the interpreter as before.

Numbers and "no" words are understood in English and in Hungarian.
Hungarian words are compared without accents, because the recogniser may drop them.
"""

import re
import unicodedata
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
    "twenty": 20, "thirty": 30, "forty": 40, "fourty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
}
_DIGITS = {"zero": "0", "oh": "0", **{word: str(n) for word, n in _UNITS.items()}}

_BEFORE = {"diameter": {"diameter", "dia", "phi", "ø", "atmero"}, "length": {"length", "hossz", "hossza"}}
_AFTER = {"diameter": {"dia", "diameter", "atmero"}, "length": {"long", "hosszu", "hossz"}}
_MM = {"mm", "millimeter", "millimeters", "millimetre", "millimetres", "milli", "millis"}


def _no_accents(text: str) -> str:
    """ "átmérő" -> "atmero". The sign "ø" stays."""
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


# Hungarian numbers are written as one word: "százhuszonöt". The table has every spelling of 1 to 999.
_HU_UNITS = {1: ["egy"], 2: ["ketto", "ket"], 3: ["harom"], 4: ["negy"], 5: ["ot"], 6: ["hat"], 7: ["het"], 8: ["nyolc"], 9: ["kilenc"]}
_HU_TENS = {30: "harminc", 40: "negyven", 50: "otven", 60: "hatvan", 70: "hetven", 80: "nyolcvan", 90: "kilencven"}
_HU_DIGITS = {"nulla": "0", **{word: str(n) for n, words in _HU_UNITS.items() for word in words}}


def _hungarian_table() -> dict[str, int]:
    below_100: dict[str, int] = {"tiz": 10, "husz": 20}
    for n, words in _HU_UNITS.items():
        for word in words:
            below_100[word] = n
            below_100["tizen" + word] = 10 + n
            below_100["huszon" + word] = 20 + n
            for tens, name in _HU_TENS.items():
                below_100[name + word] = tens + n
    below_100.update({name: tens for tens, name in _HU_TENS.items()})

    table = dict(below_100)
    for n, prefixes in {1: ["", "egy"], **{k: v for k, v in _HU_UNITS.items() if k > 1}}.items():
        for prefix in prefixes:
            table[prefix + "szaz"] = n * 100
            for word, value in below_100.items():
                table[prefix + "szaz" + word] = n * 100 + value
    return table


_HU = _hungarian_table()


def _hungarian_number(words: list[str]) -> Optional[float]:
    """Strict Hungarian number: "huszonot", "szaz husz", "huszonot egesz ot", "huszonot es fel", "harmincas"."""
    words = list(words)
    half = words[-2:] == ["es", "fel"]
    if half:
        words = words[:-2]

    fraction = ""
    if "egesz" in words:
        at = words.index("egesz")
        tail = words[at + 1:]
        words = words[:at]
        unit = tail.pop() if tail and tail[-1] in ("tized", "szazad") else None
        if not tail or half:
            return None
        if all(w in _HU_DIGITS for w in tail):
            fraction = "".join(_HU_DIGITS[w] for w in tail)
        elif _HU.get("".join(tail), 100) < 100:
            fraction = str(_HU["".join(tail)])
        else:
            return None
        if (unit == "tized" and len(fraction) != 1) or (unit == "szazad" and len(fraction) > 2):
            return None
        if unit == "szazad":
            fraction = fraction.zfill(2)

    if not words:
        return None
    joined = "".join(words)
    total = 0 if joined == "nulla" else _HU.get(joined)
    if total is None and not fraction and not half:
        # "harmincas", "huszonotos", "kettes": the way a size is named.
        plain = re.sub(r"harmas$", "harom", re.sub(r"kettes$", "ketto", joined))
        total = _HU.get(re.sub(r"(as|es|os)$", "", plain))
    if total is None:
        return None
    return float(f"{total}.{fraction or '0'}") + (0.5 if half else 0)


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
    Two numbers, a doubt ("25?"), another field name or any other word give None.
    """
    s = _no_accents(text.strip().lower())
    if s.endswith("?"):
        return None  # speech recognition marks a doubt this way
    s = s.rstrip(".!").strip()
    s = re.sub(r"(?<=\d),(?=\d(?!\d))", ".", s)  # "25,5" is 25.5. Only one digit after the comma.
    if re.search(r"\d,\d", s):
        return None  # "25,30" or "1,000": two numbers, or a thousands mark
    s = s.replace(",", " ")
    s = re.sub(r"(?<=[a-z])-(?=[a-z])", " ", s)  # "twenty-five", but not "-5"
    s = re.sub(r"(?<=\d)(?=mm\b)", " ", s)
    s = re.sub(r"ø\s*(?=\d)", "ø ", s)
    s = re.sub(r"(?<=\d) (point|egesz) (?=\d)", ".", s)  # "25 point 5"
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
        value = _words_to_number(words) or _hungarian_number(words)
    return value if value and value > 0 else None


# Words that join a diameter and a length: "20 and 30", "30 by 40", "30 x 40", "harminc és negyven".
_JOIN = re.compile(r"\s+(?:and|by|x|×|times|es|szer)\s+|\s*×\s*")


def parse_pair(text: str) -> Optional[tuple[float, float]]:
    """(diameter, length), if `text` is only two numbers with a joining word. Else None.

    "one hundred and twenty" is one number, so every place of a joining word is tried.
    Two numbers with no joining word ("thirty forty") stay a doubt.
    """
    s = _no_accents(text.strip().lower())
    if s.endswith("?") or parse_number(text, "diameter") is not None:
        return None
    s = re.sub(r"\s*,\s*(?=(?:and|es)\b)", " ", s.rstrip(".!").strip())  # "20, and 30"
    found = []
    for m in _JOIN.finditer(s):
        diameter, length = parse_number(s[:m.start()], "diameter"), parse_number(s[m.end():], "length")
        if diameter is not None and length is not None:
            found.append((diameter, length))
    return found[0] if len(found) == 1 else None


_REJECTIONS = {
    "no", "nope", "no no", "wrong", "that's wrong", "that is wrong", "not that", "not right",
    "undo", "undo that", "go back", "cancel", "cancel that",
    # Hungarian, without accents
    "nem", "nem nem", "nem jo", "rossz", "megse", "megsem", "torold", "vissza", "visszavonas", "vond vissza",
}


_UNDO = {"undo", "undo that", "go back", "vissza", "visszavonas", "vond vissza"}


def _plain(text: str) -> str:
    s = re.sub(r"[.,!?]", " ", _no_accents(text.lower())).replace("’", "'")
    return " ".join(s.split())


def is_rejection(text: str) -> bool:
    """True when the whole sentence only says "that was wrong".

    With a question or a warning prompt on the display it only dismisses that.
    Otherwise it means: undo the last entry.
    """
    return _plain(text) in _REJECTIONS


def is_undo(text: str) -> bool:
    """True for the words that always mean undo, whatever is on the display."""
    return _plain(text) in _UNDO


def next_step(spec: ShaftSpec, pending_diameter: Optional[float]) -> dict:
    """What the display asks for next."""
    n = len(spec.segments) + 1
    if pending_diameter is None:
        return {"segment": n, "field": "diameter", "diameter": None, "text": f"Next: segment {n} diameter?"}
    return {
        "segment": n, "field": "length", "diameter": pending_diameter,
        "text": f"Next: segment {n} Ø{fmt(pending_diameter)} length?",
    }
