"""Interpreter: answer checking, retry, and the golden transcripts (spec section 8).

The golden tests replay recorded model answers from samples/golden.json.
`pytest -m live` asks the real model through the adapter chosen by INTERPRETER.
"""

import json
from pathlib import Path

import pytest

from server.ai.interpreter import NOT_UNDERSTOOD, RecordedInterpreter, get_interpreter, interpret_with, parse_result
from server.ai.prompt import SYSTEM_PROMPT, build_user_message
from server.core.ops import parse_op
from server.core.spec import Segment, ShaftSpec

GOLDEN = json.loads((Path(__file__).parent.parent / "samples" / "golden.json").read_text(encoding="utf-8"))


def spec_of(before):
    return ShaftSpec(id="s_20261123_aaaaaa", segments=[Segment(diameter=d, length=length) for d, length in before])


def check(case, result):
    expect = case["expect"]
    if expect.get("ask"):
        assert result.ops == []
        assert result.ask and len(result.ask) <= 120
    else:
        assert result.ask is None
        assert result.ops == [parse_op(op) for op in expect["ops"]]


@pytest.mark.parametrize("case", GOLDEN, ids=[c["name"] for c in GOLDEN])
def test_golden_recorded(case):
    assert case["recorded"], "run: python -m tools.record_golden"
    interpreter = RecordedInterpreter({case["utterance"]: case["recorded"]})
    check(case, interpreter.interpret(spec_of(case["before"]), case["utterance"]))


@pytest.mark.live
@pytest.mark.parametrize("case", GOLDEN, ids=[c["name"] for c in GOLDEN])
def test_golden_live(case):
    check(case, get_interpreter().interpret(spec_of(case["before"]), case["utterance"]))


def test_parse_plain_and_fenced_json():
    plain = parse_result('{"ops": [{"op": "undo"}], "ask": null}')
    fenced = parse_result('```json\n{"ops": [{"op": "undo"}], "ask": null}\n```')
    assert plain == fenced and plain.ops[0].op == "undo"


def test_parse_drops_explicit_nulls_in_ops():
    r = parse_result('{"ops": [{"op": "add_segment", "diameter": 30, "length": 40, "at": null}], "ask": null}')
    assert r.ops[0].at is None


@pytest.mark.parametrize(
    "raw",
    [
        "Sure! Here are the operations.",
        "[1, 2]",
        '{"ops": [{"op": "approve"}], "ask": null}',
        '{"ops": [{"op": "add_segment", "diameter": 30}], "ask": null}',
        '{"ops": [{"op": "add_segment", "diameter": 30, "length": 40, "points": [[0, 0]]}], "ask": null}',
        '{"ops": [], "ask": null}',
        '{"ops": [{"op": "undo"}], "ask": "sure?"}',
        '{"ops": [{"op": "undo"}], "ask": null, "note": "hi"}',
    ],
)
def test_parse_rejects_invalid_answers(raw):
    with pytest.raises(ValueError):
        parse_result(raw)


def test_invalid_answer_is_retried_once_then_asks():
    calls = []

    def always_bad(system, user):
        calls.append(user)
        return "I think you want a shaft."

    r = interpret_with(always_bad, spec_of([]), "hello")
    assert len(calls) == 2
    assert r.ops == [] and r.ask == NOT_UNDERSTOOD


def test_retry_can_recover():
    answers = iter(["oops", '{"ops": [{"op": "finish"}], "ask": null}'])
    r = interpret_with(lambda system, user: next(answers), spec_of([]), "finish")
    assert r.ops[0].op == "finish"


def test_prompt_contains_the_current_spec_and_the_sentence():
    msg = build_user_message(spec_of([[30, 40], [25, 60]]), 'make the "second" one 28')
    assert "2: diameter 25, length 60" in msg
    assert '"make the \\"second\\" one 28"' in msg
    assert "approve" in SYSTEM_PROMPT and "Never guess" in SYSTEM_PROMPT
