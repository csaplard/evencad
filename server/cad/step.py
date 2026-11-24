"""STEP export: revolve the half profile around the X axis.

`StepExporter` is a small interface, so the CAD library can be swapped.
"""

import math
from pathlib import Path
from typing import Protocol

from server.core.spec import ShaftSpec
from server.draw.model import arcs, outline, slots


class StepExporter(Protocol):
    def export(self, spec: ShaftSpec, path: Path) -> Path: ...


def build_solid(spec: ShaftSpec):
    """The shaft as a CadQuery solid: the revolved profile, minus the keyways."""
    import cadquery as cq  # heavy import, only when needed

    nodes = outline(spec)
    if len(nodes) < 4:
        raise ValueError("The spec has no segments")
    rounds = arcs(spec)
    wire = cq.Workplane("XY").moveTo(nodes[0].x, nodes[0].r)
    for at in range(1, len(nodes)):
        before, node = nodes[at - 1], nodes[at]
        if node.arc is None or node.arc != before.arc:
            wire = wire.lineTo(node.x, node.r)
        elif at + 1 == len(nodes) or nodes[at + 1].arc != node.arc:
            # The last point of a fillet: one true arc from its first point, through its middle.
            arc = rounds[node.arc]
            mid = math.radians((arc.start + arc.end) / 2)
            wire = wire.threePointArc((arc.cx + arc.radius * math.cos(mid), arc.cy + arc.radius * math.sin(mid)), (node.x, node.r))
    solid = wire.close().revolve(360, (0, 0, 0), (1, 0, 0))
    for slot in slots(spec):
        # An oblong in the XY plane, pulled up along Z, then turned so that it stands on top (+Y).
        height = slot.depth + 1
        cutter = (
            cq.Workplane("XY").center((slot.x1 + slot.x2) / 2, 0).slot2D(slot.x2 - slot.x1, slot.width).extrude(height)
            .rotate((0, 0, 0), (1, 0, 0), -90)
            .translate((0, slot.radius - slot.depth, 0))
        )
        solid = solid.cut(cutter)
    return solid


class CadQueryStepExporter:
    def export(self, spec: ShaftSpec, path: Path) -> Path:
        import cadquery as cq  # heavy import, only when needed

        solid = build_solid(spec)
        cq.exporters.export(solid, str(path), exportType="STEP")
        return path


def default_step_exporter() -> StepExporter:
    return CadQueryStepExporter()
