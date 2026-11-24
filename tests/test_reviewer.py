"""Reviewer: hints from a second model call. It never changes or blocks anything."""

import pytest
from fastapi.testclient import TestClient

from server.ai.reviewer import MAX_NOTE_CHARS, REVIEW_PROMPT, ModelReviewer, build_review_message, get_reviewer, parse_review
from server.core.ops import InterpreterResult
from server.core.spec import Segment, ShaftSpec
from server.core.validation import validate
from server.main import create_app


def shaft():
    return ShaftSpec(id="s_20261123_aaaaaa", segments=[Segment(diameter=30, length=40), Segment(diameter=90, length=10)])


def test_parse():
    assert parse_review('{"notes": ["  Check   the Ø90 flange. ", ""]}') == ["Check the Ø90 flange."]
    assert parse_review('```json\n{"notes": []}\n```') == []
    for bad in ["", "no notes", '{"notes": "one"}', '{"notes": ["a","b","c","d"]}', '{"notes": [1]}']:
        with pytest.raises(ValueError):
            parse_review(bad)


def test_the_message_has_the_shaft_and_the_checks():
    text = build_review_message(shaft(), validate(shaft()))
    assert "diameter 90" in text and "warning: Large step: 30 to 90" in text
    assert "cannot change, approve" in REVIEW_PROMPT


def test_a_failing_model_gives_no_notes():
    def broken(system, user):
        raise RuntimeError("offline")

    assert ModelReviewer(broken).review(shaft(), validate(shaft())) == []
    assert ModelReviewer(lambda s, u: "I think it is fine").review(shaft(), validate(shaft())) == []
    assert ModelReviewer(lambda s, u: '{"notes": ["Is Ø90 right?"]}').review(shaft(), validate(shaft())) == ["Is Ø90 right?"]


def test_get_reviewer(monkeypatch):
    class WithModel:
        def _complete(self, system, user):
            return '{"notes": []}'

    assert get_reviewer(WithModel()) is not None
    assert get_reviewer(object()) is None
    monkeypatch.setenv("REVIEWER", "off")
    assert get_reviewer(WithModel()) is None


class Interp:
    def interpret(self, spec, utterance):
        return InterpreterResult.model_validate({"ops": [{"op": "edit_segment", "index": 1, "diameter": 28}], "ask": None})


class FixedReviewer:
    def __init__(self):
        self.calls = 0

    def review(self, spec, report):
        self.calls += 1
        return [f"Hint {self.calls}: <b>check</b> Ø{spec.segments[0].diameter:g}"]


def test_finish_gets_hints_once_per_revision_and_shows_them_as_hints(tmp_path):
    reviewer = FixedReviewer()
    client = TestClient(create_app(auth=False, data_dir=tmp_path, interpreter=Interp(), drive=None, reviewer=reviewer, review_in_background=False))
    sid = client.post("/session").json()["id"]
    for number in ("30", "40"):
        client.post(f"/session/{sid}/utterance", json={"text": number})
    assert client.get(f"/session/{sid}/spec").json()["review"] is None

    st = client.post(f"/session/{sid}/finish").json()
    assert st["review"] == {"revision": "A", "notes": ["Hint 1: <b>check</b> Ø30"]}
    before = st["spec"]
    client.post(f"/session/{sid}/finish")  # same revision: no second call
    assert reviewer.calls == 1

    page = client.get(f"/s/{sid}").text
    assert "AI hints" in page and "not a check" in page
    assert "Hint 1: &lt;b&gt;check&lt;/b&gt; Ø30" in page  # model text is escaped
    assert client.get(f"/session/{sid}/spec").json()["spec"] == before  # the review changed nothing

    client.post(f"/session/{sid}/utterance", json={"text": "make it 28"})
    assert client.get(f"/session/{sid}/spec").json()["review"] is None  # hints of an old revision are not shown
    st = client.post(f"/session/{sid}/finish").json()
    assert st["review"] == {"revision": "B", "notes": ["Hint 2: <b>check</b> Ø28"]}


def test_no_reviewer_means_no_hints(tmp_path):
    client = TestClient(create_app(auth=False, data_dir=tmp_path, interpreter=Interp(), drive=None))
    sid = client.post("/session").json()["id"]
    for number in ("30", "40"):
        client.post(f"/session/{sid}/utterance", json={"text": number})
    st = client.post(f"/session/{sid}/finish").json()
    assert st["finished"] and st["review"] is None
    assert "AI hints" not in client.get(f"/s/{sid}").text


def test_a_hint_that_is_too_long_is_dropped_and_the_others_stay():
    from server.ai.reviewer import MAX_NOTE_CHARS, ReviewResult

    notes = ReviewResult(notes=["Material is not set.", "x" * (MAX_NOTE_CHARS + 1)]).notes
    assert notes == ["Material is not set."]
