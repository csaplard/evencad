"""ShaftSpec: the data model of one stepped shaft (EVENCAD_SPEC.md, section 5).

Units are millimetres. The axis runs along X. Segments go left to right.
"""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


def fmt(value: float) -> str:
    """Short number text: 30.0 -> "30", 35.50 -> "35.5"."""
    return f"{value:.3f}".rstrip("0").rstrip(".")


class Chamfer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    size: float  # along the axis, mm
    angle: float = 45  # from the axis, degrees


class Segment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    diameter: float
    length: float
    chamfer_left: Optional[Chamfer] = None
    chamfer_right: Optional[Chamfer] = None


class ShaftSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str = "Shaft"
    material: Optional[str] = None
    segments: list[Segment] = Field(default_factory=list)
    status: Literal["draft", "approved"] = "draft"
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None

    # Derived values. Never stored.
    @property
    def total_length(self) -> float:
        return sum(s.length for s in self.segments)

    @property
    def max_diameter(self) -> float:
        return max((s.diameter for s in self.segments), default=0)
