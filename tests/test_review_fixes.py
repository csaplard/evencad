"""Fixes from the independent code review (Nov 23). One test per finding."""

import ezdxf
import pytest
from fastapi.testclient import TestClient

from server.core.guide import is_rejection, is_undo, parse_number
from server.core.mass import density, volume_mm3
from server.core.ops import InterpreterResult
from server.core.spec import Chamfer, Keyway, Segment, ShaftSpec
from server.core.validation import validate
from server.draw.glasses3d import render_glasses_3d
from server.draw.model import slots
from server.main import create_app


class Scripted:
    """Answers by the exact text it gets, and remembers every text."""

    def __init__(self):
        self.seen = []

    def interpret(self, spec, utterance):
        self.seen.append(utterance)
        answers = {
            "add a keyway to the second one": {"ops": [], "ask": "How long is the keyway?"},
            "add a keyway to the second one [you asked: How long is the keyway?] twenty": {"ops": [{"op": "set_keyway", "index": 2, "length": 20}]},
            "flange": {"ops": [{"op": "add_segment", "diameter": 90, "length": 10}]},
            "finish": {"ops": [{"op": "finish"}]},
            "second 28": {"ops": [{"op": "edit_segment", "index": 2, "diameter": 28}]},
        }
        return InterpreterResult.model_validate({"ask": None, **answers[utterance]})


@pytest.fixture
def model():
    return Scripted()


@pytest.fixture
def client(tmp_path, model):
    return TestClient(create_app(auth=False, data_dir=tmp_path, interpreter=model, drive=None))


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


def dims(st):
    return [(s["diameter"], s["length"]) for s in st["spec"]["segments"]]


# 1 ─ approval needs a real name
@pytest.mark.parametrize("name", ["  ", " a ", "\t\n", ""])
def test_a_blank_name_cannot_approve(client, sid, name):
    say(client, sid, "finish")
    assert client.post(f"/session/{sid}/approve", json={"name": name}).status_code == 422
    assert client.get(f"/session/{sid}/spec").json()["spec"]["status"] == "draft"


def test_the_name_is_trimmed(client, sid):
    say(client, sid, "finish")
    st = client.post(f"/session/{sid}/approve", json={"name": "  Kis Anna  "}).json()
    assert st["spec"]["approved_by"] == "Kis Anna"


# 2 ─ "no" after a question or a warning prompt only dismisses it
def test_no_after_a_question_does_not_undo(client, sid):
    assert say(client, sid, "add a keyway to the second one")["ask"]
    st = say(client, sid, "cancel")
    assert not st["undone"] and dims(st) == [(30, 40), (25, 60)] and st["ask"] is None
    assert say(client, sid, "no")["undone"]  # nothing is waiting now: this one is a real undo


def test_no_after_the_warning_prompt_does_not_undo(client, sid):
    say(client, sid, "flange")
    assert say(client, sid, "finish")["needs_confirm"]
    st = say(client, sid, "no")
    assert not st["undone"] and not st["needs_confirm"] and len(dims(st)) == 3
    assert say(client, sid, "undo")["undone"]


def test_undo_words_always_undo():
    assert is_undo("Undo.") and is_undo("go back") and not is_undo("no") and not is_undo("cancel")
    assert is_rejection("no") and is_rejection("undo")


def test_undo_after_a_question_still_undoes(client, sid):
    say(client, sid, "add a keyway to the second one")
    st = say(client, sid, "undo")
    assert st["undone"] and dims(st) == [(30, 40)]


# 3 ─ a bare number after a question answers the question
def test_a_number_after_a_question_goes_to_the_model_with_the_question(client, sid, model):
    say(client, sid, "add a keyway to the second one")
    st = say(client, sid, "twenty")
    assert model.seen[-1] == "add a keyway to the second one [you asked: How long is the keyway?] twenty"
    assert st["heard"] == "twenty" and st["spec"]["segments"][1]["keyway"] == {"length": 20}
    assert st["guide"]["field"] == "diameter" and st["guide"]["diameter"] is None
    assert say(client, sid, "20")["guide"]["diameter"] == 20  # the guide works again on the next turn


# 4 ─ the keyway sits on the cylindrical part, clear of the chamfers
def test_keyway_is_centred_between_the_chamfers():
    spec = ShaftSpec(id="s_20261123_aaaaaa", segments=[
        Segment(diameter=30, length=40, chamfer_left=Chamfer(size=10, angle=30), keyway=Keyway(length=30)),
        Segment(diameter=20, length=20),
    ])
    assert validate(spec).errors == []
    (slot,) = slots(spec)
    assert (slot.x1, slot.x2) == (10, 40)
    plain = spec.model_copy(deep=True)
    plain.segments[0].keyway = None
    lit = lambda img: sum(1 for b in img.tobytes() if b)  # noqa: E731
    assert lit(render_glasses_3d(spec, 30)) > lit(render_glasses_3d(plain, 30))

    from server.cad.step import build_solid

    assert volume_mm3(spec) == pytest.approx(build_solid(spec).val().Volume(), rel=0.003)


