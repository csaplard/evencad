"""Vector model and glasses image (EVENCAD_SPEC.md, section 6.3)."""

import io

from PIL import Image

from server.core.spec import Chamfer, Segment, ShaftSpec
from server.draw.glasses import glasses_png, glasses_tiles, render_glasses
from server.draw.model import Style, draw_shaft, profile


def spec(*segments):
    return ShaftSpec(id="s_20261123_aaaaaa", segments=list(segments))


def demo():
    return spec(
        Segment(diameter=30, length=40),
        Segment(diameter=25, length=60),
        Segment(diameter=20, length=30, chamfer_right=Chamfer(size=1)),
    )


def test_profile_of_a_plain_stepped_shaft():
    s = spec(Segment(diameter=30, length=40), Segment(diameter=20, length=30))
    assert profile(s) == [(0, 0), (0, 15), (40, 15), (40, 10), (70, 10), (70, 0)]


def test_profile_with_chamfers():
    s = spec(Segment(diameter=30, length=40, chamfer_left=Chamfer(size=2), chamfer_right=Chamfer(size=1)), Segment(diameter=20, length=30))
    pts = [(round(x, 6), round(r, 6)) for x, r in profile(s)]
    assert pts == [(0, 0), (0, 13), (2, 15), (39, 15), (40, 14), (40, 10), (70, 10), (70, 0)]


def test_model_has_outline_centre_line_and_dimensions():
    d = draw_shaft(demo())
    assert d.length == 130 and d.max_diameter == 30
    assert sum(1 for ln in d.lines if ln.layer == "CENTER") == 1
    assert len([ln for ln in d.lines if ln.layer == "OUTLINE"]) >= 12
    kinds = [(m.kind, m.text) for m in d.dims]
    assert ("length", "40") in kinds and ("length", "60") in kinds and ("length", "30") in kinds
    assert ("diameter", "Ø30") in kinds and ("diameter", "Ø20") in kinds
    assert kinds[-1] == ("overall", "130")


def test_outline_is_symmetric_about_the_axis():
    d = draw_shaft(demo())
    ys = [y for ln in d.lines if ln.layer == "OUTLINE" for y in (ln.p1[1], ln.p2[1])]
    assert max(ys) == 15 and min(ys) == -15


def test_empty_spec_gives_an_empty_model():
    d = draw_shaft(spec())
    assert d.lines == [] and d.dims == []


def test_one_segment_has_no_separate_length_dimension():
    d = draw_shaft(spec(Segment(diameter=30, length=40)))
    assert [m.kind for m in d.dims] == ["diameter", "overall"]


def test_glasses_style_reduces_dimensions_on_long_parts():
    long = spec(*[Segment(diameter=20 + i, length=10) for i in range(7)])
    full = draw_shaft(long, Style(name="sheet"))
    small = draw_shaft(long, Style(name="glasses"))
    assert len(full.dims) == 15
    assert [(m.kind, m.segment) for m in small.dims] == [("length", 7), ("diameter", 7), ("overall", None)]
    picked = draw_shaft(long, Style(name="glasses", active_segment=2))
    assert picked.dims[0].segment == 2


def test_glasses_image_is_576_by_144_and_pure_black_and_white():
    img = render_glasses(demo())
    assert img.size == (576, 144)
    assert set(img.getdata()) == {0, 255}
    lit = sum(1 for p in img.getdata() if p)
    assert 0.01 < lit / (576 * 144) < 0.35  # line drawing, not a filled shape


def test_glasses_image_for_an_empty_spec_shows_a_hint():
    img = render_glasses(spec())
    assert any(img.getdata())


def test_glasses_png_and_tiles():
    assert Image.open(io.BytesIO(glasses_png(demo()))).size == (576, 144)
    tiles = glasses_tiles(demo())
    assert len(tiles) == 2
    for t in tiles:
        im = Image.open(io.BytesIO(t))
        assert im.format == "PNG" and im.size == (288, 144)
