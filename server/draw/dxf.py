"""DXF sheet: A4 landscape, layers, real DIMENSION entities, title block.

Sheet units are millimetres of paper. The part is drawn at a standard scale.
The dimension style measures in part millimetres (dimlfac = 1 / scale).
"""

from datetime import date
from pathlib import Path

import ezdxf
from ezdxf.document import Drawing as DxfDoc
from ezdxf.enums import TextEntityAlignment

from server.core.keyway import STANDARD
from server.core.mass import mass
from server.core.spec import ShaftSpec, fmt
from server.draw.model import Style, draw_shaft

SHEET_W, SHEET_H = 297.0, 210.0
MARGIN = 10.0
TITLE_H = 40.0
TEXT_STYLE = "LiberationSans"  # a TrueType style from ezdxf setup: it has the dash and accents
DRAFT_MARK = "DRAFT – requires engineering approval"
SCALES = [(5, "5:1"), (2, "2:1"), (1, "1:1"), (0.5, "1:2"), (0.2, "1:5"), (0.1, "1:10"), (0.05, "1:20")]


def status_mark(spec: ShaftSpec) -> str:
    if spec.status == "approved" and spec.approved_by:
        return f"Approved for review by: {spec.approved_by} – not a manufacturing release"
    return DRAFT_MARK


def pick_scale(length: float, max_diameter: float) -> tuple[float, str]:
    """Largest standard scale that leaves room for the dimensions."""
    room_w = SHEET_W - 2 * MARGIN - 50
    room_h = SHEET_H - 2 * MARGIN - TITLE_H - 85
    for factor, name in SCALES:
        if length * factor <= room_w and max_diameter * factor <= room_h:
            return factor, name
    return SCALES[-1]


def build_dxf(spec: ShaftSpec) -> DxfDoc:
    doc = ezdxf.new("R2010", setup=True)  # setup=True adds the CENTER linetype and the EZDXF dim style
    doc.units = ezdxf.units.MM
    doc.layers.add("OUTLINE", color=7, lineweight=50)
    doc.layers.add("CENTER", color=1, linetype="CENTER", lineweight=18)
    doc.layers.add("DIM", color=3, lineweight=18)
    doc.layers.add("TEXT", color=7, lineweight=18)
    doc.layers.add("FRAME", color=7, lineweight=35)
    msp = doc.modelspace()

    drawing = draw_shaft(spec, Style(name="sheet"))
    scale, scale_name = pick_scale(drawing.length, drawing.max_diameter)

    # Part origin on the sheet: centred in the area above the title block.
    area_bottom = MARGIN + TITLE_H
    ox = (SHEET_W - drawing.length * scale) / 2
    oy = area_bottom + (SHEET_H - MARGIN - area_bottom) / 2 + 8

    def pt(p):
        return (ox + p[0] * scale, oy + p[1] * scale)

    for ln in drawing.lines:
        msp.add_line(pt(ln.p1), pt(ln.p2), dxfattribs={"layer": ln.layer})

    # Keyways: seen from above, an oblong with round ends on the axis. Sizes go into a note.
    for n, slot in enumerate(drawing.slots):
        half = slot.width / 2
        left, right = (slot.x1 + half, 0), (slot.x2 - half, 0)
        for sign in (1, -1):
            msp.add_line(pt((left[0], sign * half)), pt((right[0], sign * half)), dxfattribs={"layer": "OUTLINE"})
        msp.add_arc(pt(left), half * scale, 90, 270, dxfattribs={"layer": "OUTLINE"})
        msp.add_arc(pt(right), half * scale, 270, 90, dxfattribs={"layer": "OUTLINE"})
        note = (f"Keyway on segment {slot.segment}: {fmt(slot.width)} × {fmt(slot.x2 - slot.x1)}, "
                f"depth {fmt(slot.depth)}, centred ({STANDARD})")
        msp.add_text(note, height=3.0, dxfattribs={"layer": "TEXT", "style": TEXT_STYLE}).set_placement(
            (MARGIN + 4, SHEET_H - MARGIN - 8 - 5 * n), align=TextEntityAlignment.LEFT)

    dim_attribs = {"layer": "DIM"}
    override = {"dimlfac": 1 / scale, "dimtxt": 3.0, "dimasz": 2.5, "dimexo": 1.0, "dimexe": 1.5, "dimgap": 1.0, "dimdec": 2, "dimzin": 8, "dimclrt": 3}
    half = drawing.max_diameter * scale / 2
    y_len = oy - half - 12
    y_all = y_len - 10
    for d in drawing.dims:
        a, b = pt(d.p1), pt(d.p2)
        if d.kind == "length":
            dim = msp.add_linear_dim(base=(a[0], y_len), p1=a, p2=b, dimstyle="EZDXF", override=override, dxfattribs=dim_attribs)
        elif d.kind == "overall":
            dim = msp.add_linear_dim(base=(a[0], y_all), p1=a, p2=b, dimstyle="EZDXF", override=override, dxfattribs=dim_attribs)
        else:
            # Diameter: a vertical dimension across the segment, placed above the part
            # so the text stays readable.
            x = a[0]
            dim = msp.add_linear_dim(
                base=(x, oy), p1=a, p2=b, angle=90, text="Ø<>", dimstyle="EZDXF",
                override=override, dxfattribs=dim_attribs,
            )
        dim.render()

    _frame_and_title(msp, spec, scale_name)
    return doc


