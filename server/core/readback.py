"""Read-back text for the display (EVENCAD_SPEC.md, section 6.2).

Built from the spec by a template. The AI never writes this text.
Example: "3 steps  Ø30×40  Ø25×60  Ø20×30  C1 right  L130"
"""

from server.core.keyway import keyway_size
from server.core.spec import Chamfer, ShaftSpec, fmt

MAX_CHARS = 90  # about two lines on the 576 px display
SEP = "  "


def _chamfer(c: Chamfer, place: str) -> str:
    angle = "" if c.angle == 45 else f"×{fmt(c.angle)}°"
    return f"C{fmt(c.size)}{angle} {place}"


def readback(spec: ShaftSpec) -> str:
    segs = spec.segments
    if not segs:
        return "No segments yet"

    n = len(segs)
    head = f"{n} step" + ("" if n == 1 else "s")
    dims = [f"Ø{fmt(s.diameter)}×{fmt(s.length)}" for s in segs]
    tail = f"L{fmt(spec.total_length)}"

    chamfers = []
    for i, s in enumerate(segs, start=1):
        if s.chamfer_left:
            chamfers.append(_chamfer(s.chamfer_left, "left" if i == 1 else f"step {i - 1}"))
        if s.chamfer_right:
            chamfers.append(_chamfer(s.chamfer_right, "right" if i == n else f"step {i}"))

    # Keyway: "KW2 8×20" = on segment 2, 8 wide (from the table), 20 long.
    for i, s in enumerate(segs, start=1):
        if s.keyway:
            size = keyway_size(s.diameter)
            chamfers.append(f"KW{i} {fmt(size.width) if size else '?'}×{fmt(s.keyway.length)}")

    text = SEP.join([head, *dims, *chamfers, tail])
    if len(text) <= MAX_CHARS:
        return text

    # Too long: keep the newest (last) segments and the total length.
    kept = [dims[-1]]
    for d in reversed(dims[:-1]):
        if len(SEP.join([head, "…", d, *kept, tail])) > MAX_CHARS:
            break
        kept.insert(0, d)
    return SEP.join([head, "…", *kept, tail])
