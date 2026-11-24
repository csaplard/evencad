"""Every operation from SAYCAD_SPEC.md section 5."""

import pytest
from pydantic import ValidationError

from server.core.ops import InterpreterResult, OpError, apply_op, apply_ops, parse_op
from server.core.spec import ShaftSpec


def spec_with(*pairs):
    s = ShaftSpec(id="s_20261123_aaaaaa")
    for d, length in pairs:
        s = apply_op(s, parse_op({"op": "add_segment", "diameter": d, "length": length}))
    return s


def dims(spec):
    return [(s.diameter, s.length) for s in spec.segments]


def test_add_segment_appends_by_default():
    s = spec_with((30, 40), (25, 60))
    assert dims(s) == [(30, 40), (25, 60)]


def test_add_segment_at_index_inserts_before_that_segment():
    s = spec_with((30, 40), (25, 60))
    s = apply_op(s, parse_op({"op": "add_segment", "diameter": 50, "length": 5, "at": 1}))
    assert dims(s) == [(50, 5), (30, 40), (25, 60)]


def test_add_segment_at_bad_index_fails():
    s = spec_with((30, 40))
    with pytest.raises(OpError):
        apply_op(s, parse_op({"op": "add_segment", "diameter": 50, "length": 5, "at": 5}))


def test_apply_does_not_change_the_input_spec():
    s = spec_with((30, 40))
    apply_op(s, parse_op({"op": "edit_segment", "index": 1, "diameter": 99}))
    assert dims(s) == [(30, 40)]


def test_edit_segment_by_number():
    s = spec_with((30, 40), (25, 60))
    s = apply_op(s, parse_op({"op": "edit_segment", "index": 2, "diameter": 28}))
    assert dims(s) == [(30, 40), (28, 60)]


def test_edit_segment_last_changes_only_given_fields():
    s = spec_with((30, 40), (25, 60))
    s = apply_op(s, parse_op({"op": "edit_segment", "index": "last", "length": 65}))
    assert dims(s) == [(30, 40), (25, 65)]


def test_edit_segment_needs_a_value():
    with pytest.raises(ValidationError):
        parse_op({"op": "edit_segment", "index": 1})


def test_edit_segment_out_of_range_fails():
    s = spec_with((30, 40))
    with pytest.raises(OpError):
        apply_op(s, parse_op({"op": "edit_segment", "index": 3, "diameter": 10}))


def test_edit_on_empty_spec_fails():
    s = spec_with()
    with pytest.raises(OpError):
        apply_op(s, parse_op({"op": "edit_segment", "index": "last", "diameter": 10}))


def test_delete_segment():
    s = spec_with((30, 40), (25, 60), (20, 30))
    s = apply_op(s, parse_op({"op": "delete_segment", "index": 2}))
    assert dims(s) == [(30, 40), (20, 30)]
    s = apply_op(s, parse_op({"op": "delete_segment", "index": "last"}))
    assert dims(s) == [(30, 40)]


def test_chamfer_on_the_ends():
    s = spec_with((30, 40), (20, 30))
    s = apply_op(s, parse_op({"op": "set_chamfer", "where": "left_end", "size": 2}))
    s = apply_op(s, parse_op({"op": "set_chamfer", "where": "right_end", "size": 1, "angle": 30}))
    assert s.segments[0].chamfer_left.size == 2
    assert s.segments[0].chamfer_left.angle == 45
    assert s.segments[-1].chamfer_right.size == 1
    assert s.segments[-1].chamfer_right.angle == 30


def test_chamfer_on_a_step_goes_to_the_larger_segment():
    # Step 1 is between segment 1 and segment 2.
    s = spec_with((30, 40), (20, 30), (25, 10))
    s = apply_op(s, parse_op({"op": "set_chamfer", "where": 1, "size": 1}))
    assert s.segments[0].chamfer_right.size == 1
    assert s.segments[1].chamfer_left is None
    s = apply_op(s, parse_op({"op": "set_chamfer", "where": 2, "size": 1}))
    assert s.segments[2].chamfer_left.size == 1
    assert s.segments[1].chamfer_right is None


def test_chamfer_on_a_step_without_a_shoulder_fails():
    s = spec_with((30, 40), (30, 30))
    with pytest.raises(OpError):
        apply_op(s, parse_op({"op": "set_chamfer", "where": 1, "size": 1}))


def test_chamfer_on_a_missing_step_fails():
    s = spec_with((30, 40))
    with pytest.raises(OpError):
        apply_op(s, parse_op({"op": "set_chamfer", "where": 1, "size": 1}))


def test_chamfer_size_zero_removes_it():
    s = spec_with((30, 40))
    s = apply_op(s, parse_op({"op": "set_chamfer", "where": "right_end", "size": 1}))
    s = apply_op(s, parse_op({"op": "set_chamfer", "where": "right_end", "size": 0}))
    assert s.segments[0].chamfer_right is None


def test_set_material_and_title():
    s = spec_with((30, 40))
    s = apply_ops(s, [parse_op({"op": "set_material", "text": "C45"}), parse_op({"op": "set_title", "text": "Drive shaft"})])
    assert s.material == "C45"
    assert s.title == "Drive shaft"


def test_unknown_op_is_rejected():
    with pytest.raises(ValidationError):
        parse_op({"op": "approve", "name": "AI"})


def test_extra_fields_are_rejected():
    with pytest.raises(ValidationError):
        parse_op({"op": "add_segment", "diameter": 30, "length": 40, "points": [[0, 0]]})


def test_apply_ops_is_all_or_nothing():
    s = spec_with((30, 40))
    ops = [parse_op({"op": "add_segment", "diameter": 20, "length": 10}), parse_op({"op": "delete_segment", "index": 9})]
    with pytest.raises(OpError):
        apply_ops(s, ops)
    assert dims(s) == [(30, 40)]


def test_interpreter_result_is_ops_or_ask_not_both():
    ok = InterpreterResult.model_validate({"ops": [{"op": "undo"}], "ask": None})
    assert ok.ops[0].op == "undo"
    ask = InterpreterResult.model_validate({"ops": [], "ask": "Segment 2 or 3?"})
    assert ask.ask
    with pytest.raises(ValidationError):
        InterpreterResult.model_validate({"ops": [{"op": "undo"}], "ask": "Really?"})
    with pytest.raises(ValidationError):
        InterpreterResult.model_validate({"ops": [], "ask": None})
