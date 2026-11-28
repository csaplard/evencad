"""Record one real session for the demo video.

Run from the repo root:  python -m tools.demo_record

It starts the real server (Whisper, Claude, CadQuery, Google Drive from `.env`) on port 8010 and
sends the spoken lines of `demo/audio/c*.wav` to `/session/{id}/audio`, one by one. Nothing is faked:
every text, drawing and file in `demo/run/` is what the server answered. The lines are spoken by a
computer voice (text to speech), not by a person. `tools/demo_video.py` builds the video from the result.
Needs one extra package to read the mp3 files:  pip install imageio-ffmpeg
Each run uploads two revisions to the Google Drive folder of `.env`, if Drive is set up.
"""

import json
import subprocess
import threading
import time
import wave
from pathlib import Path

import httpx
import uvicorn

from server.ai.stt import pcm_to_wav
from server.main import create_app

ROOT = Path(__file__).resolve().parent.parent
AUDIO = ROOT / "demo" / "audio"
OUT = ROOT / "demo" / "run"
PORT = 8010
BASE = f"http://127.0.0.1:{PORT}"
EDGE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")

# (kind, argument). "say" sends a spoken line. The texts are only labels: the server hears the audio.
STEPS = [
    ("say", "c01", "Thirty."),
    ("say", "c02", "Forty."),
    ("say", "c03", "Twenty five."),
    ("say", "c04", "Sixty."),
    ("say", "c05", "Fifty."),
    ("say", "c06", "No."),
    ("say", "c07", "Twenty."),
    ("say", "c01", "Thirty."),
    ("say", "c08", "Chamfer one by forty five on the right end."),
    ("say", "c09", "Keyway on the second one, twenty long."),
    ("say", "c10", "The second one has an h six fit, roughness one point six."),
    ("say", "c11", "Material C forty five."),
    ("view", "30", ""),
    ("view", "60", ""),
    ("say", "c12", "Add a segment, diameter ninety, ten long."),
    ("say", "c13", "Undo."),
    ("say", "c14", "Finish."),
    ("drive", "", ""),
    ("files", "A", ""),
    ("approve", "Daniel C.", ""),
    ("files", "A-approved", ""),
    ("say", "c15", "Make the first one thirty two."),
    ("say", "c14", "Finish."),
    ("drive", "", ""),
    ("files", "B", ""),
]


def padded_wav(name: str) -> bytes:
    """The spoken line with 0.4 s of silence before and after it, as the app would send it."""
    wav = AUDIO / "16k" / f"{name}.wav"  # made from the mp3 on first use, not in git
    if not wav.exists():
        import imageio_ffmpeg

        wav.parent.mkdir(exist_ok=True)
        subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-i", str(AUDIO / f"{name}.mp3"),
                        "-ac", "1", "-ar", "16000", "-sample_fmt", "s16", str(wav)], check=True)
    with wave.open(str(wav), "rb") as w:
        assert (w.getnchannels(), w.getsampwidth(), w.getframerate()) == (1, 2, 16000)
        pcm = w.readframes(w.getnframes())
    quiet = b"\x00\x00" * int(16000 * 0.4)
    return pcm_to_wav(quiet + pcm + quiet)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*"):
        if old.is_file():
            old.unlink()
    data = OUT / "data"
    if data.exists():
        import shutil

        shutil.rmtree(data)
    app = create_app(auth=False, data_dir=data)
    # The speech model is the default of the code (.env.example), whatever the local .env says.
    import os

    os.environ["STT_MODEL"] = "base.en"
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=PORT, log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start()
    client = httpx.Client(base_url=BASE, timeout=120)
    for _ in range(100):
        try:
            client.get("/health")
            break
        except httpx.HTTPError:
            time.sleep(0.2)

    sid = client.post("/session").json()["id"]
    state = client.get(f"/session/{sid}/spec").json()
    log = [{"n": 0, "kind": "start", "state": state}]
    (OUT / "s00.png").write_bytes(client.get(f"/session/{sid}/render").content)
    # One call that is not in the video, so the speech model and the packages are loaded (as after the warm-up).
    warm = client.post("/session").json()["id"]
    for line in ("c02", "c02", "c09"):  # diameter, length, then one sentence for the model
        client.post(f"/session/{warm}/audio", content=padded_wav(line), headers={"Content-Type": "audio/wav"})

    for n, (kind, arg, label) in enumerate(STEPS, start=1):
        entry = {"n": n, "kind": kind, "arg": arg, "label": label}
        t0 = time.perf_counter()
        if kind == "say":
            r = client.post(f"/session/{sid}/audio", content=padded_wav(arg), headers={"Content-Type": "audio/wav"})
            r.raise_for_status()
            state = r.json()
            (OUT / f"s{n:02d}.png").write_bytes(client.get(f"/session/{sid}/render").content)
        elif kind == "view":
            (OUT / f"s{n:02d}.png").write_bytes(client.get(f"/session/{sid}/render", params={"view": arg}).content)
        elif kind == "drive":
            for _ in range(120):
                state = client.get(f"/session/{sid}/spec").json()
                if (state.get("drive") or {}).get("status") != "uploading":
                    break
                time.sleep(0.5)
        elif kind == "files":
            for file_kind, ext in (("pdf", "pdf"), ("dxf", "dxf"), ("step", "step")):
                (OUT / f"rev{arg}.{ext}").write_bytes(client.get(f"/session/{sid}/files/{file_kind}").content)
            time.sleep(4)  # the AI hints come in the background
            state = client.get(f"/session/{sid}/spec").json()
            (OUT / f"phone{arg}.html").write_text(client.get(f"/s/{sid}").text, encoding="utf-8")
            if EDGE.exists():
                subprocess.run([str(EDGE), "--headless=new", f"--user-data-dir={OUT / 'edge-profile'}", "--no-first-run", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=2",
                                "--window-size=560,820", f"--screenshot={OUT / f'phone{arg}.png'}", f"{BASE}/s/{sid}"],
                               check=False, timeout=90, capture_output=True)
                shot, size = OUT / f"phone{arg}.png", -1
                for _ in range(60):  # Edge may write the picture after it returns: wait until the file is there and whole
                    now = shot.stat().st_size if shot.exists() else -1
                    if now > 0 and now == size:
                        break
                    size = now
                    time.sleep(0.5)
        elif kind == "approve":
            r = client.post(f"/session/{sid}/approve", json={"name": arg})
            r.raise_for_status()
            state = r.json()
        entry["seconds"] = round(time.perf_counter() - t0, 2)
        entry["state"] = state
        log.append(entry)
        s = state
        print(f"{n:02d} {kind:7} {label[:34]:34} {entry['seconds']:5.2f}s heard={s.get('heard')!r} ask={s.get('ask')!r} err={s.get('error')!r}")
        print(f"     {s['readback']} | {(s.get('guide') or {}).get('text')} | fin={s['finished']} rev={s.get('revision')} drive={(s.get('drive') or {}).get('status')} confirm={s.get('needs_confirm')}")

    (OUT / "log.json").write_text(json.dumps(log, indent=1, ensure_ascii=False), encoding="utf-8")
    server.should_exit = True
    time.sleep(0.5)


if __name__ == "__main__":
    main()
