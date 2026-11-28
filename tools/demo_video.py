"""Build the demo video from the recorded session.

Run from the repo root, after `python -m tools.demo_record`:  python -m tools.demo_video
Needs one extra package for the video encoder:  pip install imageio-ffmpeg

Input:  demo/run/ (answers of the real server), demo/audio/ (spoken lines and narration, text to speech).
Output: demo/saycad-demo.mp4 (1920x1080, 30 fps).

What is real: every text, drawing, sheet and time on the display comes from `demo/run/log.json`.
What is made for the video: the frame around it, the waits (cut short, the real time is shown),
and the voices (a computer voice speaks the commands; a person would do it on the glasses).
"""

import json
import math
import subprocess
import wave
from pathlib import Path

import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
RUN = ROOT / "demo" / "run"
MP3 = ROOT / "demo" / "audio"
AUDIO = MP3 / "hq"  # made from the mp3 files on first use, not in git
OUT = ROOT / "demo" / "saycad-demo.mp4"
W, H, FPS, RATE = 1920, 1080, 30, 44100

BG = (9, 12, 11)
GREEN = (60, 255, 110)
DIM = (120, 140, 130)
WHITE = (236, 240, 238)
AMBER = (255, 190, 70)
FONTS = Path(r"C:\Windows\Fonts")


def font(size: int, name: str = "segoeui.ttf") -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / name), size)


F_DISPLAY = font(52)
F_SUB = font(40)
F_SMALL = font(26)
F_CHIP = font(30, "segoeuib.ttf")
F_SAY = font(54, "segoeuisl.ttf")
F_MONO = font(30, "consola.ttf")
F_BIG = font(84, "segoeuil.ttf")
F_TITLE = font(200, "segoeuib.ttf")
F_H2 = font(56, "segoeuisl.ttf")

NARRATION = {
    "n01": "A worn shaft in one hand. A caliper in the other. Oil on your fingers. You need a drawing of this part. And you cannot touch a screen.",
    "n02": "This is SayCAD, for Even Realities G2 glasses. You say the numbers. Your glasses draw the part.",
    "n03": "A bare number needs no AI. It answers the question on the display.",
    "n04": "Wrong number? Just say no.",
    "n05": "Full sentences go to Claude. It answers with a few typed operations. It never writes geometry.",
    "n06": "I gave only the length of the keyway. Width and depth come from the standard table in the code. Not from the AI.",
    "n07": "A swipe turns the part.",
    "n08": "Every change is checked by rules, in code. This flange breaks two of them. So: undo.",
    "n09": "Done. No screen touched. The files are on the phone and in Google Drive. A STEP model, a DXF, and a PDF drawing.",
    "n10": "Every drawing is a draft. The AI never approves. A person does. And any change makes it a draft again.",
    "n11": "Speech becomes text on our own server. Claude turns the text into operations. Code checks them. Code draws. Audio is never stored.",
    "n12": "SayCAD. From the part in your hand, to a drawing. Hands busy. Phone in the pocket.",
    "n13": "And this is the STEP file. A real 3D model, with the keyway, ready for any CAD program.",
}


# ── sound ────────────────────────────────────────────────────────────────────
def load_wav(name: str) -> np.ndarray:
    if not (AUDIO / f"{name}.wav").exists():
        AUDIO.mkdir(exist_ok=True)
        subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-i", str(MP3 / f"{name}.mp3"),
                        "-ac", "1", "-ar", str(RATE), "-sample_fmt", "s16", str(AUDIO / f"{name}.wav")], check=True)
    with wave.open(str(AUDIO / f"{name}.wav"), "rb") as w:
        assert (w.getnchannels(), w.getsampwidth(), w.getframerate()) == (1, 2, RATE), name
        return np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float32) / 32768.0


SOUNDS: dict[str, np.ndarray] = {}


def sound(name: str) -> np.ndarray:
    if name not in SOUNDS:
        a = load_wav(name)
        peak = float(np.abs(a).max()) or 1.0
        SOUNDS[name] = a * (0.8 / peak)
    return SOUNDS[name]


def seconds(name: str) -> float:
    return len(sound(name)) / RATE


def envelope(name: str, bars: int) -> list[float]:
    a = np.abs(sound(name))
    parts = np.array_split(a, bars)
    levels = np.array([float(p.mean()) if len(p) else 0.0 for p in parts])
    top = float(levels.max()) or 1.0
    return [float(v) / top for v in levels]


