"""Guided measuring: the display asks for the next number, a bare number answers it."""

import pytest
from fastapi.testclient import TestClient

from server.core.guide import next_step, parse_number
from server.core.ops import InterpreterResult
from server.core.spec import Segment, ShaftSpec
from server.main import create_app


@pytest.mark.parametrize("text, value", [
    ("25", 25),
    ("25.", 25),
    ("25.5", 25.5),
    ("25,5", 25.5),
    ("Twenty-five.", 25),
    ("twenty five point five", 25.5),
    ("twelve", 12),
    ("sixty", 60),
    ("one hundred and twenty", 120),
    ("a hundred", 100),
    ("two hundred five", 205),
    ("three point oh five", 3.05),
    ("25 mm", 25),
    ("25mm", 25),
    ("thirty millimeters", 30),
])
def test_bare_numbers(text, value):
    assert parse_number(text, "diameter") == value
    assert parse_number(text, "length") == value


@pytest.mark.parametrize("text", [
    "", "zero", "0", "undo", "finish", "fifteen fifty", "thirty forty", "30 40", "twenty fifteen",
    "make it 25", "25 or 35", "point", "hundred hundred", "five twenty", "second 28", "-5",
])
def test_everything_else_is_left_to_the_interpreter(text):
    assert parse_number(text, "diameter") is None
    assert parse_number(text, "length") is None


def test_the_asked_field_may_be_named():
    assert parse_number("diameter thirty", "diameter") == 30
    assert parse_number("dia 30", "diameter") == 30
    assert parse_number("sixty long", "length") == 60
    assert parse_number("length 60 mm", "length") == 60
    assert parse_number("60 millimeters long", "length") == 60
    # The other field is not a bare answer. The interpreter must look at it.
    assert parse_number("length sixty", "diameter") is None
    assert parse_number("sixty long", "diameter") is None
    assert parse_number("diameter thirty", "length") is None


def test_next_step():
    spec = ShaftSpec(id="s_20261123_aaaaaa")
    assert next_step(spec, None) == {"segment": 1, "field": "diameter", "diameter": None, "text": "Next: segment 1 diameter?"}
    assert next_step(spec, 25.5) == {"segment": 1, "field": "length", "diameter": 25.5, "text": "Next: segment 1 Ø25.5 length?"}
    spec.segments.append(Segment(diameter=30, length=40))
    assert next_step(spec, None)["text"] == "Next: segment 2 diameter?"


class NoNumbers:
    """Fails the test if a bare number reaches the model."""

    def interpret(self, spec, utterance):
        assert parse_number(utterance, "diameter") is None, utterance
        answers = {
            "bigger": {"ops": [], "ask": "Which segment and by how much?"},
            "second 28": {"ops": [{"op": "edit_segment", "index": 1, "diameter": 28}]},
            "undo": {"ops": [{"op": "undo"}]},
        }
        return InterpreterResult.model_validate({"ask": None, **answers[utterance]})


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(auth=False, data_dir=tmp_path, interpreter=NoNumbers(), drive=None))


@pytest.fixture
def sid(client):
    return client.post("/session").json()["id"]


def say(client, sid, text):
    r = client.post(f"/session/{sid}/utterance", json={"text": text})
    assert r.status_code == 200, r.text
    return r.json()


def dims(st):
    return [(s["diameter"], s["length"]) for s in st["spec"]["segments"]]


def test_two_bare_numbers_make_a_segment(client, sid):
    st = client.get(f"/session/{sid}/spec").json()
    assert st["guide"]["text"] == "Next: segment 1 diameter?"

    st = say(client, sid, "thirty")
    assert dims(st) == [] and st["heard"] == "thirty"
    assert st["guide"] == {"segment": 1, "field": "length", "diameter": 30, "text": "Next: segment 1 Ø30 length?"}
    assert st["can_undo"]

    st = say(client, sid, "40 long")
    assert dims(st) == [(30, 40)]
    assert st["guide"]["text"] == "Next: segment 2 diameter?"
    assert st["readback"].startswith("1 step")

    say(client, sid, "25")
    assert dims(say(client, sid, "sixty")) == [(30, 40), (25, 60)]


def test_the_pending_diameter_survives_a_reload_and_a_question(client, sid, tmp_path):
    say(client, sid, "thirty")
    st = say(client, sid, "bigger")
    assert st["ask"] and st["guide"]["diameter"] == 30
    fresh = TestClient(create_app(auth=False, data_dir=tmp_path, interpreter=NoNumbers(), drive=None))
    assert fresh.get(f"/session/{sid}/spec").json()["guide"]["diameter"] == 30


def test_undo_drops_the_pending_diameter_first(client, sid):
    say(client, sid, "thirty")
    say(client, sid, "forty")
    say(client, sid, "25")
    st = client.post(f"/session/{sid}/undo").json()
    assert st["guide"]["text"] == "Next: segment 2 diameter?" and dims(st) == [(30, 40)]
    say(client, sid, "25")
    st = say(client, sid, "undo")  # by voice, through the interpreter
    assert st["guide"]["diameter"] is None and dims(st) == [(30, 40)]
    st = client.post(f"/session/{sid}/undo").json()
    assert dims(st) == [] and not st["can_undo"]


def test_a_full_sentence_ends_the_pending_entry(client, sid):
    say(client, sid, "thirty")
    say(client, sid, "forty")
    say(client, sid, "25")
    st = say(client, sid, "second 28")
    assert dims(st) == [(28, 40)]
    assert st["guide"] == {"segment": 2, "field": "diameter", "diameter": None, "text": "Next: segment 2 diameter?"}


def test_guided_entry_is_in_the_audit_log_and_undo_stack(client, sid, tmp_path):
    import json

    say(client, sid, "thirty")
    say(client, sid, "forty")
    saved = json.loads((tmp_path / "sessions" / f"{sid}.json").read_text(encoding="utf-8"))
    assert [e["event"] for e in saved["log"]] == ["created", "guide_diameter", "applied"]
    assert saved["log"][-1]["source"] == "guide"
    assert saved["history"][0]["ops"] == [{"op": "add_segment", "diameter": 30.0, "length": 40.0}]


def test_no_guide_when_finished(client, sid):
    say(client, sid, "thirty")
    say(client, sid, "forty")
    st = client.post(f"/session/{sid}/finish").json()
    assert st["finished"] and st["guide"] is None
