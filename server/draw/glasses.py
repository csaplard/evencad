"""Glasses image: pure black and white, lines 2 px, large text.

The G2 has no pixel API. An image container is at most 288 x 144, four per page
(docs/sdk-notes.md). The default image is a 576 x 144 band. The app shows it as
two tiles, side by side.
"""

import io
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

from server.core.spec import ShaftSpec
from server.draw.model import Dim, Style, draw_shaft

BAND = (576, 144)
LINE = 2
FONT_PX = 17
ROW = FONT_PX + 3


def _font(size: int = FONT_PX):
    return ImageFont.load_default(size=size)


def render_glasses(spec: ShaftSpec, size: tuple[int, int] = BAND, active_segment: Optional[int] = None) -> Image.Image:
    """Return a mode "L" image with only 0 and 255 pixels."""
    w, h = size
    img = Image.new("1", size, 0)
    g = ImageDraw.Draw(img)
    font = _font()
    drawing = draw_shaft(spec, Style(name="glasses", active_segment=active_segment))

    if not spec.segments or drawing.length <= 0 or drawing.max_diameter <= 0:
        text = "Say a diameter and a length"
        tw = g.textlength(text, font=font)
        g.text(((w - tw) / 2, (h - FONT_PX) / 2), text, fill=1, font=font)
        return img.convert("L")

    has_lengths = any(d.kind == "length" for d in drawing.dims)
    top = ROW  # diameter labels
    bottom = ROW * (2 if has_lengths else 1) + 4  # length row(s)
    margin_x = 10
    part_w, part_h = w - 2 * margin_x, h - top - bottom
    scale = min(part_w / drawing.length, part_h / drawing.max_diameter)
    x0 = (w - drawing.length * scale) / 2
    y0 = top + part_h / 2

    def px(p):
        return (round(x0 + p[0] * scale), round(y0 - p[1] * scale))

    for ln in drawing.lines:
        a, b = px(ln.p1), px(ln.p2)
        if ln.layer == "OUTLINE":
            a, b = sorted([a, b])  # same pixels for a line drawn in either direction
            g.line([a, b], fill=1, width=LINE)
        else:
            _dash_dot(g, 4, w - 4, a[1])

    half = round(drawing.max_diameter * scale / 2)
    y_len = y0 + half + 5  # first row under the part
    y_all = y_len + (ROW if has_lengths else 0)

    for d in drawing.dims:
        a, b = px(d.p1), px(d.p2)
        if d.kind == "diameter":
            _dia_label(g, font, d.text.lstrip("Ø"), (a[0] + b[0]) / 2, min(a[1], b[1]) - ROW, w)
        elif d.kind == "length":
            _span(g, font, d, a[0], b[0], y_len, w)
        else:
            _span(g, font, d, a[0], b[0], y_all, w, prefix="L")

    return img.convert("L")


def _dash_dot(g: ImageDraw.ImageDraw, x_from: int, x_to: int, y: int):
    x = x_from
    while x < x_to:
        g.line([(x, y), (min(x + 14, x_to), y)], fill=1, width=1)
        g.point((min(x + 19, x_to), y), fill=1)
        x += 24


def _dia_label(g, font, number, cx, y, w):
    """Diameter sign and number. The sign is drawn by hand: the font has no "Ø"."""
    sign = FONT_PX - 5
    tw = g.textlength(number, font=font)
    total = sign + 3 + tw
    x = round(min(max(cx - total / 2, 0), w - total))
    top = y + 4
    g.ellipse([x, top, x + sign, top + sign], outline=1, width=1)
    g.line([(x - 1, top + sign + 2), (x + sign + 1, top - 2)], fill=1, width=1)
    g.text((x + sign + 3, y), number, fill=1, font=font)


def _span(g, font, d: Dim, xa: int, xb: int, y: int, w: int, prefix: str = ""):
    """Length mark: end ticks, a line, and the number in a gap in the middle."""
    text = prefix + d.text
    tw = g.textlength(text, font=font)
    mid_y = y + ROW // 2
    g.line([(xa, y), (xa, y + ROW - 2)], fill=1, width=1)
    g.line([(xb, y), (xb, y + ROW - 2)], fill=1, width=1)
    if tw + 8 <= xb - xa:
        cx = (xa + xb) / 2
        g.line([(xa, mid_y), (cx - tw / 2 - 3, mid_y)], fill=1, width=1)
        g.line([(cx + tw / 2 + 3, mid_y), (xb, mid_y)], fill=1, width=1)
        g.text((cx - tw / 2, y), text, fill=1, font=font)
    else:
        # No room for the number: the read-back line has the value.
        g.line([(xa, mid_y), (xb, mid_y)], fill=1, width=1)


def glasses_png(spec: ShaftSpec, size: tuple[int, int] = BAND, active_segment: Optional[int] = None) -> bytes:
    buf = io.BytesIO()
    render_glasses(spec, size, active_segment).save(buf, format="PNG")
    return buf.getvalue()


def glasses_tiles(spec: ShaftSpec, active_segment: Optional[int] = None) -> list[bytes]:
    """The band cut into two 288 x 144 PNGs: left tile, right tile."""
    band = render_glasses(spec, BAND, active_segment)
    tiles = []
    for i in range(2):
        buf = io.BytesIO()
        band.crop((i * 288, 0, (i + 1) * 288, 144)).save(buf, format="PNG")
        tiles.append(buf.getvalue())
    return tiles
