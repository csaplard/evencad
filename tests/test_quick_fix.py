"""Quick fix: a spoken "no" takes the last entry back, with no model call."""

import pytest
from fastapi.testclient import TestClient

from server.core.guide import is_rejection
from server.main import create_app


@pytest.mark.parametrize("text", ["no", "No.", "NO!", "nope", "no no", "No, no.", "wrong", "That's wrong.", "not that", "undo", "Undo that.", "go back", "cancel"])
def test_rejections(text):
    assert is_rejection(text)


@pytest.mark.parametrize("text", ["", "no chamfer", "nine", "know", "no the second one is 28", "undo the chamfer", "not that one, the first"])
def test_other_sentences_are_not_rejections(text):
    assert not is_rejection(text)


class NoModel:
    def interpret(self, spec, utterance):
        raise AssertionError(f"the model must not be called for {utterance!r}")


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(data_dir=tmp_path, interpreter=NoModel(), drive=None))


def say(client, sid, text):
    r = client.post(f"/session/{sid}/utterance", json={"text": text})
    assert r.status_code == 200, r.text
    return r.json()


def dims(st):
    return [(s["diameter"], s["length"]) for s in st["spec"]["segments"]]


def test_no_takes_back_the_last_entry_and_asks_again(client):
    sid = client.post("/session").json()["id"]
    assert not say(client, sid, "thirty")["undone"]
    say(client, sid, "forty")
    st = say(client, sid, "fifty")  # misheard: it was fifteen
    assert st["guide"]["text"] == "Next: segment 2 Ø50 length?"

    st = say(client, sid, "No.")
    assert st["undone"] and st["heard"] == "No." and st["error"] is None
    assert st["guide"]["text"] == "Next: segment 2 diameter?" and dims(st) == [(30, 40)]

    st = say(client, sid, "wrong")  # now the whole first segment goes
    assert st["undone"] and dims(st) == []
    st = say(client, sid, "no")
    assert not st["undone"] and st["error"] == "Nothing to undo"


def test_the_undo_button_reports_undone_too(client):
    sid = client.post("/session").json()["id"]
    say(client, sid, "thirty")
    assert client.post(f"/session/{sid}/undo").json()["undone"]
    assert not client.post(f"/session/{sid}/undo").json()["undone"]
