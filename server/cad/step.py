"""STEP export: revolve the half profile around the X axis.

`StepExporter` is a small interface, so the CAD library can be swapped.
"""

from pathlib import Path
from typing import Protocol

from server.core.spec import ShaftSpec
from server.draw.model import profile


class StepExporter(Protocol):
    def export(self, spec: ShaftSpec, path: Path) -> Path: ...


class CadQueryStepExporter:
    def export(self, spec: ShaftSpec, path: Path) -> Path:
        import cadquery as cq  # heavy import, only when needed

        pts = profile(spec)
        if len(pts) < 4:
            raise ValueError("The spec has no segments")
        solid = cq.Workplane("XY").polyline(pts).close().revolve(360, (0, 0, 0), (1, 0, 0))
        cq.exporters.export(solid, str(path), exportType="STEP")
        return path


def default_step_exporter() -> StepExporter:
    return CadQueryStepExporter()
