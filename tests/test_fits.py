"""Tolerance limits of ISO 286 shaft fits. The values come from a table in the code."""

import ezdxf
import pytest

from server.core.fits import limits, limits_text
from server.core.spec import Segment, ShaftSpec
from server.draw.dxf import build_dxf
from server.draw.model import Style, draw_shaft


# Well known handbook values: (diameter, fit, upper µm, lower µm).
@pytest.mark.parametrize("d, fit, upper, lower", [
    (25, "h6", 0, -13), (25, "k6", 15, 2), (25, "m6", 21, 8), (25, "n6", 28, 15), (25, "p6", 35, 22),
    (25, "g6", -7, -20), (25, "f7", -20, -41), (25, "e8", -40, -73), (25, "d9", -65, -117),
    (25, "r6", 41, 28), (25, "s6", 48, 35), (25, "js6", 6.5, -6.5), (25, "h7", 0, -21), (25, "h11", 0, -130),
    (50, "h6", 0, -16), (50, "k6", 18, 2), (50, "f7", -25, -50), (50, "g6", -9, -25),
    (60, "r6", 60, 41), (70, "r6", 62, 43), (60, "s6", 72, 53), (100, "h6", 0, -22), (100, "m6", 35, 13),
    (10, "h6", 0, -9), (10, "k6", 10, 1), (3, "h6", 0, -6), (6, "h7", 0, -12), (18, "h6", 0, -11),
    (30, "h6", 0, -13), (30.5, "h6", 0, -16), (400, "h7", 0, -57), (500, "h6", 0, -40),
    (25, "k8", 33, 0),  # k has a lower deviation of 0 outside grades 4 to 7
])
def test_limits(d, fit, upper, lower):
    assert limits(d, fit) == pytest.approx((upper / 1000, lower / 1000))


@pytest.mark.parametrize("d, fit", [(25, "j6"), (25, "za6"), (25, "h3"), (25, "h14"), (600, "h6"), (0, "h6"), (25, ""), (25, None), (25, "H7")])
def test_no_values_outside_the_table(d, fit):
    assert limits(d, fit) is None
    assert limits_text(d, fit) == ""


@pytest.mark.parametrize("d, fit, text", [
    (25, "h6", "0/-0.013"), (25, "k6", "+0.015/+0.002"), (25, "js6", "±0.0065"), (25, "f7", "-0.02/-0.041"),
])
def test_limits_text(d, fit, text):
    assert limits_text(d, fit) == text


def spec():
    return ShaftSpec(id="s_20261124_aaaaaa", segments=[
        Segment(diameter=30, length=40), Segment(diameter=25, length=60, fit="k6"), Segment(diameter=20, length=30, fit="j6"),
    ])


def test_the_limits_are_a_note_and_the_dimension_stays_short():
    d = draw_shaft(spec(), Style(name="sheet"))
    assert {x.segment: x.text for x in d.dims if x.kind == "diameter"} == {1: "Ø30", 2: "Ø25 k6", 3: "Ø20 j6"}
    assert [(n.text, n.segment) for n in d.notes] == [("Ø25 k6: +0.015/+0.002 (ISO 286)", 2)]  # j6 is not in the table


def test_the_dxf_has_the_note():
    msp = build_dxf(spec()).modelspace()
    assert "Ø25 k6: +0.015/+0.002 (ISO 286)" in [t.dxf.text for t in msp.query("TEXT")]
    dims = {round(d.get_measurement()): d.dxf.text for d in msp.query("DIMENSION")}
    assert dims[25] == "Ø<> k6"
