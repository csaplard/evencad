"""The thin slice through the API: text -> ops -> spec -> validation -> image -> files."""

import io
import json

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pypdf import PdfReader

from server.ai.interpreter import InterpreterError
from server.core.ops import InterpreterResult
from server.main import create_app


class FakeInterpreter:
    """Maps a sentence to a fixed answer. The real prompt is tested in test_interpreter.py."""

    answers = {
        "three steps": {"ops": [
            {"op": "add_segment", "diameter": 30, "length": 40},
            {"op": "add_segment", "diameter": 25, "length": 60},
            {"op": "add_segment", "diameter": 20, "length": 30},
        ]},
        "second 28": {"ops": [{"op": "edit_segment", "index": 2, "diameter": 28}]},
        "chamfer": {"ops": [{"op": "set_chamfer", "where": "right_end", "size": 1}]},
        "bigger": {"ops": [], "ask": "Which segment and by how much?"},
        "delete nine": {"ops": [{"op": "delete_segment", "index": 9}]},
        "big flange": {"ops": [{"op": "add_segment", "diameter": 90, "length": 10}]},
        "undo": {"ops": [{"op": "undo"}]},
        "finish": {"ops": [{"op": "finish"}]},
        "zero": {"ops": [{"op": "edit_segment", "index": 1, "diameter": 0}]},
    }

    def interpret(self, spec, utterance):
        if utterance == "offline":
            raise InterpreterError("model not reachable")
        return InterpreterResult.model_validate({"ask": None, **self.answers[utterance]})


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(data_dir=tmp_path, interpreter=FakeInterpreter()))


@pytest.fixture
def sid(client):
    return client.post("/session").json()["id"]


def say(client, sid, text):
    r = client.post(f"/session/{sid}/utterance", json={"text": text})
    assert r.status_code == 200, r.text
    return r.json()


def dims(st):
    return [(s["diameter"], s["length"]) for s in st["spec"]["segments"]]


def test_typed_text_builds_the_spec_with_readback_and_validation(client, sid):
    st = say(client, sid, "three steps")
    assert dims(st) == [(30, 40), (25, 60), (20, 30)]
    assert st["readback"] == "3 steps  Ø30×40  Ø25×60  Ø20×30  L130"
    assert st["validation"] == {"errors": [], "warnings": []}
    assert st["heard"] == "three steps" and st["ask"] is None and st["can_undo"]
    assert client.get(f"/session/{sid}/spec").json()["readback"] == st["readback"]


def test_correction_and_undo(client, sid):
    say(client, sid, "three steps")
    assert dims(say(client, sid, "second 28"))[1] == (28, 60)
    st = client.post(f"/session/{sid}/undo").json()
    assert dims(st)[1] == (25, 60)
    st = say(client, sid, "undo")  # undo by voice
    assert dims(st) == [] and not st["can_undo"]
    assert client.post(f"/session/{sid}/undo").json()["error"] == "Nothing to undo"


def test_a_question_changes_nothing(client, sid):
    say(client, sid, "three steps")
    st = say(client, sid, "bigger")
    assert st["ask"] == "Which segment and by how much?"
    assert dims(st) == [(30, 40), (25, 60), (20, 30)]


def test_an_impossible_operation_changes_nothing(client, sid):
    say(client, sid, "three steps")
    st = say(client, sid, "delete nine")
    assert st["error"] == "There is no segment 9"
    assert len(dims(st)) == 3


def test_render_gives_the_band_and_two_tiles(client, sid):
    say(client, sid, "three steps")
    band = client.get(f"/session/{sid}/render")
    assert band.headers["content-type"] == "image/png"
    assert Image.open(io.BytesIO(band.content)).size == (576, 144)
    for tile in (0, 1):
        r = client.get(f"/session/{sid}/render", params={"tile": tile})
        assert Image.open(io.BytesIO(r.content)).size == (288, 144)
    assert client.get(f"/session/{sid}/render", params={"tile": 2}).status_code == 422


def test_finish_makes_the_three_files(client, sid, tmp_path):
    say(client, sid, "three steps")
    say(client, sid, "chamfer")
    assert client.get(f"/session/{sid}/files/pdf").status_code == 404  # not finished yet
    st = say(client, sid, "finish")
    assert st["finished"] and set(st["files"]) == {"step", "dxf", "pdf"}
    for kind, url in st["files"].items():
        r = client.get(url)
        assert r.status_code == 200 and len(r.content) > 500, kind
    assert len(PdfReader(io.BytesIO(client.get(st["files"]["pdf"]).content)).pages) == 1
    assert (tmp_path / "out" / sid / "shaft.step").exists()


def test_finish_is_blocked_by_errors(client, sid):
    st = client.post(f"/session/{sid}/finish").json()
    assert not st["finished"] and st["error"] == "No segments yet"
    say(client, sid, "three steps")
    say(client, sid, "zero")
    st = say(client, sid, "finish")
    assert not st["finished"] and "diameter" in st["error"]


def test_warnings_must_be_confirmed_before_finish(client, sid):
    say(client, sid, "three steps")
    st = say(client, sid, "big flange")
    assert [w["code"] for w in st["validation"]["warnings"]] == ["BIG_STEP"]
    st = say(client, sid, "finish")
    assert st["needs_confirm"] and not st["finished"]
    st = client.post(f"/session/{sid}/finish", json={"confirm_warnings": True}).json()
    assert st["finished"]


def test_a_change_after_finish_needs_a_new_finish(client, sid):
    say(client, sid, "three steps")
    assert say(client, sid, "finish")["finished"]
    st = say(client, sid, "second 28")
    assert not st["finished"] and st["files"] == {}


def test_human_approval_on_the_phone_page(client, sid):
    say(client, sid, "three steps")
    assert client.post(f"/session/{sid}/approve", json={"name": "Kis Anna"}).status_code == 409
    say(client, sid, "finish")
    page = client.get(f"/s/{sid}").text
    assert "DRAFT – requires engineering approval" in page and "Approve for review" in page
    st = client.post(f"/session/{sid}/approve", json={"name": "Kis Anna"}).json()
    assert st["spec"]["status"] == "approved" and st["spec"]["approved_by"] == "Kis Anna"
    page = client.get(f"/s/{sid}").text
    assert "Approved for review by Kis Anna" in page and "Approve for review</button>" not in page


def test_interpreter_failure_is_a_503_and_changes_nothing(client, sid):
    r = client.post(f"/session/{sid}/utterance", json={"text": "offline"})
    assert r.status_code == 503
    assert dims(client.get(f"/session/{sid}/spec").json()) == []


def test_the_session_file_keeps_an_audit_log(client, sid, tmp_path):
    say(client, sid, "three steps")
    say(client, sid, "bigger")
    say(client, sid, "undo")
    saved = json.loads((tmp_path / "sessions" / f"{sid}.json").read_text(encoding="utf-8"))
    assert [e["event"] for e in saved["log"]] == ["created", "applied", "ask", "undo"]
    assert saved["history"] == []


def test_empty_text_is_refused(client, sid):
    assert client.post(f"/session/{sid}/utterance", json={"text": ""}).status_code == 422
