"""3D line view of the shaft for the glasses.

The glasses have no 3D engine. They show images only, and one refresh takes about
a second on the device. So the view turns in steps: each step is one new image.

The picture is a hidden-line drawing made with the painter's method. The shaft is a
row of coaxial bands. They are drawn from far to near as black shapes with a white
outline, so nearer parts cover the parts behind them.
"""

import math
from typing import Optional

from PIL import Image, ImageDraw

from server.core.spec import ShaftSpec
from server.draw.glasses import BAND, FONT_PX, LINE, _font, segment_span
from server.draw.model import Slot, profile, slots

PITCH_DEG = 20  # the view looks down a little, so circles show as ellipses
YAW_STEPS = (30, 60, 90, 120, 150)  # 90 = end view
CIRCLE_POINTS = 48


def _projector(yaw_deg: float, pitch_deg: float, length: float):
    cy, sy = math.cos(math.radians(yaw_deg)), math.sin(math.radians(yaw_deg))
    cp, sp = math.cos(math.radians(pitch_deg)), math.sin(math.radians(pitch_deg))

    def project(x: float, y: float, z: float) -> tuple[float, float]:
        x -= length / 2
        x1 = x * cy + z * sy
        z1 = -x * sy + z * cy
        return (x1, -(y * cp - z1 * sp))  # screen x, screen y (down is positive)

    return project


def _circle(project, x: float, r: float) -> list[tuple[float, float]]:
    if r <= 0:
        return [project(x, 0, 0)]
    return [
        project(x, r * math.cos(2 * math.pi * i / CIRCLE_POINTS), r * math.sin(2 * math.pi * i / CIRCLE_POINTS))
        for i in range(CIRCLE_POINTS)
    ]


def _hull(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Convex hull (monotone chain). The outline of a band is the hull of its two end circles."""
    pts = sorted(set(points))
    if len(pts) <= 2:
        return pts

    def half(seq):
        out: list[tuple[float, float]] = []
        for p in seq:
            while len(out) >= 2 and (out[-1][0] - out[-2][0]) * (p[1] - out[-2][1]) - (out[-1][1] - out[-2][1]) * (p[0] - out[-2][0]) <= 0:
                out.pop()
            out.append(p)
        return out[:-1]

    return half(pts) + half(reversed(pts))


def _slot_outline(project, slot: Slot) -> list[tuple[float, float]]:
    """The keyway edge on the cylinder surface, as projected points. The keyway is on top (+Y)."""
    half = slot.width / 2
    flat = []  # (x, z) around the oblong
    for cx, start in ((slot.x2 - half, -90), (slot.x1 + half, 90)):
        for k in range(9):
            a = math.radians(start + 180 * k / 8)
            flat.append((cx + half * math.cos(a), half * math.sin(a)))
    return [project(x, math.sqrt(max(slot.radius**2 - z**2, 0)), z) for x, z in flat]


def render_glasses_3d(
    spec: ShaftSpec, yaw_deg: float, size: tuple[int, int] = BAND, pitch_deg: float = PITCH_DEG,
    active_segment: Optional[int] = None,
) -> Image.Image:
    """Return a mode "L" image with only 0 and 255 pixels.

    `active_segment` (1-based) is drawn with thicker lines. One segment alone is never marked.
    """
    w, h = size
    img = Image.new("1", size, 0)
    g = ImageDraw.Draw(img)
    font = _font()
    if not spec.segments or spec.total_length <= 0 or spec.max_diameter <= 0:
        text = "Say a diameter and a length"
        g.text(((w - g.textlength(text, font=font)) / 2, (h - FONT_PX) / 2), text, fill=1, font=font)
        return img.convert("L")

    pts = profile(spec)
    project = _projector(yaw_deg, pitch_deg, spec.total_length)
    # Far to near: the end of the shaft that points away from the viewer comes first.
    if math.sin(math.radians(yaw_deg)) > 0:
        pts = pts[::-1]
    rings = [_circle(project, x, r) for x, r in pts]
    span = segment_span(spec, active_segment) if len(spec.segments) > 1 else None

    key_slots = slots(spec)

    def is_active(a, b) -> bool:
        """True for a band that is part of the active segment (its body or its chamfers)."""
        lo, hi = sorted((a[0], b[0]))
        return bool(span) and hi - lo > 1e-9 and lo >= span[0] - 1e-9 and hi <= span[1] + 1e-9

    # Fit the whole picture into the image.
    xs = [p[0] for ring in rings for p in ring]
    ys = [p[1] for ring in rings for p in ring]
    margin = 8
    label_w = 70  # room for the view label in the top left corner
    span_x, span_y = max(xs) - min(xs) or 1, max(ys) - min(ys) or 1
    scale = min((w - 2 * margin - label_w) / span_x, (h - 2 * margin) / span_y)
    cx, cy = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2

    def px(p):
        return (round(w / 2 + label_w / 4 + (p[0] - cx) * scale), round(h / 2 + (p[1] - cy) * scale))

    def outline(shape, fill, width=LINE):
        if len(shape) >= 3:
            g.polygon(shape, fill=fill)
        if len(shape) >= 2:
            g.line(shape + [shape[0]], fill=1, width=width, joint="curve")

    for i, (far, near) in enumerate(zip(rings, rings[1:])):
        width = LINE + 2 if is_active(pts[i], pts[i + 1]) else LINE
        outline([px(p) for p in _hull(far + near)], fill=0, width=width)  # the band covers what is behind it
        if len(near) > 1:
            outline([px(p) for p in near], fill=None, width=width)  # its near edge is a visible circle
        lo, hi = sorted((pts[i][0], pts[i + 1][0]))
        for slot in key_slots:
            if lo - 1e-9 <= slot.x1 and slot.x2 <= hi + 1e-9:
                edge = [px(p) for p in _slot_outline(project, slot)]
                g.line(edge + [edge[0]], fill=1, width=1)

    g.text((4, 2), f"3D {round(yaw_deg)}°", fill=1, font=font)
    return img.convert("L")


def glasses_3d_tiles(spec: ShaftSpec, yaw_deg: float, active_segment: Optional[int] = None) -> list[bytes]:
    """The band cut into two 288 x 144 PNGs: left tile, right tile."""
    import io

    band = render_glasses_3d(spec, yaw_deg, active_segment=active_segment)
    tiles = []
    for i in range(2):
        buf = io.BytesIO()
        band.crop((i * 288, 0, (i + 1) * 288, 144)).save(buf, format="PNG")
        tiles.append(buf.getvalue())
    return tiles
