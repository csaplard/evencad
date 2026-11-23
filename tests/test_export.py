"""Exports: STEP, DXF, PDF (EVENCAD_SPEC.md, section 6.4). Each file is loaded again."""

import math
from datetime import datetime, timezone

import ezdxf
import pytest
from pypdf import PdfReader

from server.core.spec import Chamfer, Segment, ShaftSpec
from server.draw.dxf import DRAFT_MARK, pick_scale, status_mark, write_dxf
from server.export import ExportBlocked, export_all, rebuild_sheets


def demo(**extra):
    return ShaftSpec(
        id="s_20261123_aaaaaa",
        title="Demo shaft",
        material="C45",
        segments=[
            Segment(diameter=30, length=40),
            Segment(diameter=25, length=60),
            Segment(diameter=20, length=30, chamfer_right=Chamfer(size=1)),
        ],
        **extra,
    )


@pytest.fixture(scope="module")
def files(tmp_path_factory):
    return export_all(demo(), tmp_path_factory.mktemp("out"))


def test_all_three_files_exist(files):
    assert set(files) == {"step", "dxf", "pdf"}
    for path in files.values():
        assert path.exists() and path.stat().st_size > 500


def test_step_loads_again_with_the_right_size_and_volume(files):
    import cadquery as cq

    solid = cq.importers.importStep(str(files["step"])).val()
    box = solid.BoundingBox()
    assert box.xlen == pytest.approx(130, abs=1e-3)
    assert box.ylen == pytest.approx(30, abs=1e-2)
    cylinders = math.pi * (15**2 * 40 + 12.5**2 * 60 + 10**2 * 30)
    # A 1 x 45 degree chamfer on radius 10 removes a ring: pi * (R^2 * c - cone frustum).
    frustum = math.pi / 3 * 1 * (10**2 + 10 * 9 + 9**2)
    chamfer = math.pi * 10**2 * 1 - frustum
    assert solid.Volume() == pytest.approx(cylinders - chamfer, rel=1e-4)


def test_dxf_has_layers_and_real_dimensions(files):
    doc = ezdxf.readfile(files["dxf"])
    for layer in ("OUTLINE", "CENTER", "DIM", "TEXT"):
        assert layer in doc.layers
    msp = doc.modelspace()
    dims = msp.query("DIMENSION")
    assert len(dims) == 7  # 3 lengths, 3 diameters, 1 overall
    assert all(d.dxf.layer == "DIM" for d in dims)
    measured = sorted(round(d.get_measurement(), 3) for d in dims)
    scale, _ = pick_scale(130, 30)
    assert [round(m / scale, 3) for m in measured] == [20, 25, 30, 30, 40, 60, 130]
    assert len(msp.query('LINE[layer=="CENTER"]')) == 1
    assert len(msp.query('LINE[layer=="OUTLINE"]')) >= 12


def test_dxf_carries_the_draft_mark_and_the_title_block(files):
    texts = [t.dxf.text for t in ezdxf.readfile(files["dxf"]).modelspace().query("TEXT")]
    assert DRAFT_MARK in texts
    joined = "\n".join(texts)
    for needle in ("Demo shaft", "Material: C45", "Units: mm", "Scale: 1:1", "Session: s_20261123_aaaaaa", "Approved by: "):
        assert needle in joined


def test_pdf_has_one_a4_landscape_page(files):
    reader = PdfReader(str(files["pdf"]))
    assert len(reader.pages) == 1
    box = reader.pages[0].mediabox
    assert float(box.width) == pytest.approx(297 / 25.4 * 72, abs=1)
    assert float(box.height) == pytest.approx(210 / 25.4 * 72, abs=1)


def test_export_is_blocked_by_validation_errors(tmp_path):
    bad = ShaftSpec(id="s_20261123_aaaaaa", segments=[Segment(diameter=0, length=10)])
    with pytest.raises(ExportBlocked):
        export_all(bad, tmp_path / "bad")
    assert not (tmp_path / "bad").exists()


def test_mark_changes_only_after_human_approval(tmp_path):
    assert status_mark(demo()) == DRAFT_MARK
    assert status_mark(demo(status="approved")) == DRAFT_MARK  # no name, still a draft
    approved = demo(status="approved", approved_by="Kis Anna", approved_at=datetime(2026, 11, 27, tzinfo=timezone.utc))
    assert status_mark(approved) == "Approved for review by: Kis Anna – not a manufacturing release"
    rebuild_sheets(approved, tmp_path)
    texts = "\n".join(t.dxf.text for t in ezdxf.readfile(tmp_path / "shaft.dxf").modelspace().query("TEXT"))
    assert DRAFT_MARK not in texts
    assert "Approved by: Kis Anna" in texts and "Approval date: 2026-11-27" in texts
    assert len(PdfReader(str(tmp_path / "shaft.pdf")).pages) == 1


def test_scale_is_chosen_from_standard_scales():
    assert pick_scale(130, 30)[1] == "1:1"
    assert pick_scale(1200, 80)[1] == "1:10"
    assert pick_scale(20, 6)[1] == "5:1"


def test_dxf_writer_alone(tmp_path):
    assert write_dxf(demo(), tmp_path / "a.dxf").exists()
