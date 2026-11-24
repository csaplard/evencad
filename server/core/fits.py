"""Tolerance limits of ISO 286 shaft fits: "h6" on Ø25 -> 0 / -0.013 mm.

The AI gives only the fit text. The numbers are looked up here.
A fit that is not in the table gives no numbers. Nothing is guessed.

The table covers sizes over 0 up to 500 mm, the letters d e f g h js k m n p r s
and the grades IT5 to IT11. The values were typed in from memory of ISO 286-2 and
must be checked against the standard before anyone relies on them (docs/open-questions.md).
"""

import re
from bisect import bisect_left
from typing import Optional

STANDARD = "ISO 286"

# Upper ends of the main size ranges in mm ("over ... up to and including").
_RANGES = (3, 6, 10, 18, 30, 50, 80, 120, 180, 250, 315, 400, 500)

# Standard tolerances in µm, one value per main range.
_IT = {
    5: (4, 5, 6, 8, 9, 11, 13, 15, 18, 20, 23, 25, 27),
    6: (6, 8, 9, 11, 13, 16, 19, 22, 25, 29, 32, 36, 40),
    7: (10, 12, 15, 18, 21, 25, 30, 35, 40, 46, 52, 57, 63),
    8: (14, 18, 22, 27, 33, 39, 46, 54, 63, 72, 81, 89, 97),
    9: (25, 30, 36, 43, 52, 62, 74, 87, 100, 115, 130, 140, 155),
    10: (40, 48, 58, 70, 84, 100, 120, 140, 160, 185, 210, 230, 250),
    11: (60, 75, 90, 110, 130, 160, 190, 220, 250, 290, 320, 360, 400),
}

# Letters d to h: the upper deviation in µm (the zone is below it).
_UPPER = {
    "d": (-20, -30, -40, -50, -65, -80, -100, -120, -145, -170, -190, -210, -230),
    "e": (-14, -20, -25, -32, -40, -50, -60, -72, -85, -100, -110, -125, -135),
    "f": (-6, -10, -13, -16, -20, -25, -30, -36, -43, -50, -56, -62, -68),
    "g": (-2, -4, -5, -6, -7, -9, -10, -12, -14, -15, -17, -18, -20),
    "h": (0,) * 13,
}

# Letters k to p: the lower deviation in µm (the zone is above it).
_K_GRADES_5_TO_7 = (0, 1, 1, 1, 2, 2, 2, 3, 3, 4, 4, 4, 5)  # k is 0 for the other grades
_LOWER = {
    "m": (2, 4, 6, 7, 8, 9, 11, 13, 15, 17, 20, 21, 23),
    "n": (4, 8, 10, 12, 15, 17, 20, 23, 27, 31, 34, 37, 40),
    "p": (6, 12, 15, 18, 22, 26, 32, 37, 43, 50, 56, 62, 68),
}

# Letters r and s: the lower deviation in µm. Above 50 mm the ranges are split.
_SPLIT_RANGES = (3, 6, 10, 18, 30, 50, 65, 80, 100, 120, 140, 160, 180, 200, 225, 250, 280, 315, 355, 400, 450, 500)
_LOWER_SPLIT = {
    "r": (10, 15, 19, 23, 28, 34, 41, 43, 51, 54, 63, 65, 68, 77, 80, 84, 94, 98, 108, 114, 126, 132),
    "s": (14, 19, 23, 28, 35, 43, 53, 59, 71, 79, 92, 100, 108, 122, 130, 140, 158, 170, 190, 208, 232, 252),
}

_FIT = re.compile(r"(js|[a-z])(\d{1,2})")


def _row(ranges: tuple, diameter: float) -> Optional[int]:
    if not 0 < diameter <= ranges[-1]:
        return None
    return bisect_left(ranges, diameter)


def limits(diameter: float, fit: Optional[str]) -> Optional[tuple[float, float]]:
    """(upper, lower) deviation in mm, or None when the fit or the size is not in the table."""
    m = _FIT.fullmatch(fit or "")
    row = _row(_RANGES, diameter)
    if not m or row is None or int(m[2]) not in _IT:
        return None
    letter, grade = m[1], int(m[2])
    it = _IT[grade][row]

    if letter in _UPPER:
        upper = _UPPER[letter][row]
        lower = upper - it
    elif letter == "js":
        upper, lower = it / 2, -it / 2
    else:
        if letter == "k":
            lower = _K_GRADES_5_TO_7[row] if grade <= 7 else 0
        elif letter in _LOWER:
            lower = _LOWER[letter][row]
        elif letter in _LOWER_SPLIT:
            lower = _LOWER_SPLIT[letter][_row(_SPLIT_RANGES, diameter)]
        else:
            return None
        upper = lower + it
    return (upper / 1000, lower / 1000)


def _signed(value: float) -> str:
    text = f"{value:.4f}".rstrip("0").rstrip(".")
    if text in ("0", "-0"):
        return "0"
    return text if value < 0 else "+" + text


def limits_text(diameter: float, fit: Optional[str]) -> str:
    """Text for the drawing: "0/-0.013", "+0.015/+0.002", "±0.0065". Empty when not in the table."""
    found = limits(diameter, fit)
    if not found:
        return ""
    upper, lower = found
    if upper == -lower:
        return "±" + _signed(upper).lstrip("+")
    return f"{_signed(upper)}/{_signed(lower)}"
