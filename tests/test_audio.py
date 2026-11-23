"""Voice path: WAV in -> STT -> the same flow as typed text. Audio is never stored."""

import io
import wave

import pytest
from fastapi.testclient import TestClient

from server.ai.stt import AudioError, SttError, pcm_to_wav, wav_to_pcm
from server.core.ops import InterpreterResult
from server.main import create_app

ONE_SECOND = b"\x01\x00" * 16000


class FakeStt:
    def __init__(self, text="diameter thirty, forty long"):
        self.text = text
        self.got = None

    def transcribe(self, pcm):
        self.got = pcm
        if self.text == "BROKEN":
            raise SttError("recogniser is down")
        return self.text


class FakeInterpreter:
    def interpret(self, spec, utterance):
        assert utterance == "diameter thirty, forty long"
        return InterpreterResult.model_validate({"ops": [{"op": "add_segment", "diameter": 30, "length": 40}], "ask": None})


def make(tmp_path, stt):
    client = TestClient(create_app(auth=False, data_dir=tmp_path, interpreter=FakeInterpreter(), stt=stt))
    return client, client.post("/session").json()["id"]


def post_wav(client, sid, body):
    return client.post(f"/session/{sid}/audio", content=body, headers={"Content-Type": "audio/wav"})


def test_wav_round_trip():
    assert wav_to_pcm(pcm_to_wav(ONE_SECOND)) == ONE_SECOND


def test_wav_checks():
    with pytest.raises(AudioError, match="Not a WAV"):
        wav_to_pcm(b"hello, this is not audio")
    with pytest.raises(AudioError, match="too short"):
        wav_to_pcm(pcm_to_wav(b"\x00\x00" * 100))
    with pytest.raises(AudioError, match="longer than"):
        wav_to_pcm(pcm_to_wav(b"\x00\x00" * 16000 * 31))
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\x00" * 44100 * 4)
    with pytest.raises(AudioError, match="16 kHz"):
        wav_to_pcm(buf.getvalue())


def test_audio_goes_through_stt_and_the_interpreter(tmp_path):
    stt = FakeStt()
    client, sid = make(tmp_path, stt)
    r = post_wav(client, sid, pcm_to_wav(ONE_SECOND))
    assert r.status_code == 200, r.text
    st = r.json()
    assert stt.got == ONE_SECOND
    assert st["heard"] == "diameter thirty, forty long"
    assert st["readback"] == "1 step  Ø30×40  L40"
    assert st["timing_ms"]["audio_s"] == 1.0 and "stt" in st["timing_ms"] and "interpret" in st["timing_ms"]


def test_silence_asks_and_changes_nothing(tmp_path):
    client, sid = make(tmp_path, FakeStt(text="  "))
    st = post_wav(client, sid, pcm_to_wav(ONE_SECOND)).json()
    assert st["ask"] == "I did not hear anything" and st["spec"]["segments"] == []


def test_bad_audio_is_a_400(tmp_path):
    client, sid = make(tmp_path, FakeStt())
    assert post_wav(client, sid, b"not audio").status_code == 400
    assert post_wav(client, sid, b"").status_code == 400


def test_too_long_audio_is_refused(tmp_path):
    client, sid = make(tmp_path, FakeStt())
    assert post_wav(client, sid, pcm_to_wav(b"\x00\x00" * 16000 * 40)).status_code in (400, 413)


def test_stt_failure_is_a_503(tmp_path):
    client, sid = make(tmp_path, FakeStt(text="BROKEN"))
    assert post_wav(client, sid, pcm_to_wav(ONE_SECOND)).status_code == 503


def test_audio_is_never_written_to_disk(tmp_path):
    client, sid = make(tmp_path, FakeStt())
    marker = b"\x39\x30" * 16000  # a pattern we can search for
    post_wav(client, sid, pcm_to_wav(marker))
    files = [p for p in tmp_path.rglob("*") if p.is_file()]
    assert [p.name for p in files] == [f"{sid}.json"]
    assert marker[:64] not in files[0].read_bytes()


def test_unknown_session_is_404(tmp_path):
    client, _ = make(tmp_path, FakeStt())
    assert post_wav(client, "s_20261123_ffffff", pcm_to_wav(ONE_SECOND)).status_code == 404