# ── drawing helpers ──────────────────────────────────────────────────────────
def wrap(draw: ImageDraw.ImageDraw, text: str, fnt, width: int) -> list[str]:
    lines = []
    for paragraph in text.split("\n"):
        line = ""
        for word in paragraph.split(" "):
            trial = f"{line} {word}".strip()
            if draw.textlength(trial, font=fnt) <= width or not line:
                line = trial
            else:
                lines.append(line)
                line = word
        lines.append(line)
    return lines


def base() -> Image.Image:
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    for x in range(0, W, 60):  # a faint grid, like drawing paper
        d.line([(x, 0), (x, H)], fill=(13, 18, 16))
    for y in range(0, H, 60):
        d.line([(0, y), (W, y)], fill=(13, 18, 16))
    return img


BASE = base()


def frame_plain(title: str) -> Image.Image:
    """A frame with no glasses display: for the files, the sheet and the diagram."""
    img = BASE.copy()
    d = ImageDraw.Draw(img)
    d.text((60, 28), "SayCAD", font=F_CHIP, fill=GREEN)
    d.text((190, 30), title, font=F_SMALL, fill=DIM)
    return img


def frame_live(title: str) -> Image.Image:
    img = BASE.copy()
    glow = Image.new("RGB", (DW + 80, DH + 80), BG)
    ImageDraw.Draw(glow).rounded_rectangle([30, 30, DW + 50, DH + 50], radius=30, fill=(18, 60, 34))
    img.paste(glow.filter(ImageFilter.GaussianBlur(14)).crop((14, 14, DW + 66, DH + 66)), (DX - 26, DY - 26))
    d = ImageDraw.Draw(img)
    d.text((60, 28), "SayCAD", font=F_CHIP, fill=GREEN)
    d.text((190, 30), title, font=F_SMALL, fill=DIM)
    d.text((W - 60, 30), "what the glasses show", font=F_SMALL, fill=DIM, anchor="ra")
    return img


# The glasses display is 576 x 288. It is drawn 2.5 times larger.
SCALE = 2.5
DX, DY = (W - int(576 * SCALE)) // 2, 96
DW, DH = int(576 * SCALE), int(288 * SCALE)


