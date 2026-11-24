"""Read-back text (SAYCAD_SPEC.md, section 6.2). Made by a template, never by the AI."""

from server.core.readback import MAX_CHARS, readback
from server.core.spec import Chamfer, Segment, ShaftSpec


def spec(*segments):
    return ShaftSpec(id="s_20261123_aaaaaa", segments=list(segments))


def test_the_example_from_the_spec():
    s = spec(
        Segment(diameter=30, length=40),
        Segment(diameter=25, length=60),
        Segment(diameter=20, length=30, chamfer_right=Chamfer(size=1)),
    )
    assert readback(s) == "3 steps  Ø30×40  Ø25×60  Ø20×30  C1 right  L130"


def test_empty_spec():
    assert readback(spec()) == "No segments yet"


def test_one_segment_and_decimals():
    assert readback(spec(Segment(diameter=35.5, length=12.25))) == "1 step  Ø35.5×12.25  L12.25"


def test_chamfers_left_end_step_and_angle():
    s = spec(
        Segment(diameter=30, length=40, chamfer_left=Chamfer(size=2), chamfer_right=Chamfer(size=1, angle=30)),
        Segment(diameter=20, length=30),
    )
    assert readback(s) == "2 steps  Ø30×40  Ø20×30  C2 left  C1×30° step 1  L70"


def test_long_parts_stay_short():
    s = spec(*[Segment(diameter=20 + i, length=10.5) for i in range(12)])
    text = readback(s)
    assert len(text) <= MAX_CHARS
    assert text.startswith("12 steps")
    assert text.endswith("L126")
    assert "Ø31×10.5" in text  # the last segment is always shown
