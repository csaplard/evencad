"""Mass: volume from the spec by formula, density from a small table by the material name."""

import math

import pytest

from server.core.mass import density, mass, mass_text, volume_mm3
from server.core.readback import readback
from server.core.spec import Chamfer, Keyway, Segment, ShaftSpec
from server.draw.dxf import build_dxf


def shaft(material=None):
    return ShaftSpec(id="s_20261123_aaaaaa", material=material, segments=[
        Segment(diameter=30, length=40, chamfer_left=Chamfer(size=2)),
        Segment(diameter=25, length=60, keyway=Keyway(length=20)),
        Segment(diameter=20, length=30, chamfer_right=Chamfer(size=1, angle=30)),
    ])


def test_volume_of_plain_cylinders():
    spec = ShaftSpec(id="s_20261123_aaaaaa", segments=[Segment(diameter=30, length=40), Segment(diameter=20, length=10)])
    assert volume_mm3(spec) == pytest.approx(math.pi * (15**2 * 40 + 10**2 * 10))
    assert volume_mm3(ShaftSpec(id="s_20261123_aaaaaa")) == 0


def test_volume_matches_the_cad_model():
    from server.cad.step import build_solid

    cad = build_solid(shaft()).val().Volume()
    assert volume_mm3(shaft()) == pytest.approx(cad, rel=0.002)


@pytest.mark.parametrize("material, name, rho", [
    ("C45", "steel", 7.85), ("c 45", "steel", 7.85), ("42CrMo4", "steel", 7.85), ("S355", "steel", 7.85),
    ("steel", "steel", 7.85), ("1.0503", "steel", 7.85), ("16MnCr5", "steel", 7.85),
    ("stainless steel", "stainless steel", 7.9), ("1.4301", "stainless steel", 7.9), ("AISI 304", "stainless steel", 7.9),
    ("aluminium", "aluminium", 2.7), ("Aluminum 6061", "aluminium", 2.7), ("EN AW-6082", "aluminium", 2.7), ("AlMgSi1", "aluminium", 2.7),
    ("brass", "brass", 8.5), ("CuZn39Pb3", "brass", 8.5), ("bronze", "bronze", 8.8), ("copper", "copper", 8.96),
    ("titanium", "titanium", 4.5), ("cast iron", "cast iron", 7.2), ("POM", "POM", 1.41), ("nylon", "PA6", 1.14),
])
def test_density_by_name(material, name, rho):
    assert density(material) == (name, rho)


@pytest.mark.parametrize("material", [None, "", "wood", "unobtainium", "C", "45"])
def test_unknown_material_has_no_density(material):
    assert density(material) is None


def test_mass_and_its_text():
    assert mass(shaft()) is None and mass(shaft("wood")) is None
    m = mass(shaft("C45"))
    assert m["material"] == "steel" and m["density"] == 7.85
    assert m["kg"] == pytest.approx(volume_mm3(shaft()) * 7.85e-6, abs=0.001)
    assert m["text"] == mass_text(m["kg"])
    assert mass_text(0.4237) == "424 g" and mass_text(1.234) == "1.23 kg" and mass_text(12.34) == "12.3 kg" and mass_text(0.0042) == "4.2 g"


def test_readback_and_sheet_show_the_mass():
    assert "kg" not in readback(shaft()) and " g" not in readback(shaft())
    steel = shaft("C45")
    assert readback(steel).endswith(f"L130  {mass(steel)['text']}")
    texts = [t.dxf.text for t in build_dxf(steel).modelspace().query("TEXT")]
    assert any(f"Mass: {mass(steel)['text']} (steel, 7.85 g/cm³)" in t for t in texts)
    texts = [t.dxf.text for t in build_dxf(shaft("wood")).modelspace().query("TEXT")]
    assert not any("Mass" in t for t in texts)
