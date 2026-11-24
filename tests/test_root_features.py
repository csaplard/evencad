"""Fillet and undercut at a shoulder. Both sit at the root, on the smaller segment."""

import math

import ezdxf
import pytest

from server.ai.prompt import SYSTEM_PROMPT, describe_spec
from server.core.mass import volume_mm3
from server.core.ops import OpError, active_after, apply_ops, parse_op
from server.core.readback import readback
from server.core.spec import Chamfer, Keyway, Segment, ShaftSpec, Undercut
from server.core.validation import validate
from server.draw.dxf import build_dxf
from server.draw.glasses import render_glasses
from server.draw.glasses3d import render_glasses_3d
from server.draw.model import draw_shaft, profile, slots


def shaft(*dims):
    return ShaftSpec(id="s_20261124_aaaaaa", segments=[Segment(diameter=d, length=l) for d, l in dims])


def do(spec, *ops):
    return apply_ops(spec, [parse_op(o) for o in ops])


def codes(spec):
    return [m.code for m in validate(spec).errors]


BASE = ((30, 40), (20, 30), (40, 20))  # step 1 goes down, step 2 goes up


# ── operations ───────────────────────────────────────────────────────────────
def test_a_fillet_goes_to_the_smaller_segment():
    spec = do(shaft(*BASE), {"op": "set_fillet", "step": 1, "radius": 2}, {"op": "set_fillet", "step": 2, "radius": 3})
    assert (spec.segments[1].fillet_left, spec.segments[1].fillet_right) == (2, 3)
    assert spec.segments[0].fillet_right is None and spec.segments[2].fillet_left is None
    assert codes(spec) == []


def test_an_undercut_goes_to_the_smaller_segment_and_replaces_a_fillet():
    spec = do(shaft(*BASE), {"op": "set_fillet", "step": 1, "radius": 2}, {"op": "set_undercut", "step": 1, "width": 3, "depth": 0.5})
    seg = spec.segments[1]
    assert seg.fillet_left is None and seg.undercut_left == Undercut(width=3, depth=0.5)
    spec = do(spec, {"op": "set_fillet", "step": 1, "radius": 1})
    assert spec.segments[1].undercut_left is None and spec.segments[1].fillet_left == 1


def test_zero_removes():
    spec = do(shaft(*BASE), {"op": "set_fillet", "step": 1, "radius": 2}, {"op": "set_fillet", "step": 1, "radius": 0})
    assert spec == shaft(*BASE)
    spec = do(shaft(*BASE), {"op": "set_undercut", "step": 2, "width": 2, "depth": 1}, {"op": "set_undercut", "step": 2, "width": 0, "depth": 0})
    assert spec == shaft(*BASE)


def test_bad_steps():
    with pytest.raises(OpError):
        do(shaft(*BASE), {"op": "set_fillet", "step": 3, "radius": 1})
    with pytest.raises(OpError):
        do(shaft((30, 40), (30, 30)), {"op": "set_undercut", "step": 1, "width": 2, "depth": 1})
    with pytest.raises(OpError):
        do(shaft(*BASE), {"op": "set_fillet", "step": 1, "radius": -1})


def test_deleting_a_segment_drops_the_features_that_faced_it():
    spec = do(shaft(*BASE), {"op": "set_fillet", "step": 1, "radius": 2}, {"op": "delete_segment", "index": 1})
    assert spec.segments[0].fillet_left is None
    spec = do(shaft(*BASE), {"op": "set_fillet", "step": 2, "radius": 2}, {"op": "add_segment", "diameter": 25, "length": 5, "at": 3})
    assert spec.segments[1].fillet_right is None


def test_the_display_marks_the_smaller_segment():
    assert active_after(shaft(*BASE), [parse_op({"op": "set_fillet", "step": 2, "radius": 2})], 1) == 2
    assert active_after(shaft(*BASE), [parse_op({"op": "set_undercut", "step": 1, "width": 2, "depth": 1})], 3) == 2


