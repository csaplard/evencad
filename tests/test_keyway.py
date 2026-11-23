"""Keyway: the speaker gives the segment and the length. Width and depth come from a table."""

import ezdxf
import pytest

from server.ai.prompt import SYSTEM_PROMPT, describe_spec
from server.core.keyway import keyway_size
from server.core.ops import OpError, active_after, apply_ops, parse_op
from server.core.readback import readback
from server.core.spec import Chamfer, Keyway, Segment, ShaftSpec
from server.core.validation import validate
from server.draw.dxf import build_dxf
from server.draw.glasses import render_glasses
from server.draw.glasses3d import render_glasses_3d
from server.draw.model import draw_shaft


def shaft(*dims, keyway_on=None, keyway_length=20.0):
    segs = [Segment(diameter=d, length=l) for d, l in dims]
    if keyway_on:
        segs[keyway_on - 1].keyway = Keyway(length=keyway_length)
    return ShaftSpec(id="s_20261123_aaaaaa", segments=segs)


def lit(img):
    return sum(1 for b in img.tobytes() if b)


@pytest.mark.parametrize("d, b, t1", [
    (7, 2, 1.2), (8, 2, 1.2), (8.5, 3, 1.8), (12, 4, 2.5), (17, 5, 3), (20, 6, 3.5), (22, 6, 3.5),
    (25, 8, 4), (30, 8, 4), (30.1, 10, 5), (38, 10, 5), (40, 12, 5), (50, 14, 5.5), (58, 16, 6),
    (65, 18, 7), (75, 20, 7.5), (85, 22, 9), (95, 25, 9), (110, 28, 10), (230, 50, 17),
])
def test_table(d, b, t1):
    size = keyway_size(d)
    assert (size.width, size.depth) == (b, t1)


@pytest.mark.parametrize("d", [0, 5, 6, 230.5, 500])
def test_no_size_outside_the_table(d):
    assert keyway_size(d) is None


def test_the_operation_sets_and_removes_a_keyway():
    part = shaft((30, 40), (25, 60))
    op = parse_op({"op": "set_keyway", "index": 2, "length": 20})
    new = apply_ops(part, [op])
    assert new.segments[1].keyway == Keyway(length=20) and part.segments[1].keyway is None
    assert active_after(part, [op], None) == 2
    assert apply_ops(new, [parse_op({"op": "set_keyway", "index": "last", "length": 0})]).segments[1].keyway is None
    with pytest.raises(OpError):
        apply_ops(part, [parse_op({"op": "set_keyway", "index": 5, "length": 20})])
    with pytest.raises(Exception):  # the model cannot send a width or a depth
        parse_op({"op": "set_keyway", "index": 2, "length": 20, "width": 9})


def test_the_keyway_follows_a_new_diameter():
    part = shaft((30, 40), (25, 60), keyway_on=2)
    assert "KW2 8×20" in readback(part)
    bigger = apply_ops(part, [parse_op({"op": "edit_segment", "index": 2, "diameter": 40})])
    assert "KW2 12×20" in readback(bigger)


def test_validation():
    def codes(spec):
        return [m.code for m in validate(spec).errors]

    assert codes(shaft((30, 40), (25, 60), keyway_on=2)) == []
    assert codes(shaft((30, 40), (5, 60), keyway_on=2)) == ["KEYWAY_NO_SIZE"]
    assert codes(shaft((30, 40), (25, 60), keyway_on=2, keyway_length=8)) == ["KEYWAY_TOO_SHORT"]
    assert codes(shaft((30, 40), (25, 60), keyway_on=2, keyway_length=61)) == ["KEYWAY_TOO_LONG"]
    # Chamfers take room from the keyway.
    tight = shaft((30, 40), (25, 60), keyway_on=2, keyway_length=59)
    assert codes(tight) == []
    tight.segments[1].chamfer_right = Chamfer(size=2)
    assert codes(tight) == ["KEYWAY_TOO_LONG"]
    for m in validate(shaft((30, 40), (5, 60), keyway_on=2)).errors:
        assert len(m.text) <= 40


def test_the_model_sees_the_keyway_and_the_rule():
    assert "keyway 8 wide, 20 long" in describe_spec(shaft((30, 40), (25, 60), keyway_on=2))
    assert "set_keyway" in SYSTEM_PROMPT


def test_drawing_model_has_a_centred_slot():
    d = draw_shaft(shaft((30, 40), (25, 60), keyway_on=2))
    (slot,) = d.slots
    assert (slot.x1, slot.x2, slot.width, slot.depth, slot.segment) == (60, 80, 8, 4, 2)
    assert draw_shaft(shaft((30, 40), (5, 60), keyway_on=2)).slots == []  # no size, nothing to draw


def test_glasses_views_show_the_keyway():
    plain, keyed = shaft((30, 40), (25, 60)), shaft((30, 40), (25, 60), keyway_on=2)
    assert lit(render_glasses(keyed)) > lit(render_glasses(plain))
    for yaw in (30, 150):
        img = render_glasses_3d(keyed, yaw)
        assert set(img.tobytes()) <= {0, 255}
        assert lit(img) > lit(render_glasses_3d(plain, yaw)), yaw


def test_dxf_has_the_slot_and_a_note():
    msp = build_dxf(shaft((30, 40), (25, 60), keyway_on=2)).modelspace()
    arcs = msp.query("ARC")
    assert len(arcs) == 2 and all(a.dxf.layer == "OUTLINE" for a in arcs)
    texts = [t.dxf.text for t in msp.query("TEXT")]
    assert any("Keyway" in t and "8 × 20" in t and "depth 4" in t and "DIN 6885-1" in t for t in texts)
    assert len(build_dxf(shaft((30, 40), (25, 60))).modelspace().query("ARC")) == 0


def test_step_has_less_material_with_a_keyway():
    from server.cad.step import build_solid

    plain = build_solid(shaft((30, 40), (25, 60))).val().Volume()
    keyed = build_solid(shaft((30, 40), (25, 60), keyway_on=2)).val().Volume()
    # 8 wide, 20 long, 4 deep. Round ends and the curved top make it a bit less than the box.
    assert 0.75 * 8 * 20 * 4 < plain - keyed < 8 * 20 * 4
