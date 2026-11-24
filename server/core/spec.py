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


class Keyway(BaseModel):
    """A key slot on top of one segment, centred along it. Only the length is stored.

    Width and depth come from the table in server/core/keyway.py, by the segment diameter.
    """

    model_config = ConfigDict(extra="forbid")

    length: float  # along the axis, mm, round ends included


class Undercut(BaseModel):
    """A plain relief groove at the root of a shoulder: a rectangle, `width` along the axis."""

    model_config = ConfigDict(extra="forbid")

    width: float
    depth: float  # radial, below the surface of its segment


class Segment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    diameter: float
    length: float
    chamfer_left: Optional[Chamfer] = None
    chamfer_right: Optional[Chamfer] = None
    keyway: Optional[Keyway] = None
    # Root features. They sit at an end of this segment where the neighbour is larger.
    # One end has a fillet or an undercut, never both.
    fillet_left: Optional[float] = None  # radius, mm
    fillet_right: Optional[float] = None
    undercut_left: Optional[Undercut] = None
    undercut_right: Optional[Undercut] = None
    fit: Optional[str] = None  # ISO 286 shaft fit as text, for example "h6". A note only.
    roughness: Optional[float] = None  # Ra in micrometres. A note only.


def end_size(seg: Segment, side: str) -> float:
    """Length along the axis that the end feature of one side takes ("left" or "right")."""
    chamfer, fillet, undercut = (getattr(seg, f"{kind}_{side}") for kind in ("chamfer", "fillet", "undercut"))
    return max(chamfer.size if chamfer else 0, fillet or 0, undercut.width if undercut else 0)


class ShaftSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str = "Shaft"
    material: Optional[str] = None
    segments: list[Segment] = Field(default_factory=list)
    revision: Optional[str] = None  # "A", "B", ... set by the server at finish
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