# ── validation ───────────────────────────────────────────────────────────────
def test_a_fillet_cannot_be_higher_than_the_shoulder():
    assert codes(do(shaft(*BASE), {"op": "set_fillet", "step": 1, "radius": 5})) == []
    assert codes(do(shaft(*BASE), {"op": "set_fillet", "step": 1, "radius": 5.1})) == ["FILLET_TOO_BIG"]
    spec = do(shaft(*BASE), {"op": "set_chamfer", "where": 1, "size": 2}, {"op": "set_fillet", "step": 1, "radius": 3.5})
    assert codes(spec) == ["FILLET_TOO_BIG"]  # the chamfer of the larger segment takes 2 of the 5


def test_end_features_must_fit_into_the_length():
    spec = do(shaft((30, 40), (20, 6), (40, 20)), {"op": "set_fillet", "step": 1, "radius": 3}, {"op": "set_undercut", "step": 2, "width": 3.5, "depth": 1})
    assert codes(spec) == ["ENDS_TOO_LONG"]


def test_undercut_limits():
    assert codes(do(shaft(*BASE), {"op": "set_undercut", "step": 1, "width": 2, "depth": 10})) == ["UNDERCUT_TOO_DEEP"]
    spec = shaft(*BASE)
    spec.segments[1].undercut_left = Undercut(width=2, depth=0)
    assert codes(spec) == ["BAD_UNDERCUT"]


def test_a_feature_with_no_shoulder_is_an_error():
    spec = do(shaft(*BASE), {"op": "set_fillet", "step": 1, "radius": 2}, {"op": "edit_segment", "index": 1, "diameter": 20})
    assert "ROOT_NO_SHOULDER" in codes(spec)
    assert codes(do(spec, {"op": "set_fillet", "step": 1, "radius": 0})) == []  # it can still be removed


def test_a_keyway_stays_clear_of_the_fillet_and_the_undercut():
    spec = do(shaft((40, 20), (30, 40), (40, 20)), {"op": "set_fillet", "step": 1, "radius": 4}, {"op": "set_undercut", "step": 2, "width": 6, "depth": 1},
              {"op": "set_keyway", "index": 2, "length": 30})
    assert codes(spec) == []
    (slot,) = slots(spec)
    assert (slot.x1, slot.x2) == (24, 54)
    assert codes(do(spec, {"op": "set_keyway", "index": 2, "length": 31})) == ["KEYWAY_TOO_LONG"]


# ── geometry ─────────────────────────────────────────────────────────────────
def test_fillet_profile_points_lie_on_the_arc():
    spec = do(shaft(*BASE), {"op": "set_fillet", "step": 1, "radius": 2}, {"op": "set_fillet", "step": 2, "radius": 3})
    pts = profile(spec)
    assert (40, 12) in pts and (42, 10) in pts and (67, 10) in pts and (70, 13) in pts
    left = [p for p in pts if 40 < p[0] < 42]
    right = [p for p in pts if 67 < p[0] < 70]
    assert len(left) >= 4 and len(right) >= 4
    assert all(math.hypot(x - 42, r - 12) == pytest.approx(2) for x, r in left)
    assert all(math.hypot(x - 67, r - 13) == pytest.approx(3) for x, r in right)
    assert [p[0] for p in pts] == sorted(p[0] for p in pts)


def test_undercut_profile():
    spec = do(shaft(*BASE), {"op": "set_undercut", "step": 1, "width": 3, "depth": 0.5})
    pts = profile(spec)
    at = pts.index((40, 15))
    assert pts[at:at + 5] == [(40, 15), (40, 9.5), (43, 9.5), (43, 10), (70, 10)]


def test_the_fillet_adds_no_edge_line_at_its_tangent_point():
    spec = do(shaft(*BASE), {"op": "set_fillet", "step": 1, "radius": 2})
    d = draw_shaft(spec)
    verticals = sorted({ln.p1[0] for ln in d.lines if ln.layer == "OUTLINE" and ln.p1[0] == ln.p2[0]})
    assert verticals == [0, 40, 70, 90]
    (arc,) = d.arcs
    assert (arc.cx, arc.cy, arc.radius, arc.start, arc.end) == (42, 12, 2, 180, 270)
    assert sum(1 for ln in d.lines if ln.curve) >= 8  # both halves


