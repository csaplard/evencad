"""Mass of the shaft: volume by formula, density from a small table.

The AI gives only the material name. The density is looked up here.
An unknown material gives no mass. Nothing is guessed.

The densities are common handbook values in g/cm³. They are for a quick estimate,
not for a calculation that someone relies on (docs/open-questions.md).
"""

import math
import re
from typing import Optional

from server.core.keyway import keyway_size
from server.core.spec import ShaftSpec
from server.core.validation import chamfer_depth

# (name, density in g/cm³, pattern on the lower-case material text). The first match wins.
_MATERIALS = [
    ("stainless steel", 7.9, r"stainless|inox|\b1\.4\d{3}\b|\b(aisi\s*)?(304|316)l?\b|x\d+crni"),
    ("cast iron", 7.2, r"cast iron|\bgj[ls]\b|\bgg[g]?\b"),
    ("aluminium", 2.7, r"alumin|\balu\b|\ben aw\b|\b(6060|6061|6082|7075|5083|2024)\b|\bal(mg|si|cu|zn)"),
    ("brass", 8.5, r"brass|\bcuzn|\bms\s?5[68]\b"),
    ("bronze", 8.8, r"bronze|\bcusn"),
    ("copper", 8.96, r"copper"),
    ("titanium", 4.5, r"titan"),
    ("POM", 1.41, r"\bpom\b|delrin|acetal"),
    ("PA6", 1.14, r"\bpa\s?6\b|nylon|polyamide"),
    ("steel", 7.85, r"steel|\bc\s?k?\s?\d{2}\b|\bs\d{3}\b|\be\d{3}\b|\bst\s?\d{2}\b|\d{2}(crmo|mncr|cr|nicrmo|crnimo)\w*|\b1\.[0-2]\d{3}\b|\b1\.[5-8]\d{3}\b"),
]


def density(material: Optional[str]) -> Optional[tuple[str, float]]:
    """(material family, g/cm³) for a material text, or None when it is not known."""
    text = (material or "").strip().lower()
    if not text:
        return None
    for name, rho, pattern in _MATERIALS:
        if re.search(pattern, text):
            return (name, rho)
    return None


def _keyway_volume(radius: float, width: float, depth: float, length: float) -> float:
    """Material removed by a keyway with round ends, cut `depth` deep from the top of the cylinder."""
    half = width / 2

    def under_arc(z):  # integral of sqrt(r² - z²)
        return z / 2 * math.sqrt(radius**2 - z**2) + radius**2 / 2 * math.asin(z / radius)

    section = 2 * under_arc(half) - width * (radius - depth)  # cross-section area of the cut
    mean_depth = section / width
    return section * (length - width) + math.pi * half**2 * mean_depth


def volume_mm3(spec: ShaftSpec) -> float:
    total = 0.0
    for s in spec.segments:
        r = s.diameter / 2
        total += math.pi * r**2 * s.length
        for c in (s.chamfer_left, s.chamfer_right):
            if c:
                r1 = r - chamfer_depth(c)
                total -= math.pi * c.size * (r**2 - (r**2 + r * r1 + r1**2) / 3)  # ring minus cone frustum
        size = keyway_size(s.diameter) if s.keyway else None
        if size and s.keyway.length > size.width:
            total -= _keyway_volume(r, size.width, size.depth, s.keyway.length)
    return total


def mass_text(kg: float) -> str:
    if kg < 0.01:
        return f"{kg * 1000:.1f} g"
    if kg < 1:
        return f"{kg * 1000:.0f} g"
    return f"{kg:.2f} kg" if kg < 10 else f"{kg:.1f} kg"


def mass(spec: ShaftSpec) -> Optional[dict]:
    """Mass estimate, or None when there is no part or the material is not in the table."""
    found = density(spec.material)
    volume = volume_mm3(spec)
    if not found or volume <= 0:
        return None
    name, rho = found
    kg = volume * rho * 1e-6
    return {"kg": round(kg, 4), "text": mass_text(kg), "material": name, "density": rho}
