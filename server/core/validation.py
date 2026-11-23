"""Deterministic validation (EVENCAD_SPEC.md, section 6.1).

Errors block `finish`. Warnings must be confirmed by the user.
Every text is at most 40 characters, so it fits one display line.
"""

import math
from typing import Optional

from pydantic import BaseModel, Field

from server.core.spec import Chamfer, ShaftSpec, fmt


class Limits(BaseModel):
    max_diameter: float = 500
    max_length: float = 2000
    big_step_ratio: float = 2
    slender_ratio: float = 20
    short_segment: float = 2


class Message(BaseModel):
    code: str
    text: str = Field(max_length=40)
    segment: Optional[int] = None  # 1-based. None = the whole part.


class Report(BaseModel):
    errors: list[Message] = Field(default_factory=list)
    warnings: list[Message] = Field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def chamfer_depth(c: Chamfer) -> float:
    """Radial depth of a chamfer. `size` is along the axis, `angle` is from the axis."""
    return c.size * math.tan(math.radians(c.angle))


def validate(spec: ShaftSpec, limits: Optional[Limits] = None) -> Report:
    lim = limits or Limits()
    r = Report()
    segs = spec.segments

    def err(code, text, segment=None):
        r.errors.append(Message(code=code, text=text, segment=segment))

    def warn(code, text, segment=None):
        r.warnings.append(Message(code=code, text=text, segment=segment))

    if not segs:
        err("NO_SEGMENTS", "No segments yet")
        return r

    for i, s in enumerate(segs, start=1):
        sizes_ok = True
        if s.diameter <= 0:
            err("BAD_DIAMETER", f"Seg {i}: diameter must be above 0", i)
            sizes_ok = False
        elif s.diameter > lim.max_diameter:
            err("DIAMETER_TOO_BIG", f"Seg {i}: diameter over {fmt(lim.max_diameter)}", i)
        if s.length <= 0:
            err("BAD_LENGTH", f"Seg {i}: length must be above 0", i)
            sizes_ok = False
        elif s.length > lim.max_length:
            err("LENGTH_TOO_BIG", f"Seg {i}: length over {fmt(lim.max_length)}", i)
        if not sizes_ok:
            continue

        chamfers = [c for c in (s.chamfer_left, s.chamfer_right) if c]
        if any(not 0 < c.angle < 90 for c in chamfers):
            err("BAD_CHAMFER_ANGLE", f"Seg {i}: chamfer angle not 0-90", i)
            continue
        if sum(c.size for c in chamfers) > s.length:
            err("CHAMFER_TOO_LONG", f"Seg {i}: chamfer longer than segment", i)
            continue

        # Radius that is free at each edge: the full radius at an outer end,
        # the shoulder height at a step.
        left_d = segs[i - 2].diameter if i > 1 else 0
        right_d = segs[i].diameter if i < len(segs) else 0
        for c, neighbour_d in ((s.chamfer_left, left_d), (s.chamfer_right, right_d)):
            if not c:
                continue
            free = (s.diameter - neighbour_d) / 2
            if free <= 0:
                err("CHAMFER_NO_EDGE", f"Seg {i}: no free edge for chamfer", i)
            elif chamfer_depth(c) > free + 1e-9:
                err("CHAMFER_TOO_DEEP", f"Seg {i}: chamfer deeper than edge", i)

    one_segment_too_long = any(s.length > lim.max_length for s in segs)
    if spec.total_length > lim.max_length and not one_segment_too_long:
        err("TOTAL_TOO_LONG", f"Total length over {fmt(lim.max_length)}")

    if any(s.diameter <= 0 or s.length <= 0 for s in segs):
        return r  # ratios make no sense with bad sizes

    for i in range(1, len(segs)):
        a, b = segs[i - 1].diameter, segs[i].diameter
        if a == b:
            warn("EQUAL_NEIGHBOURS", f"Seg {i} and {i + 1}: same diameter", i + 1)
        elif max(a, b) / min(a, b) > lim.big_step_ratio:
            warn("BIG_STEP", f"Large step: {fmt(a)} to {fmt(b)}", i + 1)

    for i, s in enumerate(segs, start=1):
        if s.length < lim.short_segment:
            warn("SHORT_SEGMENT", f"Seg {i}: shorter than {fmt(lim.short_segment)} mm", i)

    if spec.total_length / spec.max_diameter > lim.slender_ratio:
        warn("SLENDER", f"Slender part: length/dia over {fmt(lim.slender_ratio)}")

    return r