def test_the_undercut_shows_its_edges():
    d = draw_shaft(do(shaft(*BASE), {"op": "set_undercut", "step": 1, "width": 3, "depth": 0.5}))
    verticals = sorted({ln.p1[0] for ln in d.lines if ln.layer == "OUTLINE" and ln.p1[0] == ln.p2[0]})
    assert verticals == [0, 40, 43, 70, 90]


@pytest.mark.parametrize("ops", [
    [{"op": "set_fillet", "step": 1, "radius": 2}],
    [{"op": "set_fillet", "step": 1, "radius": 5}, {"op": "set_fillet", "step": 2, "radius": 4}],
    [{"op": "set_undercut", "step": 1, "width": 3, "depth": 0.5}, {"op": "set_undercut", "step": 2, "width": 2, "depth": 1}],
    [{"op": "set_chamfer", "where": 1, "size": 1, "angle": 45}, {"op": "set_fillet", "step": 1, "radius": 3},
     {"op": "set_undercut", "step": 2, "width": 2, "depth": 1}, {"op": "set_keyway", "index": 2, "length": 15}],
])
def test_volume_matches_the_solid(ops):
    from server.cad.step import build_solid

    spec = do(shaft(*BASE), *ops)
    assert codes(spec) == []
    assert volume_mm3(spec) == pytest.approx(build_solid(spec).val().Volume(), rel=0.002)
    assert volume_mm3(spec) != pytest.approx(volume_mm3(shaft(*BASE)), rel=1e-6)


def test_the_step_solid_has_a_real_round_face():
    from server.cad.step import build_solid

    spec = do(shaft(*BASE), {"op": "set_fillet", "step": 1, "radius": 2})
    kinds = {f.geomType() for f in build_solid(spec).faces().vals()}
    assert "TORUS" in kinds


# ── outputs ──────────────────────────────────────────────────────────────────
def test_readback_and_prompt():
    spec = do(shaft(*BASE), {"op": "set_fillet", "step": 1, "radius": 2}, {"op": "set_undercut", "step": 2, "width": 3, "depth": 0.5})
    assert readback(spec) == "3 steps  Ø30×40  Ø20×30  Ø40×20  R2 step 1  U3×0.5 step 2  L90"
    text = describe_spec(spec)
    assert "fillet left R2" in text and "undercut right 3 wide, 0.5 deep" in text
    assert "set_fillet" in SYSTEM_PROMPT and "set_undercut" in SYSTEM_PROMPT


def test_pictures_change():
    plain = shaft(*BASE)
    for op in ({"op": "set_fillet", "step": 1, "radius": 4}, {"op": "set_undercut", "step": 1, "width": 4, "depth": 2}):
        spec = do(plain, op)
        assert render_glasses(spec).tobytes() != render_glasses(plain).tobytes()
        assert render_glasses_3d(spec, 30).tobytes() != render_glasses_3d(plain, 30).tobytes()


def test_dxf_has_arcs_and_notes():
    spec = do(shaft(*BASE), {"op": "set_fillet", "step": 1, "radius": 2}, {"op": "set_undercut", "step": 2, "width": 3, "depth": 0.5})
    msp = build_dxf(spec).modelspace()
    arcs = msp.query("ARC")
    assert len(arcs) == 2 and all(a.dxf.radius == pytest.approx(2) for a in arcs)  # scale 1:1
    texts = [t.dxf.text for t in msp.query("TEXT")]
    assert "Fillet R2 at step 1" in texts
    assert "Undercut at step 2: 3 wide, 0.5 deep (plain groove)" in texts


def test_notes_do_not_overlap_the_keyway_note():
    spec = do(shaft(*BASE), {"op": "set_fillet", "step": 1, "radius": 2}, {"op": "set_keyway", "index": 1, "length": 20})
    notes = [t for t in build_dxf(spec).modelspace().query("TEXT") if t.dxf.text.startswith(("Fillet", "Keyway"))]
    assert len({round(t.dxf.insert.y, 1) for t in notes}) == 2


def test_old_sessions_still_load():
    old = {"id": "s_20261123_aaaaaa", "segments": [{"diameter": 30, "length": 40, "chamfer_left": None, "keyway": None}]}
    assert ShaftSpec.model_validate(old).segments[0].fillet_left is None
    assert Chamfer and Keyway  # imported for the other tests' helpers
