"""PDF sheet, made from the DXF (one A4 landscape page)."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # no window, works on a server

import matplotlib.pyplot as plt  # noqa: E402
from ezdxf.addons.drawing import Frontend, RenderContext  # noqa: E402
from ezdxf.addons.drawing.config import BackgroundPolicy, ColorPolicy, Configuration  # noqa: E402
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend  # noqa: E402

from server.core.spec import ShaftSpec  # noqa: E402
from server.draw.dxf import SHEET_H, SHEET_W, build_dxf  # noqa: E402

MM_PER_INCH = 25.4


def write_pdf(spec: ShaftSpec, path: Path) -> Path:
    doc = build_dxf(spec)
    fig = plt.figure(figsize=(SHEET_W / MM_PER_INCH, SHEET_H / MM_PER_INCH))
    try:
        ax = fig.add_axes([0, 0, 1, 1])
        config = Configuration(background_policy=BackgroundPolicy.WHITE, color_policy=ColorPolicy.BLACK)
        Frontend(RenderContext(doc), MatplotlibBackend(ax), config=config).draw_layout(doc.modelspace(), finalize=False)
        ax.set_xlim(0, SHEET_W)
        ax.set_ylim(0, SHEET_H)
        ax.set_aspect("equal", adjustable="box")
        ax.axis("off")
        fig.savefig(path, format="pdf")
    finally:
        plt.close(fig)
    return path
