"""Revisions: every finish of a changed drawing gets the next letter. A change ends an approval."""

import ezdxf
import pytest
from fastapi.testclient import TestClient

from server.core.ops import InterpreterResult
from server.main import create_app, revision_name


class Fake:
    def interpret(self, spec, utterance):
        answers = {
            "second 28": {"ops": [{"op": "edit_segment", "index": 2, "diameter": 28}]},
            "finish": {"ops": [{"op": "finish"}]},
        }
        return InterpreterResult.model_validate({"ask": None, **answers[utterance]})


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(data_dir=tmp_path, interpreter=Fake(), drive=None))


@pytest.fixture
def sid(client):
    sid = client.post("/session").json()["id"]
    for number in ("30", "40", "25", "60"):
        say(client, sid, number)
    return sid


def say(client, sid, text):
    r = client.post(f"/session/{sid}/utterance", json={"text": text})
    assert r.status_code == 200, r.text
    return r.json()


def test_revision_names():
    assert [revision_name(n) for n in (1, 2, 26, 27, 28, 52, 53)] == ["A", "B", "Z", "AA", "AB", "AZ", "BA"]


def test_each_changed_finish_gets_the_next_letter(client, sid, tmp_path):
    assert client.get(f"/session/{sid}/spec").json()["revision"] is None
    st = say(client, sid, "finish")
    assert st["revision"] == "A" and st["spec"]["revision"] == "A"
    assert say(client, sid, "finish")["revision"] == "A"  # nothing changed: still A

    st = say(client, sid, "second 28")
    assert not st["finished"] and st["revision"] is None
    assert say(client, sid, "finish")["revision"] == "B"

    out = tmp_path / "out" / sid
    assert (out / "rev_A" / "shaft.pdf").exists() and (out / "rev_B" / "shaft.step").exists()
    texts = [t.dxf.text for t in ezdxf.readfile(out / "shaft.dxf").modelspace().query("TEXT")]
    assert any("Rev: B" in t for t in texts)
    old = [t.dxf.text for t in ezdxf.readfile(out / "rev_A" / "shaft.dxf").modelspace().query("TEXT")]
    assert any("Rev: A" in t for t in old)


def test_old_revisions_can_be_downloaded(client, sid):
    say(client, sid, "finish")
    first = client.get(f"/session/{sid}/files/dxf").content
    say(client, sid, "second 28")
    say(client, sid, "finish")
    assert client.get(f"/session/{sid}/files/dxf", params={"rev": "A"}).content == first
    assert client.get(f"/session/{sid}/files/dxf").content != first
    assert client.get(f"/session/{sid}/files/dxf", params={"rev": "C"}).status_code == 404
    assert client.get(f"/session/{sid}/files/dxf", params={"rev": "../x"}).status_code == 404
    page = client.get(f"/s/{sid}").text
    assert "Revision B" in page and "rev=A" in page


def test_a_change_after_approval_makes_it_a_draft_again(client, sid, tmp_path):
    say(client, sid, "finish")
    st = client.post(f"/session/{sid}/approve", json={"name": "Kis Anna"}).json()
    assert st["spec"]["status"] == "approved"

    st = say(client, sid, "second 28")
    assert st["spec"]["status"] == "draft" and st["spec"]["approved_by"] is None and st["spec"]["approved_at"] is None
    st = say(client, sid, "finish")
    assert st["revision"] == "B" and st["spec"]["status"] == "draft"
    page = client.get(f"/s/{sid}").text
    assert "DRAFT – requires engineering approval" in page and "Approved for review by" not in page
    # The approved revision A is still there, with its mark.
    old = [t.dxf.text for t in ezdxf.readfile(tmp_path / "out" / sid / "rev_A" / "shaft.dxf").modelspace().query("TEXT")]
    assert any("Approved for review by: Kis Anna" in t for t in old)


def test_undo_after_approval_also_makes_it_a_draft(client, sid):
    say(client, sid, "finish")
    client.post(f"/session/{sid}/approve", json={"name": "Kis Anna"})
    st = client.post(f"/session/{sid}/undo").json()
    assert st["spec"]["status"] == "draft" and st["spec"]["approved_by"] is None and not st["finished"]