def glasses(status: str, band: Image.Image | None, info: str) -> Image.Image:
    """The display as the app lays it out: status line, drawing band, info lines."""
    panel = Image.new("RGB", (DW, DH), (0, 0, 0))
    d = ImageDraw.Draw(panel)
    d.text((14, 6), status, font=F_DISPLAY, fill=GREEN)
    if band is not None:
        big = band.convert("L").resize((576 * 5, 144 * 5), Image.NEAREST).resize((DW, int(144 * SCALE)), Image.LANCZOS)
        green = Image.merge("RGB", [big.point(lambda v, c=c: v * c // 255) for c in GREEN])
        panel.paste(green, (0, int(48 * SCALE)))
    y = int(196 * SCALE) + 4
    for line in wrap(d, info, F_DISPLAY, DW - 28)[:3]:
        d.text((14, y), line, font=F_DISPLAY, fill=GREEN)
        y += 68
    return panel


def put_glasses(img: Image.Image, panel: Image.Image) -> None:
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([DX - 14, DY - 14, DX + DW + 14, DY + DH + 14], radius=22, fill=(0, 0, 0), outline=(40, 110, 64), width=3)
    img.paste(panel, (DX, DY))


LOW_Y = DY + DH + 34  # the strip under the display


def strip_say(img: Image.Image, name: str, text: str, progress: float) -> None:
    """The spoken command: label, moving sound bars, the words."""
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([DX, LOW_Y, DX + 190, LOW_Y + 58], radius=29, fill=(20, 70, 40))
    d.text((DX + 95, LOW_Y + 29), "YOU SAY", font=F_CHIP, fill=GREEN, anchor="mm")
    bars = envelope(name, 46)
    x0 = DX + 220
    for i, level in enumerate(bars):
        h = 6 + int(46 * level)
        played = (i + 0.5) / len(bars) <= progress
        d.rounded_rectangle([x0 + i * 9, LOW_Y + 29 - h // 2, x0 + i * 9 + 5, LOW_Y + 29 + h // 2], radius=2, fill=GREEN if played else (40, 80, 56))
    tx = x0 + 46 * 9 + 34
    d.text((tx, LOW_Y + 26), f"“{text}”", font=fit(d, f"“{text}”", DX + DW - tx), fill=WHITE, anchor="lm")


def fit(d: ImageDraw.ImageDraw, text: str, width: int, size: int = 54, name: str = "segoeuisl.ttf"):
    """The largest font, up to `size`, with which the text fits the width."""
    while size > 22 and d.textlength(text, font=font(size, name)) > width:
        size -= 2
    return font(size, name)


def strip_result(img: Image.Image, text: str, timing: str, ops: str) -> None:
    d = ImageDraw.Draw(img)
    d.text((DX, LOW_Y + 10), "HEARD", font=font(22, "segoeuib.ttf"), fill=DIM, anchor="la")
    d.text((DX + 96, LOW_Y + 22), f"“{text}”", font=fit(d, f"“{text}”", 760, 44), fill=(170, 184, 177), anchor="lm")
    d.text((DX + DW, LOW_Y + 10), timing, font=F_SMALL, fill=AMBER, anchor="ra")
    if ops:
        d.text((DX, LOW_Y + 66), "CLAUDE ANSWERED", font=font(22, "segoeuib.ttf"), fill=DIM, anchor="la")
        d.text((DX + 250, LOW_Y + 78), ops, font=fit(d, ops, DW - 250, 30, "consola.ttf"), fill=GREEN, anchor="lm")


def strip_sub(img: Image.Image, text: str) -> None:
    """One sentence of the narration."""
    d = ImageDraw.Draw(img)
    lines = wrap(d, text, F_SUB, DW)
    y = LOW_Y + 44 - (len(lines) - 1) * 26
    for line in lines:
        d.text((W // 2, y), line, font=F_SUB, fill=WHITE, anchor="mm")
        y += 52


def sentences(name: str) -> list[tuple[float, float, str]]:
    """(start, end, text) of each sentence, timed by its share of the letters."""
    text = NARRATION[name]
    parts, piece = [], ""
    for ch in text:
        piece += ch
        if ch in ".?!":
            parts.append(piece.strip())
            piece = ""
    if piece.strip():
        parts.append(piece.strip())
    # Short sentences are shown in pairs, so the line does not flicker.
    merged: list[str] = []
    for p in parts:
        if merged and len(merged[-1]) + len(p) < 62:
            merged[-1] = f"{merged[-1]} {p}"
        else:
            merged.append(p)
    total, at, out = sum(len(p) for p in merged), 0.0, []
    for p in merged:
        share = len(p) / total * seconds(name)
        out.append((at, at + share, p))
        at += share
    return out


def sub_at(name: str, t: float) -> str:
    for start, end, text in sentences(name):
        if start <= t < end:
            return text
    return sentences(name)[-1][2]


# ── timeline ─────────────────────────────────────────────────────────────────
class Timeline:
    def __init__(self):
        self.parts: list[tuple[float, object, bool]] = []  # (duration, draw(t) -> Image, fade in)
        self.clips: list[tuple[float, str, float]] = []  # (start, sound name, volume)
        self.now = 0.0

    def add(self, duration: float, draw, fade: bool = False, play: str | None = None, volume: float = 1.0) -> None:
        if play:
            self.clips.append((self.now, play, volume))
        self.parts.append((duration, draw, fade))
        self.now += duration


def still(img: Image.Image):
    return lambda t: img


def build() -> Timeline:
    log = json.loads((RUN / "log.json").read_text(encoding="utf-8"))
    sid = log[0]["state"]["id"]
    session = json.loads((RUN / "data" / "sessions" / f"{sid}.json").read_text(encoding="utf-8"))
    applied = [e for e in session["log"] if e["event"] == "applied" and e.get("source") != "guide"]
    ops_of = {e["utterance"]: e["ops"] for e in applied}
    tl = Timeline()

    # ── 1. the problem ──
    hook = ["A worn shaft in one hand.", "A caliper in the other.", "Oil on your fingers.", "You need a drawing of this part.", "And you cannot touch a screen."]
    starts = [s for s, _, _ in [(0, 0, 0)]]
    d1 = seconds("n01")
    total = sum(len(x) for x in hook)
    starts, at = [], 0.0
    for line in hook:
        starts.append(at)
        at += len(line) / total * d1

    def draw_hook(t: float) -> Image.Image:
        img = BASE.copy()
        d = ImageDraw.Draw(img)
        y = 250
        for line, start in zip(hook, starts):
            if t >= start:
                k = min(1.0, (t - start) / 0.4)
                last = line == hook[-1]
                color = tuple(int(BG[i] + ((GREEN if last else WHITE)[i] - BG[i]) * k) for i in range(3))
                d.text((230, y), line, font=F_BIG, fill=color)
            y += 124
        d.line([(170, 250), (170, 250 + int(600 * min(1.0, t / d1)))], fill=GREEN, width=6)
        return img

    tl.add(0.5, still(BASE))
    tl.add(d1 + 0.6, draw_hook, play="n01")

    # ── 2. the title ──
    final_band = Image.open(RUN / "s12.png")

    def draw_title(t: float) -> Image.Image:
        img = BASE.copy()
        d = ImageDraw.Draw(img)
        d.text((W // 2, 300), "SayCAD", font=F_TITLE, fill=GREEN, anchor="mm")
        d.text((W // 2, 450), "Voice to engineering drawing, for Even Realities G2", font=F_H2, fill=WHITE, anchor="mm")
        if t > 3.3:
            k = min(1.0, (t - 3.3) / 0.6)
            big = final_band.convert("L").resize((1440, 360), Image.LANCZOS).point(lambda v: int(v * k))
            green = Image.merge("RGB", [big.point(lambda v, c=c: v * c // 255) for c in GREEN])
            img.paste(green, (240, 560))
            d.text((W // 2, 980), "You say the numbers. Your glasses draw the part.", font=F_H2, fill=WHITE, anchor="mm")
        return img

    tl.add(seconds("n02") + 0.7, draw_title, fade=True, play="n02")

    # ── 3. the live session ──
    def info_of(state: dict) -> str:
        """The same lines as show() in app/src/main.ts."""
        empty = not state["spec"]["segments"]
        lines = [] if empty else [state["readback"]]
        v = state["validation"]
        problem = None if empty else (v["errors"] or v["warnings"] or [None])[0]
        if problem:
            lines.append(f"{'Error' if v['errors'] else 'Warning'}: {problem['text']}")
        if state.get("needs_confirm"):
            lines.append("Tap to accept the warning and finish")
        elif state["finished"]:
            drive = (state.get("drive") or {}).get("status")
            saved = {"ok": " · saved to Drive", "error": " · Drive failed", "uploading": " · saving to Drive…"}.get(drive, "")
            lines.append(f"DRAFT rev {state.get('revision') or '-'} ready{saved} · code {state['id'][-6:]}")
        elif state.get("guide"):
            lines.append(f"Tap and say a number. {state['guide']['text']}" if empty else state["guide"]["text"])
        return "\n".join(lines)

    def status_of(state: dict) -> str:
        heard = state.get("heard")
        short = f"{heard[:43]}…" if heard and len(heard) > 44 else heard
        status = f"“{short}”" if short else "SayCAD · ready"
        if state.get("undone"):
            status = "Undone"
        if state.get("ask"):
            status = f"? {state['ask']}"
        elif state.get("error"):
            status = f"! {state['error']}"
        return status

    def band_of(n: int) -> Image.Image:
        while not (RUN / f"s{n:02d}.png").exists():
            n -= 1
        return Image.open(RUN / f"s{n:02d}.png")

    shown = {"n": 0, "state": log[0]["state"], "title": "1 · Measure and say"}

    def current(status: str | None = None, band: Image.Image | None = None) -> Image.Image:
        img = frame_live(shown["title"])
        state = shown["state"]
        put_glasses(img, glasses(status or status_of(state), band or band_of(shown["n"]), info_of(state)))
        return img

    def narrate(name: str, extra: float = 0.3, band: Image.Image | None = None, status: str | None = None) -> None:
        img = current(status=status, band=band)

        def draw(t: float) -> Image.Image:
            out = img.copy()
            strip_sub(out, sub_at(name, t))
            return out

        tl.add(seconds(name) + extra, draw, play=name)

    def say(n: int, hold: float = 1.3) -> None:
        entry = log[n]
        name, label, state = entry["arg"], entry["label"], entry["state"]
        before = shown["state"]
        guide = before.get("guide")
        listening = f"Listening… segment {guide['segment']} {guide['field']}?" if guide else "Listening… tap to stop"
        img_listen = current(status=listening)
        d = seconds(name)

        def draw_listen(t: float) -> Image.Image:
            out = img_listen.copy()
            strip_say(out, name, label, min(1.0, t / d))
            return out

        tl.add(d + 0.35, draw_listen, play=name, volume=0.9)

        img_think = current(status="Thinking…")
        strip_say(img_think, name, label, 1.0)
        tl.add(0.7, still(img_think))

        shown["n"], shown["state"] = n, state
        timing = state["timing_ms"]
        ai = f"Claude {timing['interpret'] / 1000:.1f} s" if timing["interpret"] else "no AI call"
        ops = ops_of.get(state.get("heard") or "", [])
        ops_text = "  ".join(json.dumps(op, separators=(",", ":")).replace(".0,", ",").replace(".0}", "}") for op in ops)
        img_done = current()
        strip_result(img_done, state.get("heard") or label, f"speech to text {timing['stt'] / 1000:.1f} s · {ai} · total {entry['seconds']:.1f} s", ops_text)
        tl.add(hold, still(img_done))

    tl.add(1.2, still(current()), fade=True)
    say(1)
    say(2)
    narrate("n03")
    say(3, hold=0.9)
    say(4)
    say(5, hold=0.9)
    narrate("n04", extra=0.1)
    say(6, hold=1.0)
    say(7, hold=0.8)
    say(8, hold=1.6)

    shown["title"] = "2 · Full sentences"
    narrate("n05")
    say(9, hold=1.8)
    say(10, hold=1.0)
    narrate("n06")
    say(11, hold=2.2)
    say(12, hold=1.8)

    shown["title"] = "3 · Look at it"
    view30, view60 = Image.open(RUN / "s13.png"), Image.open(RUN / "s14.png")
    narrate("n07", extra=0.2, band=view30)
    tl.add(1.6, still(current(band=view60)))
    tl.add(1.0, still(current(band=view30)))
    tl.add(0.8, still(current()))

    shown["title"] = "4 · Rules, not trust"
    say(15, hold=1.2)
    narrate("n08")
    say(16, hold=1.2)
    say(17, hold=1.6)
    shown["n"], shown["state"] = 17, log[18]["state"]
    done = current(status="“Finish.”")
    tl.add(2.2, still(done))

    # ── 4. the files ──
    phone = Image.open(RUN / "phoneA.png").convert("RGB")
    phone = phone.crop((0, 0, phone.width, min(phone.height, 1540)))  # cut above the name field
    phone = phone.resize((int(phone.width * 820 / phone.height), 820), Image.LANCZOS)
    sheet_a = Image.open(RUN / "revA.png").convert("RGB")
    sheet_ok = Image.open(RUN / "revA-approved.png").convert("RGB")
    sheet_b = Image.open(RUN / "revB.png").convert("RGB")
    drive = log[18]["state"]["drive"]

    def files_frame(sheet: Image.Image, caption: str, sub: str) -> Image.Image:
        img = frame_plain("5 · The files")
        d = ImageDraw.Draw(img)
        px, py = 110, 110
        d.rounded_rectangle([px - 16, py - 16, px + phone.width + 16, py + phone.height + 16], radius=34, fill=(30, 34, 32), outline=(70, 80, 75), width=3)
        img.paste(phone, (px, py))
        sw = W - (px + phone.width + 90) - 80
        s = sheet.resize((sw, int(sheet.height * sw / sheet.width)), Image.LANCZOS)
        sx = px + phone.width + 90
        d.rectangle([sx - 4, py - 4, sx + s.width + 4, py + s.height + 4], fill=(70, 80, 75))
        img.paste(s, (sx, py))
        d.text((sx, py + s.height + 34), caption, font=F_CHIP, fill=GREEN)
        d.text((sx, py + s.height + 80), f"Google Drive: {', '.join(k.upper() for k in sorted(drive['files']))} uploaded", font=F_SMALL, fill=DIM)
        strip_sub_at(img, sub, 990)
        return img

    def strip_sub_at(img: Image.Image, text: str, y: int) -> None:
        ImageDraw.Draw(img).text((W // 2, y), text, font=F_SUB, fill=WHITE, anchor="mm")

    def draw_files(t: float) -> Image.Image:
        return files_frame(sheet_a, "PDF sheet · DRAFT rev A · made by code from the checked operations", sub_at("n09", t))

    tl.add(seconds("n09") + 0.5, draw_files, fade=True, play="n09")

    # ── 4b. the STEP file as a turning 3D model (pictures from tools/demo_model3d.py) ──
    model = sorted((RUN / "model").glob("m*.png"))
    if model:
        d13 = seconds("n13")
        hold = d13 + 1.6
        cache: dict[int, Image.Image] = {}

        def draw_model(t: float) -> Image.Image:
            i = min(len(model) - 1, int(t / hold * len(model)))
            if i not in cache:
                cache.clear()
                img = Image.open(model[i]).convert("RGB")
                d = ImageDraw.Draw(img)
                d.text((60, 28), "SayCAD", font=F_CHIP, fill=GREEN)
                d.text((190, 30), "5 · The STEP file", font=F_SMALL, fill=DIM)
                d.text((W - 60, 30), "revA.step, as the server wrote it", font=F_SMALL, fill=DIM, anchor="ra")
                d.text((W // 2, 150), "A solid 3D model, not a picture", font=F_BIG, fill=WHITE, anchor="mm")
                cache[i] = img
            out = cache[i].copy()
            strip_sub_at(out, sub_at("n13", min(t, d13 - 0.01)), 970)
            return out

        tl.add(hold, draw_model, fade=True, play="n13")

    # ── 5. draft, approval, draft again ──
    def title_block(sheet: Image.Image) -> Image.Image:
        w, h = sheet.size
        return sheet.crop((0, int(h * 0.69), w, h))

    def approval_frame(sheet: Image.Image, label: str, color, sub: str) -> Image.Image:
        img = frame_plain("6 · A person approves")
        d = ImageDraw.Draw(img)
        block = title_block(sheet)
        bw = W - 240
        block = block.resize((bw, int(block.height * bw / block.width)), Image.LANCZOS)
        d.rectangle([116, 236, 124 + bw, 244 + block.height], fill=(70, 80, 75))
        img.paste(block, (120, 240))
        d.text((120, 150), label, font=F_H2, fill=color)
        strip_sub_at(img, sub, 960)
        return img

    d10 = seconds("n10")

    def draw_approval(t: float) -> Image.Image:
        sub = sub_at("n10", t)
        if t < d10 * 0.42:
            return approval_frame(sheet_a, "Title block of the sheet: DRAFT, rev A", AMBER, sub)
        return approval_frame(sheet_ok, "After a person typed a name on the phone page", GREEN, sub)

    tl.add(d10 + 0.5, draw_approval, fade=True, play="n10")

    shown["title"] = "7 · Any change is a draft again"
    shown["n"], shown["state"] = 17, log[21]["state"]
    tl.add(0.8, still(current(status="SayCAD · ready")), fade=True)
    say(22, hold=1.6)
    say(23, hold=1.0)
    shown["n"], shown["state"] = 23, log[24]["state"]
    tl.add(1.6, still(current(status="“Finish.”")))
    tl.add(2.0, still(approval_frame(sheet_b, "The new sheet: DRAFT again, rev B, diameter 32", AMBER, "")))

    # ── 6. how it works ──
    boxes = [
        ("Speech", "one sentence, 16 kHz", 0.0),
        ("Whisper", "on our own server", 0.0),
        ("Claude", "text to typed operations", 0.22),
        ("Rules", "code checks each one", 0.47),
        ("CAD code", "drawing, STEP, DXF, PDF", 0.60),
    ]
    d11 = seconds("n11")
    example = ops_of.get("Keyway on the second one, twenty long.", [])
    example_text = json.dumps(example[0], separators=(", ", ": ")).replace("20.0", "20") if example else ""

    def draw_how(t: float) -> Image.Image:
        img = frame_plain("How it works")
        d = ImageDraw.Draw(img)
        d.text((W // 2, 160), "The AI never writes geometry", font=F_BIG, fill=WHITE, anchor="mm")
        bw, gap, y = 330, 34, 320
        x = (W - (len(boxes) * bw + (len(boxes) - 1) * gap)) // 2
        for i, (name, note, when) in enumerate(boxes):
            on = t >= when * d11
            color = GREEN if on else (50, 70, 60)
            d.rounded_rectangle([x, y, x + bw, y + 190], radius=22, outline=color, width=4, fill=(12, 26, 18) if on else BG)
            d.text((x + bw // 2, y + 70), name, font=F_H2, fill=color, anchor="mm")
            d.text((x + bw // 2, y + 136), note, font=font(24), fill=WHITE if on else (70, 84, 78), anchor="mm")
            if i < len(boxes) - 1:
                d.text((x + bw + gap // 2, y + 95), "›", font=F_H2, fill=color, anchor="mm")
            x += bw + gap
        if t >= 0.22 * d11:
            d.text((W // 2, 610), "“Keyway on the second one, twenty long.”", font=F_SAY, fill=WHITE, anchor="mm")
            d.text((W // 2, 690), example_text, font=font(40, "consola.ttf"), fill=GREEN, anchor="mm")
        if t >= 0.47 * d11:
            d.text((W // 2, 770), "width 8 and depth 4 come from the DIN 6885 table in the code", font=F_SMALL, fill=DIM, anchor="mm")
        if t >= 0.82 * d11:
            d.text((W // 2, 850), "Audio is never stored · keys stay on the server · every sheet is a DRAFT until a person approves", font=F_SMALL, fill=AMBER, anchor="mm")
        strip_sub_at(img, sub_at("n11", t), 970)
        return img

    tl.add(d11 + 0.6, draw_how, fade=True, play="n11")

    # ── 7. the end ──
    def draw_end(t: float) -> Image.Image:
        img = BASE.copy()
        d = ImageDraw.Draw(img)
        d.text((W // 2, 250), "SayCAD", font=F_TITLE, fill=GREEN, anchor="mm")
        d.text((W // 2, 410), "From the part in your hand to a drawing.", font=F_H2, fill=WHITE, anchor="mm")
        big = Image.open(RUN / "s23.png").convert("L").resize((1440, 360), Image.LANCZOS)
        img.paste(Image.merge("RGB", [big.point(lambda v, c=c: v * c // 255) for c in GREEN]), (240, 480))
        d.text((W // 2, 890), "Hands busy. Phone in the pocket.", font=F_H2, fill=WHITE, anchor="mm")
        d.text((W // 2, 965), "github.com/csaplard/saycad  ·  Even Realities hackathon, track 04: AI Assistants & Work", font=F_SMALL, fill=DIM, anchor="mm")
        d.text((W // 2, 1020), "Recorded from a real run of the SayCAD server. Voice: AI voice of the author.", font=font(22), fill=(110, 126, 118), anchor="mm")
        return img

    tl.add(seconds("n12") + 2.0, draw_end, fade=True, play="n12")
    return tl


# ── output ───────────────────────────────────────────────────────────────────
def render(tl: Timeline) -> None:
    total = tl.now
    track = np.zeros(int(total * RATE) + RATE, dtype=np.float32)
    for start, name, volume in tl.clips:
        a = sound(name) * volume
        at = int(start * RATE)
        track[at:at + len(a)] += a
    track = np.clip(track, -1.0, 1.0)
    wav_path = RUN / "track.wav"
    with wave.open(str(wav_path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes((track * 32767).astype("<i2").tobytes())

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [ffmpeg, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-i", str(wav_path), "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", str(OUT)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    black = Image.new("RGB", (W, H), (0, 0, 0))
    count = 0
    for duration, draw, fade in tl.parts:
        frames = max(1, round(duration * FPS))
        last_img, last_bytes = None, b""
        for i in range(frames):
            t = i / FPS
            img = draw(t)
            if fade and t < 0.35:
                data = Image.blend(black, img, t / 0.35).tobytes()
            elif img is last_img:
                data = last_bytes
            else:
                data = img.tobytes()
                last_img, last_bytes = img, data
            proc.stdin.write(data)
            count += 1
    proc.stdin.close()
    proc.wait()
    print(f"{OUT}  {count / FPS:.1f} s  ({math.floor(count / FPS / 60)}:{int(count / FPS) % 60:02d})")


def stills(tl: Timeline, times: list[float]) -> None:
    """Save single frames, to check the layout without building the video."""
    for want in times:
        at = 0.0
        for duration, draw, _ in tl.parts:
            if at <= want < at + duration:
                draw(want - at).save(RUN / f"check_{int(want):03d}.jpg", quality=88)
                break
            at += duration


if __name__ == "__main__":
    import sys

    timeline = build()
    if len(sys.argv) > 1:
        stills(timeline, [float(x) for x in sys.argv[1:]])
        print("length", round(timeline.now, 1))
    else:
        render(timeline)