# 5 ─ an approved revision is never overwritten
def test_a_finish_after_an_approval_reset_gets_a_new_letter(client, sid, tmp_path):
    say(client, sid, "finish")
    client.post(f"/session/{sid}/approve", json={"name": "Kis Anna"})
    say(client, sid, "second 28")
    client.post(f"/session/{sid}/undo")  # same content as revision A again
    st = say(client, sid, "finish")
    assert st["revision"] == "B" and st["spec"]["status"] == "draft"
    kept = [t.dxf.text for t in ezdxf.readfile(tmp_path / "out" / sid / "rev_A" / "shaft.dxf").modelspace().query("TEXT")]
    assert any("Status: APPROVED   Rev: A" in t for t in kept)


def test_finish_again_on_an_approved_drawing_keeps_the_letter(client, sid):
    say(client, sid, "finish")
    client.post(f"/session/{sid}/approve", json={"name": "Kis Anna"})
    st = client.post(f"/session/{sid}/finish").json()
    assert st["revision"] == "A" and st["spec"]["status"] == "approved"


# 8 ─ density table
@pytest.mark.parametrize("material, name", [
    ("aluminium bronze", "bronze"), ("S316", "stainless steel"), ("S235JR", "steel"), ("S355J2", "steel"),
    ("C45E", "steel"), ("GG25", "cast iron"), ("GGG40", "cast iron"), ("EN-GJL-250", "cast iron"),
    ("1.3505", "steel"), ("AISI 1045", "steel"), ("Ck45", "steel"), ("EN AW-7075", "aluminium"),
])
def test_density_families(material, name):
    assert density(material)[0] == name


@pytest.mark.parametrize("material", ["1.6082", "1.7075", "1.2024"])
def test_steel_numbers_are_not_aluminium(material):
    assert density(material) == ("steel", 7.85)


@pytest.mark.parametrize("material", ["PTFE C 25", "rev c 12", "PVC", "oak"])
def test_other_texts_have_no_density(material):
    assert density(material) is None


# 9 ─ odd characters in the token
def test_a_non_ascii_token_is_refused_cleanly(tmp_path):
    client = TestClient(create_app(data_dir=tmp_path, interpreter=Scripted(), drive=None))
    sid = client.post("/session").json()["id"]
    assert client.get(f"/session/{sid}/spec", params={"k": "é"}).status_code == 401


# 10 ─ the session file is written in one step
def test_save_leaves_no_temp_file_and_a_whole_json(client, sid, tmp_path):
    import json

    files = sorted(p.name for p in (tmp_path / "sessions").iterdir())
    assert files == [f"{sid}.json"]
    assert json.loads((tmp_path / "sessions" / f"{sid}.json").read_text(encoding="utf-8"))["spec"]["id"] == sid


# 11 ─ finish drops a half-entered segment
def test_finish_clears_a_pending_diameter(client, sid):
    say(client, sid, "20")
    st = say(client, sid, "finish")
    assert st["finished"]
    st = say(client, sid, "no")  # undoes the last real entry, not a hidden pending number
    assert st["undone"] and dims(st) == [(30, 40)] and st["guide"]["diameter"] is None


# 12 ─ number parser
@pytest.mark.parametrize("text", ["25?", "twenty five?", "25,30", "1,000", "25 point", "point 5"])
def test_doubt_and_odd_punctuation_are_not_numbers(text):
    assert parse_number(text, "diameter") is None


@pytest.mark.parametrize("text, value", [("Ø25", 25), ("ø 25", 25), ("25 point 5", 25.5), ("30 dia", 30), ("30 diameter", 30), ("25,5", 25.5)])
def test_more_ways_to_say_a_diameter(text, value):
    assert parse_number(text, "diameter") == value


# 13 ─ the revision test now looks at the content
def test_a_new_revision_has_the_new_content(client, sid, tmp_path):
    say(client, sid, "finish")
    say(client, sid, "second 28")
    say(client, sid, "finish")
    out = tmp_path / "out" / sid

    def dia(path):
        return sorted(round(d.get_measurement()) for d in ezdxf.readfile(path).modelspace().query("DIMENSION"))

    assert dia(out / "rev_A" / "shaft.dxf") != dia(out / "shaft.dxf")


def test_the_review_also_works_in_the_background(tmp_path):
    import time

    class Slow:
        def review(self, spec, report):
            time.sleep(0.2)
            return ["Look at the step."]

    client = TestClient(create_app(auth=False, data_dir=tmp_path, interpreter=Scripted(), drive=None, reviewer=Slow()))
    sid = client.post("/session").json()["id"]
    for number in ("30", "40"):
        say(client, sid, number)
    assert client.post(f"/session/{sid}/finish").json()["review"] is None  # the finish did not wait
    client.post(f"/session/{sid}/finish")  # a second finish must not start a second review
    for _ in range(40):
        st = client.get(f"/session/{sid}/spec").json()
        if st["review"]:
            break
        time.sleep(0.1)
    assert st["review"] == {"revision": "A", "notes": ["Look at the step."]}
    import json

    log = json.loads((tmp_path / "sessions" / f"{sid}.json").read_text(encoding="utf-8"))["log"]
    assert [e["event"] for e in log].count("review") == 1
