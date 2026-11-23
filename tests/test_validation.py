"""Every validation rule from EVENCAD_SPEC.md section 6.1."""

from server.core.spec import Chamfer, Segment, ShaftSpec
from server.core.validation import validate


def spec(*segments):
    return ShaftSpec(id="s_20261123_aaaaaa", segments=list(segments))


def seg(d, length, left=None, right=None):
    return Segment(
        diameter=d,
        length=length,
        chamfer_left=Chamfer(size=left) if left else None,
        chamfer_right=Chamfer(size=right) if right else None,
    )


def codes(messages):
    return [m.code for m in messages]


def test_good_shaft_has_no_messages():
    r = validate(spec(seg(30, 40), seg(25, 60), seg(20, 30, right=1)))
    assert r.errors == [] and r.warnings == []
    assert r.ok


def test_no_segments_is_an_error():
    r = validate(spec())
    assert codes(r.errors) == ["NO_SEGMENTS"]
    assert not r.ok


def test_zero_or_negative_values_are_errors():
    r = validate(spec(seg(0, 40), seg(25, -1)))
    assert codes(r.errors) == ["BAD_DIAMETER", "BAD_LENGTH"]
    assert [m.segment for m in r.errors] == [1, 2]


def test_limits():
    r = validate(spec(seg(501, 40), seg(400, 2001)))
    assert codes(r.errors) == ["DIAMETER_TOO_BIG", "LENGTH_TOO_BIG"]
    assert validate(spec(seg(500, 2000))).errors == []


def test_total_length_limit():
    r = validate(spec(seg(300, 1500), seg(300, 1500)))
    assert "TOTAL_TOO_LONG" in codes(r.errors)


def test_chamfer_longer_than_the_segment():
    r = validate(spec(seg(30, 2, left=1.5, right=1)))
    assert codes(r.errors) == ["CHAMFER_TOO_LONG"]
    assert r.errors[0].segment == 1


def test_chamfer_deeper_than_the_radius_at_an_end():
    r = validate(spec(seg(10, 40, left=6)))
    assert codes(r.errors) == ["CHAMFER_TOO_DEEP"]


def test_chamfer_deeper_than_the_shoulder():
    # The shoulder between 30 and 28 is 1 mm high. A 2 mm chamfer does not fit.
    r = validate(spec(seg(30, 40, right=2), seg(28, 30)))
    assert codes(r.errors) == ["CHAMFER_TOO_DEEP"]
    assert validate(spec(seg(30, 40, right=1), seg(28, 30))).errors == []


def test_chamfer_on_an_edge_that_is_not_free():
    # Segment 1 is smaller than segment 2, so its right edge is inside the part.
    r = validate(spec(seg(20, 40, right=1), seg(30, 30)))
    assert codes(r.errors) == ["CHAMFER_NO_EDGE"]


def test_bad_chamfer_angle():
    s = spec(Segment(diameter=30, length=40, chamfer_right=Chamfer(size=1, angle=90)))
    assert codes(validate(s).errors) == ["BAD_CHAMFER_ANGLE"]


def test_warning_large_step():
    r = validate(spec(seg(50, 40), seg(20, 30)))
    assert codes(r.warnings) == ["BIG_STEP"]
    assert r.warnings[0].segment == 2
    assert r.ok


def test_warning_slender_part():
    r = validate(spec(seg(10, 150), seg(8, 80)))
    assert codes(r.warnings) == ["SLENDER"]
    assert r.warnings[0].segment is None


def test_warning_equal_neighbours():
    r = validate(spec(seg(30, 40), seg(30, 20)))
    assert codes(r.warnings) == ["EQUAL_NEIGHBOURS"]


def test_warning_short_segment():
    r = validate(spec(seg(30, 40), seg(25, 1.5)))
    assert codes(r.warnings) == ["SHORT_SEGMENT"]


def test_every_text_fits_the_display():
    bad = validate(spec(seg(0, -1), seg(600, 3000, left=5000), seg(1, 1, right=9), seg(1, 1)))
    odd = validate(spec(seg(499.5, 1.25), seg(499.5, 1.5), seg(123.25, 1999.5), seg(1.125, 1)))
    assert len(bad.errors) >= 4 and len(odd.warnings) >= 4
    for m in bad.errors + odd.errors + odd.warnings:
        assert 0 < len(m.text) <= 40, m.text
