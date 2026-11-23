"""Operations: the only thing the AI may output (EVENCAD_SPEC.md, section 5).

`apply_op` is plain code. It returns a new spec and never changes its input.
`undo` and `finish` are session actions. The session layer handles them.
"""

from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

from server.core.spec import Chamfer, Segment, ShaftSpec


class OpError(ValueError):
    """An operation is well formed but cannot be applied to this spec."""


class _Op(BaseModel):
    model_config = ConfigDict(extra="forbid")


Index = Union[int, Literal["last"]]


class AddSegment(_Op):
    op: Literal["add_segment"]
    diameter: float
    length: float
    at: Optional[int] = None  # 1-based position of the new segment. Default: the end.


class EditSegment(_Op):
    op: Literal["edit_segment"]
    index: Index
    diameter: Optional[float] = None
    length: Optional[float] = None

    @model_validator(mode="after")
    def _needs_a_value(self):
        if self.diameter is None and self.length is None:
            raise ValueError("edit_segment needs diameter or length")
        return self


class DeleteSegment(_Op):
    op: Literal["delete_segment"]
    index: Index


class SetChamfer(_Op):
    op: Literal["set_chamfer"]
    where: Union[Literal["left_end", "right_end"], int]  # int = step number
    size: float  # along the axis, in mm. 0 removes the chamfer.
    angle: float = 45


class SetMaterial(_Op):
    op: Literal["set_material"]
    text: str = Field(max_length=60)


class SetTitle(_Op):
    op: Literal["set_title"]
    text: str = Field(max_length=60)


class Undo(_Op):
    op: Literal["undo"]


class Finish(_Op):
    op: Literal["finish"]


Op = Annotated[
    Union[AddSegment, EditSegment, DeleteSegment, SetChamfer, SetMaterial, SetTitle, Undo, Finish],
    Field(discriminator="op"),
]
_op_adapter = TypeAdapter(Op)


def parse_op(data: dict) -> Op:
    return _op_adapter.validate_python(data)


class InterpreterResult(BaseModel):
    """What an interpreter returns: operations, or one short question."""

    model_config = ConfigDict(extra="forbid")

    ops: list[Op] = Field(default_factory=list)
    ask: Optional[str] = Field(default=None, max_length=120)

    @model_validator(mode="after")
    def _ops_or_ask(self):
        if bool(self.ops) == bool(self.ask):
            raise ValueError("give either ops or ask, not both and not neither")
        return self


def _position(spec: ShaftSpec, index: Index) -> int:
    """1-based segment number or "last" -> 0-based list position."""
    n = len(spec.segments)
    if n == 0:
        raise OpError("There are no segments yet")
    if index == "last":
        return n - 1
    if not 1 <= index <= n:
        raise OpError(f"There is no segment {index}")
    return index - 1


def apply_op(spec: ShaftSpec, op: Op) -> ShaftSpec:
    new = spec.model_copy(deep=True)
    segs = new.segments

    if isinstance(op, AddSegment):
        seg = Segment(diameter=op.diameter, length=op.length)
        if op.at is None:
            segs.append(seg)
        elif 1 <= op.at <= len(segs) + 1:
            segs.insert(op.at - 1, seg)
        else:
            raise OpError(f"Cannot add a segment at position {op.at}")

    elif isinstance(op, EditSegment):
        seg = segs[_position(new, op.index)]
        if op.diameter is not None:
            seg.diameter = op.diameter
        if op.length is not None:
            seg.length = op.length

    elif isinstance(op, DeleteSegment):
        del segs[_position(new, op.index)]

    elif isinstance(op, SetChamfer):
        chamfer = Chamfer(size=op.size, angle=op.angle) if op.size > 0 else None
        if not segs:
            raise OpError("There are no segments yet")
        if op.where == "left_end":
            segs[0].chamfer_left = chamfer
        elif op.where == "right_end":
            segs[-1].chamfer_right = chamfer
        else:
            # Step k is the shoulder between segment k and segment k+1.
            # The chamfer belongs to the edge of the larger segment.
            k = op.where
            if not 1 <= k <= len(segs) - 1:
                raise OpError(f"There is no step {k}")
            left, right = segs[k - 1], segs[k]
            if left.diameter > right.diameter:
                left.chamfer_right = chamfer
            elif right.diameter > left.diameter:
                right.chamfer_left = chamfer
            else:
                raise OpError(f"Step {k} has no shoulder")

    elif isinstance(op, SetMaterial):
        new.material = op.text.strip() or None

    elif isinstance(op, SetTitle):
        new.title = op.text.strip() or "Shaft"

    else:
        raise OpError(f"{op.op} is a session action, not a spec change")

    return new


def active_after(spec: ShaftSpec, ops: list[Op], current: Optional[int]) -> Optional[int]:
    """The 1-based segment that the operations touched last. The display marks it.

    `spec` is the shaft before the operations. `current` is the mark before them.
    """
    active = current
    for op in ops:
        before = spec
        spec = apply_op(spec, op)
        n = len(spec.segments)
        if isinstance(op, AddSegment):
            active = op.at or n
        elif isinstance(op, EditSegment):
            active = _position(spec, op.index) + 1
        elif isinstance(op, DeleteSegment):
            active = None
        elif isinstance(op, SetChamfer):
            if op.where == "left_end":
                active = 1
            elif op.where == "right_end":
                active = n
            else:
                left, right = before.segments[op.where - 1], before.segments[op.where]
                active = op.where if left.diameter > right.diameter else op.where + 1
    return active


def apply_ops(spec: ShaftSpec, ops: list[Op]) -> ShaftSpec:
    """Apply all operations, or none (raises OpError)."""
    for op in ops:
        spec = apply_op(spec, op)
    return spec
