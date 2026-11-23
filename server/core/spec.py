"""ShaftSpec: the data model of one stepped shaft (EVENCAD_SPEC.md, section 5).

Units are millimetres. The axis runs along X. Segments go left to right.
Validation rules and operations are added in step 2.
"""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class Chamfer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    size: float
    angle: float = 45


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
