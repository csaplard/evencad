"""Speech to text (SAYCAD_SPEC.md, sections 4 and 6.7).

The glasses give PCM: 16 kHz, signed 16-bit little-endian, mono.
The app sends one utterance as a WAV file. Audio is handled in memory only.
It is never written to disk and never kept after the text is made.
"""

import io
import os
import wave
from typing import Optional, Protocol

SAMPLE_RATE = 16000
MAX_SECONDS = 30
MAX_WAV_BYTES = 44 + SAMPLE_RATE * 2 * MAX_SECONDS + 4096

# Domain words help the recogniser with short technical phrases. One text per language.
DOMAIN_PROMPTS = {
    "en": (
        "Shaft dimensions in millimetres. Diameter thirty, forty long. Diameter twenty-five, length sixty. "
        "Chamfer one by forty-five on the right end. Fillet, undercut, keyway. Step, segment, undo, finish, material C45."
    ),
    "hu": (
        "Tengely méretei milliméterben. Átmérő harminc, hossz negyven. Átmérő huszonöt, hossz hatvan. "
        "Letörés egyszer negyvenöt fok a jobb végén. Lekerekítés, beszúrás, reteszhorony, illesztés h6, "
        "érdesség. Szakasz, váll, vissza, kész, anyag C45."
    ),
}
DOMAIN_PROMPT = DOMAIN_PROMPTS["en"]


class AudioError(ValueError):
    """The upload is not a usable recording."""


class SttError(RuntimeError):
    """The speech recogniser failed or is not set up."""


class SttProvider(Protocol):
    def transcribe(self, pcm: bytes) -> str:
        """`pcm` is 16 kHz, 16-bit, mono. Returns the text ("" if nothing was heard)."""
        ...


def pcm_to_wav(pcm: bytes) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(pcm)
    return buf.getvalue()


def wav_to_pcm(data: bytes) -> bytes:
    """Check the WAV and return its samples. Only the glasses format is accepted."""
    if len(data) > MAX_WAV_BYTES:
        raise AudioError(f"Recording is longer than {MAX_SECONDS} seconds")
    try:
        with wave.open(io.BytesIO(data), "rb") as w:
            if (w.getnchannels(), w.getsampwidth(), w.getframerate()) != (1, 2, SAMPLE_RATE):
                raise AudioError("Audio must be 16 kHz, 16-bit, mono")
            pcm = w.readframes(w.getnframes())
    except (wave.Error, EOFError) as e:
        raise AudioError("Not a WAV file") from e
    if len(pcm) < SAMPLE_RATE * 2 * 0.2:
        raise AudioError("Recording is too short")
    return pcm


# A quiet microphone (a laptop microphone array gave peaks near 1 % of full scale) makes the speech check
# of the recogniser drop real speech. The recording is made louder first. Near silence stays as it is.
QUIET_PEAK = 0.25  # below this the recording is made louder
SILENT_PEAK = 0.002  # below this there is nothing to make louder
TARGET_PEAK = 0.5
MAX_GAIN = 40.0


def louder(audio):
    """`audio`: float samples in -1..1. Returns it louder if it is quiet, else the same array."""
    peak = float(abs(audio).max()) if len(audio) else 0.0
    if not SILENT_PEAK <= peak < QUIET_PEAK:
        return audio
    return audio * min(TARGET_PEAK / peak, MAX_GAIN)


class FasterWhisperStt:
    """Whisper on the server (CPU is enough for short phrases). The model loads on first use."""

    def __init__(self, model: Optional[str] = None, language: Optional[str] = None):
        self.language = (language or os.environ.get("STT_LANGUAGE") or "en").lower()
        # The ".en" models know English only. Other languages need a multilingual model.
        self.model_name = model or os.environ.get("STT_MODEL") or ("base.en" if self.language == "en" else "small")
        self._model = None

    def _load(self):
        if self._model is None:
            if self.language != "en" and self.model_name.endswith(".en"):
                raise SttError(f"STT_MODEL {self.model_name} is English only. Use small for STT_LANGUAGE={self.language}")
            try:
                from faster_whisper import WhisperModel

                self._model = WhisperModel(self.model_name, device="cpu", compute_type="int8")
            except Exception as e:  # missing package, no model download, ...
                raise SttError(f"Cannot load the Whisper model {self.model_name}: {e}") from e
        return self._model

    def transcribe(self, pcm: bytes) -> str:
        import numpy as np

        audio = louder(np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768.0)
        prompt = DOMAIN_PROMPTS.get(self.language)
        try:
            segments, _info = self._load().transcribe(
                audio,
                language=self.language,
                initial_prompt=prompt,
                beam_size=5,
                vad_filter=True,
                condition_on_previous_text=False,
                temperature=0.0,
            )
            return " ".join(s.text.strip() for s in segments).strip()
        except SttError:
            raise
        except Exception as e:
            raise SttError(f"Speech recognition failed: {e}") from e


def get_stt(kind: Optional[str] = None) -> SttProvider:
    kind = (kind or os.environ.get("STT_PROVIDER") or "faster-whisper").lower()
    if kind == "faster-whisper":
        return FasterWhisperStt()
    raise SttError(f"Unknown STT_PROVIDER value: {kind}")
