"""Fit and surface roughness: text notes on a segment. They do not change the geometry."""

import pytest

from server.ai.prompt import SYSTEM_PROMPT, describe_spec
from server.core.ops import OpError, active_after, apply_ops, parse_op
from server.core.readback import readback
from server.core.spec import Segment, ShaftSpec
from server.core.validation import validate
from server.draw.dxf import build_dxf
from server.draw.model import draw_shaft
from server.draw.glasses import render_glasses


def shaft():
    return ShaftSpec(id="s_20261123_aaaaaa", segments=[Segment(diameter=30, length=40), Segment(diameter=25, length=60)])


def do(spec, *ops):
    return apply_ops(spec, [parse_op(o) for o in ops])


def test_set_and_remove():
    new = do(shaft(), {"op": "set_fit", "index": 2, "fit": "H6"}, {"op": "set_roughness", "index": "last", "ra": 1.6})
    assert new.segments[1].fit == "h6"  # a shaft fit is written in lower case
    assert new.segments[1].roughness == 1.6 and new.segments[0].fit is None
    cleared = do(new, {"op": "set_fit", "index": 2, "fit": ""}, {"op": "set_roughness", "index": 2, "ra": 0})
    assert cleared.segments[1].fit is None and cleared.segments[1].roughness is None
    assert active_after(shaft(), [parse_op({"op": "set_fit", "index": 1, "fit": "k6"})], None) == 1
    assert active_after(shaft(), [parse_op({"op": "set_roughness", "index": 2, "ra": 0.8})], None) == 2
    with pytest.raises(OpError):
        do(shaft(), {"op": "set_roughness", "index": 1, "ra": -1})
    with pytest.raises(OpError):
        do(shaft(), {"op": "set_fit", "index": 7, "fit": "h6"})


@pytest.mark.parametrize("fit", ["h6", "k6", "js5", "f7", "g6", "m6", "p6", "h11", "za8"])
def test_good_fits(fit):
    assert validate(do(shaft(), {"op": "set_fit", "index": 1, "fit": fit})).errors == []


@pytest.mark.parametrize("fit", ["h", "6", "h66", "i6", "h0", "h19", "tight", "h6/H7", "o7"])
def test_bad_fits_are_errors(fit):
    errors = validate(do(shaft(), {"op": "set_fit", "index": 1, "fit": fit})).errors
    assert [e.code for e in errors] == ["BAD_FIT"] and len(errors[0].text) <= 40


def test_roughness_outside_the_series_is_a_warning():
    assert validate(do(shaft(), {"op": "set_roughness", "index": 1, "ra": 1.6})).warnings == []
    report = validate(do(shaft(), {"op": "set_roughness", "index": 1, "ra": 1.5}))
    assert report.errors == [] and [w.code for w in report.warnings] == ["RA_NOT_STANDARD"]


def test_texts():
    spec = do(shaft(), {"op": "set_fit", "index": 2, "fit": "h6"}, {"op": "set_roughness", "index": 2, "ra": 1.6})
    assert readback(spec) == "2 steps  Ø30×40  Ø25h6×60  Ra1.6 #2  L100"
    assert "fit h6" in describe_spec(spec) and "Ra 1.6" in describe_spec(spec)
    assert "set_fit" in SYSTEM_PROMPT and "set_roughness" in SYSTEM_PROMPT


def test_drawing():
    spec = do(shaft(), {"op": "set_fit", "index": 2, "fit": "h6"}, {"op": "set_roughness", "index": 2, "ra": 1.6})
    d = draw_shaft(spec)
    assert [x.text for x in d.dims if x.kind == "diameter"] == ["Ø30", "Ø25 h6 (0/-0.013)"]
    (mark,) = d.marks
    assert mark.text == "Ra 1.6" and mark.segment == 2 and mark.y == 12.5 and 40 < mark.x < 100
    assert render_glasses(spec).tobytes() != render_glasses(shaft()).tobytes()

    msp = build_dxf(spec).modelspace()
    assert any(t.dxf.text == "Ra 1.6" for t in msp.query("TEXT"))
    dim_texts = [dim.dxf.text for dim in msp.query("DIMENSION")]
    assert "Ø<> h6 (0/-0.013)" in dim_texts and "Ø<>" in dim_texts