def _frame_and_title(msp, spec: ShaftSpec, scale_name: str):
    f = {"layer": "FRAME"}
    x0, y0, x1, y1 = MARGIN, MARGIN, SHEET_W - MARGIN, SHEET_H - MARGIN
    msp.add_lwpolyline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], close=True, dxfattribs=f)
    ty = y0 + TITLE_H
    msp.add_line((x0, ty), (x1, ty), dxfattribs=f)
    # Title block: three columns, four rows.
    c1, c2 = x0 + 120, x0 + 200
    for x in (c1, c2):
        msp.add_line((x, y0), (x, ty), dxfattribs=f)
    for i in (1, 2, 3):
        y = y0 + i * TITLE_H / 4
        msp.add_line((c1, y), (x1, y), dxfattribs=f)

    def text(s, x, y, h=3.0):
        msp.add_text(s, height=h, dxfattribs={"layer": "TEXT", "style": TEXT_STYLE}).set_placement((x, y), align=TextEntityAlignment.LEFT)

    text(spec.title, x0 + 4, y0 + 26, h=7)
    text("EvenCAD – stepped shaft, side view", x0 + 4, y0 + 16)
    text(f"Total length {fmt(spec.total_length)}   Max diameter {fmt(spec.max_diameter)}", x0 + 4, y0 + 8)

    m = mass(spec)
    if m:
        text(f"Mass: {m['text']} ({m['material']}, {fmt(m['density'])} g/cm³) – estimate", x0 + 4, y0 + 2.5, h=2.5)

    rows_left = [f"Material: {spec.material or '-'}", "Units: mm", f"Scale: {scale_name}", f"Date: {date.today().isoformat()}"]
    approved = spec.status == "approved" and spec.approved_by
    when = spec.approved_at.date().isoformat() if approved and spec.approved_at else ""
    rows_right = [f"Session: {spec.id}", f"Status: {spec.status.upper()}", f"Approved by: {spec.approved_by if approved else ''}", f"Approval date: {when}"]
    for i, (left, right) in enumerate(zip(rows_left, rows_right)):
        y = ty - (i + 1) * TITLE_H / 4 + 3.5
        text(left, c1 + 3, y)
        text(right, c2 + 3, y)

    # The mark is large and sits above the title block. It is never left out.
    msp.add_text(status_mark(spec), height=6, dxfattribs={"layer": "TEXT", "style": TEXT_STYLE}).set_placement((x0 + 4, ty + 5), align=TextEntityAlignment.LEFT)


def write_dxf(spec: ShaftSpec, path: Path) -> Path:
    build_dxf(spec).saveas(path)
    return path
