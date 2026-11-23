"""Keyway sizes from a table. The AI never gives a keyway width or depth.

Parallel key, DIN 6885-1, form A (round ends). The rows are:
shaft diameter over, up to, key width b, key height h, depth in the shaft t1.
All values are millimetres.

Check this table against your copy of the standard before real use (docs/open-questions.md).
"""

from dataclasses import dataclass
from typing import Optional

STANDARD = "DIN 6885-1 A"

_TABLE = [
    (6, 8, 2, 2, 1.2),
    (8, 10, 3, 3, 1.8),
    (10, 12, 4, 4, 2.5),
    (12, 17, 5, 5, 3.0),
    (17, 22, 6, 6, 3.5),
    (22, 30, 8, 7, 4.0),
    (30, 38, 10, 8, 5.0),
    (38, 44, 12, 8, 5.0),
    (44, 50, 14, 9, 5.5),
    (50, 58, 16, 10, 6.0),
    (58, 65, 18, 11, 7.0),
    (65, 75, 20, 12, 7.5),
    (75, 85, 22, 14, 9.0),
    (85, 95, 25, 14, 9.0),
    (95, 110, 28, 16, 10.0),
    (110, 130, 32, 18, 11.0),
    (130, 150, 36, 20, 12.0),
    (150, 170, 40, 22, 13.0),
    (170, 200, 45, 25, 15.0),
    (200, 230, 50, 28, 17.0),
]


@dataclass(frozen=True)
class KeywaySize:
    width: float  # b
    key_height: float  # h
    depth: float  # t1, measured from the shaft surface


def keyway_size(diameter: float) -> Optional[KeywaySize]:
    """Size for a shaft diameter. None when the diameter is outside the table (6 < d <= 230)."""
    for over, up_to, b, h, t1 in _TABLE:
        if over < diameter <= up_to:
            return KeywaySize(width=b, key_height=h, depth=t1)
    return None
