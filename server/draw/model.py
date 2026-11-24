"""Vector model of the shaft side view (SAYCAD_SPEC.md, section 6.3).

`draw_shaft` is the single source for the glasses image, the DXF and the PDF.
Coordinates are millimetres. X runs along the axis from 0. Y is up. The axis is y = 0.
"""

import math
from dataclasses import dataclass, field
from typing import Literal, Optional

from server.core.fits import STANDARD as FIT_STANDARD
from server.core.fits import limits_text
from server.core.keyway import keyway_size
from server.core.spec import ShaftSpec, end_size, fmt
from server.core.validation import chamfer_depth

Point = tuple[float, float]


@dataclass(frozen=True)
class Line:
    p1: Point
    p2: Point
    layer: Literal["OUTLINE", "CENTER"]
    curve: bool = False  # a short piece of a fillet arc. The DXF draws the real arc instead.


@dataclass(frozen=True)
class Arc:
    """A fillet in the upper half of the side view. Angles in degrees, counter-clockwise."""

    cx: float
    cy: float
    radius: float
    start: float
    end: float
    step: int  # 1-based step number


@dataclass(frozen=True)
class Node:
    """One point of the upper half outline."""

    x: float
    r: float
    arc: Optional[int] = None  # index into arcs(spec) when the point lies on a fillet
    smooth: bool = False  # no visible edge here: inside an arc, or where it runs into the cylinder


@dataclass(frozen=True)
class Note:
    """A line of text for the sheet."""

    text: str
    segment: int


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
    arcs: list[Arc] = field(default_factory=list)
    notes: list[Note] = field(default_factory=list)
    marks: list[Mark] = field(default_factory=list)
    length: float = 0
    max_diameter: float = 0


ARC_STEPS = 6  # straight pieces per fillet in the point outline


def arcs(spec: ShaftSpec) -> list[Arc]:
    """The fillets, left to right."""
    out: list[Arc] = []
    x = 0.0
    for i, s in enumerate(spec.segments, start=1):
        r = s.diameter / 2
        if s.fillet_left:
            out.append(Arc(x + s.fillet_left, r + s.fillet_left, s.fillet_left, 180, 270, i - 1))
        if s.fillet_right:
            out.append(Arc(x + s.length - s.fillet_right, r + s.fillet_right, s.fillet_right, 270, 360, i))
        x += s.length
    return out


def outline(spec: ShaftSpec) -> list[Node]:
    """Upper half outline, from (0, 0) to (L, 0). Fillets are short straight pieces."""
    nodes: list[Node] = [Node(0.0, 0.0)]
    all_arcs = arcs(spec)

    def arc_nodes(arc: Arc, tangent_first: bool) -> list[Node]:
        number = all_arcs.index(arc)
        out = []
        for k in range(ARC_STEPS + 1):
            a = math.radians(arc.start + (arc.end - arc.start) * k / ARC_STEPS)
            on_cylinder = k == (0 if tangent_first else ARC_STEPS)
            on_shoulder = k == (ARC_STEPS if tangent_first else 0)
            # The end points are exact, so they match the neighbour points.
            px = arc.cx - arc.radius if (on_shoulder and not tangent_first) else arc.cx + arc.radius if on_shoulder else arc.cx if on_cylinder else arc.cx + arc.radius * math.cos(a)
            pr = arc.cy - arc.radius if on_cylinder else arc.cy if on_shoulder else arc.cy + arc.radius * math.sin(a)
            out.append(Node(px, pr, number, smooth=not on_shoulder))
        return out

    x = 0.0
    for i, s in enumerate(spec.segments, start=1):
        r = s.diameter / 2
        x_end = x + s.length
        if s.chamfer_left:
            nodes += [Node(x, r - chamfer_depth(s.chamfer_left)), Node(x + s.chamfer_left.size, r)]
        elif s.fillet_left:
            nodes += arc_nodes(next(a for a in all_arcs if a.step == i - 1 and a.start == 180), tangent_first=False)
        elif s.undercut_left:
            u = s.undercut_left
            nodes += [Node(x, r - u.depth), Node(x + u.width, r - u.depth), Node(x + u.width, r)]
        else:
            nodes.append(Node(x, r))
        if s.chamfer_right:
            nodes += [Node(x_end - s.chamfer_right.size, r), Node(x_end, r - chamfer_depth(s.chamfer_right))]
        elif s.fillet_right:
            nodes += arc_nodes(next(a for a in all_arcs if a.step == i and a.start == 270), tangent_first=True)
        elif s.undercut_right:
            u = s.undercut_right
            nodes += [Node(x_end - u.width, r), Node(x_end - u.width, r - u.depth), Node(x_end, r - u.depth)]
        else:
            nodes.append(Node(x_end, r))
        x = x_end
    nodes.append(Node(x, 0.0))

    clean: list[Node] = []
    for n in nodes:
        if clean and abs(n.x - clean[-1].x) <= 1e-9 and abs(n.r - clean[-1].r) <= 1e-9:
            if n.arc is not None and clean[-1].arc is None:
                clean[-1] = Node(clean[-1].x, clean[-1].r, n.arc, smooth=False)  # same place: keep the corner
            continue
        clean.append(n)
    return clean


