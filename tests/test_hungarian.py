"""Hungarian dictation: numbers, "no" words and the speech settings."""

import pytest
from fastapi.testclient import TestClient

from server.ai.prompt import SYSTEM_PROMPT
from server.ai.stt import DOMAIN_PROMPTS, FasterWhisperStt, SttError
from server.core.guide import is_rejection, is_undo, parse_number
from server.core.ops import InterpreterResult
from server.main import create_app


@pytest.mark.parametrize("text, value", [
    ("egy", 1), ("kettő", 2), ("két", 2), ("öt", 5), ("hat", 6), ("hét", 7), ("tíz", 10), ("tizenkettő", 12), ("tizenkét", 12),
    ("tizenöt", 15), ("húsz", 20), ("huszonöt", 25), ("Huszonöt.", 25), ("harminc", 30), ("harmincöt", 35), ("negyven", 40),
    ("ötven", 50), ("hatvan", 60), ("hetvenhét", 77), ("nyolcvan", 80), ("kilencvenkilenc", 99), ("száz", 100),
    ("százhúsz", 120), ("száz húsz", 120), ("százhuszonöt", 125), ("kétszáz", 200), ("kettőszáz", 200), ("háromszázötven", 350),
    ("huszonöt egész öt", 25.5), ("huszonöt egész huszonöt", 25.25), ("három egész nulla öt", 3.05), ("nulla egész öt", 0.5),
    ("huszonöt egész öt tized", 25.5), ("huszonöt és fél", 25.5), ("25 egész 5", 25.5), ("25,5", 25.5),
    ("husz", 20), ("otven", 50), ("harmincot", 35),  # the recogniser may drop the accents
    ("harminc milliméter", 30), ("30 milliméter", 30), ("harminc millis", 30), ("átmérő harminc", 30), ("harmincas átmérő", 30),
    ("harmincas", 30), ("huszonötös", 25), ("negyvenes", 40), ("hatos", 6), ("százas", 100),
])
def test_hungarian_numbers(text, value):
    assert parse_number(text, "diameter") == value


@pytest.mark.parametrize("text, value", [("hossz hatvan", 60), ("hatvan hosszú", 60), ("hatvan milliméter hosszú", 60), ("hossza negyven", 40)])
def test_hungarian_length_words(text, value):
    assert parse_number(text, "length") == value


@pytest.mark.parametrize("text", [
    "harminc negyven", "tizenöt ötven", "huszonöt?", "hossz hatvan", "harminc vagy negyven", "egész öt", "huszonöt egész",
    "nulla", "száz száz", "tizentíz", "huszonhúsz", "harminchúsz", "nem", "kész", "hatvan hosszú", "twenty öt",
])
def test_not_a_bare_diameter(text):
    assert parse_number(text, "diameter") is None


@pytest.mark.parametrize("text", ["Nem.", "nem, nem", "nem jó", "rossz", "mégse", "mégsem", "vissza", "Visszavonás.", "töröld"])
def test_hungarian_rejections(text):
    assert is_rejection(text)


def test_hungarian_undo_words():
    assert is_undo("vissza") and is_undo("Visszavonás") and is_undo("vond vissza")
    assert not is_undo("nem") and not is_undo("mégse")
    assert not is_rejection("nem tudom") and not is_rejection("nem harminc, hanem negyven")


class NoModel:
    def interpret(self, spec, utterance):
        raise AssertionError(f"the model was called for {utterance!r}")


def test_a_shaft_by_hungarian_numbers_needs_no_model(tmp_path):
    client = TestClient(create_app(auth=False, data_dir=tmp_path, interpreter=NoModel(), drive=None))
    sid = client.post("/session").json()["id"]

    def say(text):
        return client.post(f"/session/{sid}/utterance", json={"text": text}).json()

    for text in ("harminc", "negyven", "huszonöt", "hatvan", "ötven"):
        st = say(text)
    assert st["guide"]["diameter"] == 50
    st = say("nem")
    assert st["undone"] and st["guide"]["diameter"] is None
    st = say("húsz")
    st = say("harminc")
    assert [(s["diameter"], s["length"]) for s in st["spec"]["segments"]] == [(30, 40), (25, 60), (20, 30)]


def test_a_hungarian_sentence_goes_to_the_model(tmp_path):
    class Model:
        seen = []

        def interpret(self, spec, utterance):
            self.seen.append(utterance)
            return InterpreterResult.model_validate({"ops": [{"op": "add_segment", "diameter": 30, "length": 40}]})

    model = Model()
    client = TestClient(create_app(auth=False, data_dir=tmp_path, interpreter=model, drive=None))
    sid = client.post("/session").json()["id"]
    client.post(f"/session/{sid}/utterance", json={"text": "átmérő harminc, hossz negyven"})
    assert model.seen == ["átmérő harminc, hossz negyven"]


def test_the_prompt_knows_hungarian_words():
    for word in ("Hungarian", "átmérő", "letörés", "lekerekítés", "beszúrás", "reteszhorony", "kész"):
        assert word in SYSTEM_PROMPT


# ── speech settings ──────────────────────────────────────────────────────────
def test_the_default_model_follows_the_language(monkeypatch):
    monkeypatch.delenv("STT_MODEL", raising=False)
    monkeypatch.delenv("STT_LANGUAGE", raising=False)
    assert FasterWhisperStt().model_name == "base.en"
    monkeypatch.setenv("STT_LANGUAGE", "hu")
    stt = FasterWhisperStt()
    assert (stt.language, stt.model_name) == ("hu", "small")
    assert "Átmérő" in DOMAIN_PROMPTS["hu"] and "Diameter" in DOMAIN_PROMPTS["en"]


def test_an_english_only_model_cannot_do_hungarian(monkeypatch):
    monkeypatch.setenv("STT_MODEL", "base.en")
    monkeypatch.setenv("STT_LANGUAGE", "hu")
    with pytest.raises(SttError, match="English only"):
        FasterWhisperStt()._load()


def test_the_hungarian_prompt_is_passed_to_the_recogniser(monkeypatch):
    import numpy as np

    class FakeModel:
        def transcribe(self, audio, **kw):
            self.kw = kw
            return iter([]), None

    stt = FasterWhisperStt(model="small", language="hu")
    stt._model = FakeModel()
    stt.transcribe(np.zeros(16000, dtype="<i2").tobytes())
    assert stt._model.kw["language"] == "hu" and stt._model.kw["initial_prompt"] == DOMAIN_PROMPTS["hu"]
