"""Build all output files of a session into data/out/<session id>/."""

from pathlib import Path
from typing import Optional

from server.cad.step import StepExporter, default_step_exporter
from server.core.spec import ShaftSpec
from server.core.validation import validate
from server.draw.dxf import write_dxf
from server.draw.pdf import write_pdf

FILE_NAMES = {"step": "shaft.step", "dxf": "shaft.dxf", "pdf": "shaft.pdf"}


class ExportBlocked(ValueError):
    """The spec has validation errors. No files are made."""


def export_all(spec: ShaftSpec, out_dir: Path, step_exporter: Optional[StepExporter] = None) -> dict[str, Path]:
    report = validate(spec)
    if not report.ok:
        raise ExportBlocked("; ".join(m.text for m in report.errors))
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {kind: out_dir / name for kind, name in FILE_NAMES.items()}
    (step_exporter or default_step_exporter()).export(spec, paths["step"])
    write_dxf(spec, paths["dxf"])
    write_pdf(spec, paths["pdf"])
    return paths


def rebuild_sheets(spec: ShaftSpec, out_dir: Path) -> None:
    """After approval: only the title block changes, so only DXF and PDF are rebuilt."""
    out_dir.mkdir(parents=True, exist_ok=True)
    write_dxf(spec, out_dir / FILE_NAMES["dxf"])
    write_pdf(spec, out_dir / FILE_NAMES["pdf"])
