"""Vector model of the shaft side view (EVENCAD_SPEC.md, section 6.3).

`draw_shaft` is the single source for the glasses image, the DXF and the PDF.
Coordinates are millimetres. X runs along the axis from 0. Y is up. The axis is y = 0.
"""

from dataclasses import dataclass, field
from typing import Literal, Optional

from server.core.fits import limits_text
from server.core.keyway import keyway_size
from server.core.spec import ShaftSpec, fmt
from server.core.validation import chamfer_depth

Point = tuple[float, float]


@dataclass(frozen=True)
class Line:
    p1: Point
    p2: Point
    layer: Literal["OUTLINE", "CENTER"]


@dataclass(frozen=True)
class Dim:
    kind: Literal["length", "diameter", "overall"]
    p1: Point  # the two measured points
    p2: Point
    value: float
    text: str  # "40", "Ø30", "130"
    segment: Optional[int]  # 1-based, None for the overall length


@dataclass(frozen=True)
class Slot:
    """A keyway seen from above: an oblong with round ends, centred on the axis."""

    x1: float
    x2: float
    width: float
    depth: float
    segment: int  # 1-based
    radius: float  # radius of its segment


@dataclass(frozen=True)
class Mark:
    """A surface roughness note. (x, y) is the point on the top outline that it points at."""

    x: float
    y: float
    text: str  # "Ra 1.6"
    segment: int


@dataclass(frozen=True)
class Style:
    name: Literal["glasses", "sheet"] = "sheet"
    # Glasses only: with more segments than this, show the dimensions of the
    # active segment plus the overall length.
    max_full_dims: int = 4
    active_segment: Optional[int] = None  # default: the last segment


@dataclass
class Drawing:
    lines: list[Line] = field(default_factory=list)
    dims: list[Dim] = field(default_factory=list)
    slots: list[Slot] = field(default_factory=list)
    marks: list[Mark] = field(default_factory=list)
    length: float = 0
    max_diameter: float = 0


def profile(spec: ShaftSpec) -> list[Point]:
    """Upper half outline as (x, radius) points, from (0, 0) to (L, 0)."""
    pts: list[Point] = [(0.0, 0.0)]
    x = 0.0
    for s in spec.segments:
        r = s.diameter / 2
        x_end = x + s.length
        if s.chamfer_left:
            pts += [(x, r - chamfer_depth(s.chamfer_left)), (x + s.chamfer_left.size, r)]
        else:
            pts.append((x, r))
        if s.chamfer_right:
            pts += [(x_end - s.chamfer_right.size, r), (x_end, r - chamfer_depth(s.chamfer_right))]
        else:
            pts.append((x_end, r))
        x = x_end
    pts.append((x, 0.0))

    clean: list[Point] = []
    for p in pts:
        if not clean or abs(p[0] - clean[-1][0]) > 1e-9 or abs(p[1] - clean[-1][1]) > 1e-9:
            clean.append(p)
    return clean


def slots(spec: ShaftSpec) -> list[Slot]:
    """One slot per keyway that has a table size. It sits in the middle of the cylindrical part,
    between the chamfers of its segment."""
    out: list[Slot] = []
    x = 0.0
    for i, s in enumerate(spec.segments, start=1):
        size = keyway_size(s.diameter) if s.keyway else None
        if size and s.keyway.length > size.width:
            left = x + (s.chamfer_left.size if s.chamfer_left else 0)
            right = x + s.length - (s.chamfer_right.size if s.chamfer_right else 0)
            mid = (left + right) / 2
            out.append(Slot(mid - s.keyway.length / 2, mid + s.keyway.length / 2, size.width, size.depth, i, s.diameter / 2))
        x += s.length
    return out


def draw_shaft(spec: ShaftSpec, style: Optional[Style] = None) -> Drawing:
    style = style or Style()
    d = Drawing(length=spec.total_length, max_diameter=spec.max_diameter)
    segs = spec.segments
    if not segs:
        return d

    pts = profile(spec)

    # Outline: upper half, mirrored lower half.
    for a, b in zip(pts, pts[1:]):
        d.lines.append(Line(a, b, "OUTLINE"))
        if a[1] != 0 or b[1] != 0:
            d.lines.append(Line((a[0], -a[1]), (b[0], -b[1]), "OUTLINE"))

    # Visible edges: a vertical line wherever the outline has an inner corner.
    # Seen from the side, each circular edge is a line across the part.
    edge_r: dict[float, float] = {}
    for x, r in pts:
        if 0 < x < d.length:
            edge_r[x] = max(edge_r.get(x, 0), r)
    for x, r in edge_r.items():
        d.lines.append(Line((x, r), (x, -r), "OUTLINE"))

    d.slots = slots(spec)

    # Centre line, a little longer than the part.
    over = max(2.0, 0.03 * d.length)
    d.lines.append(Line((-over, 0), (d.length + over, 0), "CENTER"))

    # Dimensions.
    n = len(segs)
    active = style.active_segment or n
    reduced = style.name == "glasses" and n > style.max_full_dims
    x = 0.0
    for i, s in enumerate(segs, start=1):
        r = s.diameter / 2
        if not reduced or i == active:
            if n > 1:
                d.dims.append(Dim("length", (x, -r), (x + s.length, -r), s.length, fmt(s.length), i))
            mid = x + s.length / 2
            for slot in d.slots:
                if slot.segment == i and slot.x2 < x + s.length:
                    mid = (slot.x2 + x + s.length) / 2  # beside the keyway, not across it
            label = "Ø" + fmt(s.diameter) + (f" {s.fit}" if s.fit else "")
            # The sheet also gives the limits of the fit, from the table. The glasses have no room for them.
            numbers = limits_text(s.diameter, s.fit) if style.name == "sheet" else ""
            if numbers:
                label += f" ({numbers})"
            d.dims.append(Dim("diameter", (mid, -r), (mid, r), s.diameter, label, i))
        if s.roughness:
            d.marks.append(Mark(x + s.length / 4, r, f"Ra {fmt(s.roughness)}", i))
        x += s.length
    r_max = d.max_diameter / 2
    d.dims.append(Dim("overall", (0, -r_max), (d.length, -r_max), d.length, fmt(d.length), None))
    return d