def profile(spec: ShaftSpec) -> list[Point]:
    """Upper half outline as (x, radius) points, from (0, 0) to (L, 0)."""
    return [(n.x, n.r) for n in outline(spec)]


def notes(spec: ShaftSpec) -> list[Note]:
    """Text lines for the sheet: sizes that have no dimension of their own."""
    out: list[Note] = []
    for i, s in enumerate(spec.segments, start=1):
        for side, step in (("left", i - 1), ("right", i)):
            fillet, cut = getattr(s, f"fillet_{side}"), getattr(s, f"undercut_{side}")
            if fillet:
                out.append(Note(f"Fillet R{fmt(fillet)} at step {step}", i))
            if cut:
                out.append(Note(f"Undercut at step {step}: {fmt(cut.width)} wide, {fmt(cut.depth)} deep (plain groove)", i))
    # The limits of each fit, from the table. A fit that is not in the table has no line.
    for i, s in enumerate(spec.segments, start=1):
        numbers = limits_text(s.diameter, s.fit)
        if numbers:
            out.append(Note(f"Ø{fmt(s.diameter)} {s.fit}: {numbers} ({FIT_STANDARD})", i))
    return out


def slots(spec: ShaftSpec) -> list[Slot]:
    """One slot per keyway that has a table size. It sits in the middle of the cylindrical part,
    between the chamfers of its segment."""
    out: list[Slot] = []
    x = 0.0
    for i, s in enumerate(spec.segments, start=1):
        size = keyway_size(s.diameter) if s.keyway else None
        if size and s.keyway.length > size.width:
            left = x + end_size(s, "left")
            right = x + s.length - end_size(s, "right")
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

    nodes = outline(spec)

    # Outline: upper half, mirrored lower half.
    for m, n in zip(nodes, nodes[1:]):
        a, b = (m.x, m.r), (n.x, n.r)
        curve = m.arc is not None and m.arc == n.arc
        d.lines.append(Line(a, b, "OUTLINE", curve))
        if a[1] != 0 or b[1] != 0:
            d.lines.append(Line((a[0], -a[1]), (b[0], -b[1]), "OUTLINE", curve))

    # Visible edges: a vertical line wherever the outline has an inner corner.
    # Seen from the side, each circular edge is a line across the part.
    # A fillet runs smoothly into the cylinder, so it has no edge there.
    edge_r: dict[float, float] = {}
    for n in nodes:
        if 0 < n.x < d.length and not n.smooth:
            edge_r[n.x] = max(edge_r.get(n.x, 0), n.r)
    for x, r in edge_r.items():
        d.lines.append(Line((x, r), (x, -r), "OUTLINE"))

    d.slots = slots(spec)
    d.arcs = arcs(spec)
    d.notes = notes(spec)

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
            d.dims.append(Dim("diameter", (mid, -r), (mid, r), s.diameter, label, i))
        if s.roughness:
            d.marks.append(Mark(x + s.length / 4, r, f"Ra {fmt(s.roughness)}", i))
        x += s.length
    r_max = d.max_diameter / 2
    d.dims.append(Dim("overall", (0, -r_max), (d.length, -r_max), d.length, fmt(d.length), None))
    return d
