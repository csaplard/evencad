"""EvenCAD backend (FastAPI).

Run:  uvicorn server.main:app --reload --port 8000
"""

import hashlib
import secrets
import html
import json
import shutil
import io
import logging
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Union

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from server.ai.interpreter import Interpreter, InterpreterError, get_interpreter
from server.ai.stt import MAX_WAV_BYTES, AudioError, SttError, SttProvider, get_stt, wav_to_pcm
from server.core.mass import mass
from server.core.guide import is_rejection, next_step, parse_number
from server.core.ops import AddSegment, Finish, OpError, Undo, active_after, apply_ops
from server.core.readback import readback
from server.core.validation import validate
from server.drive import DriveError, DriveUploader, get_uploader
from server.draw.glasses import glasses_png, glasses_tiles
from server.draw.glasses3d import YAW_STEPS, glasses_3d_tiles, render_glasses_3d
from server.export import FILE_NAMES, export_all, rebuild_sheets
from server.sessions import SESSION_ID_PATTERN, Session, SessionStore, Turn, now_iso

log = logging.getLogger("evencad")

MEDIA = {"step": "model/step", "dxf": "image/vnd.dxf", "pdf": "application/pdf"}


class UtteranceIn(BaseModel):
    text: str = Field(min_length=1, max_length=500)


class FinishIn(BaseModel):
    confirm_warnings: bool = False


class ApproveIn(BaseModel):
    name: str = Field(min_length=2, max_length=60)


def revision_name(n: int) -> str:
    """1 -> A, 2 -> B, 26 -> Z, 27 -> AA."""
    name = ""
    while n > 0:
        n, rest = divmod(n - 1, 26)
        name = chr(ord("A") + rest) + name
    return name


def _fingerprint(spec) -> str:
    """Changes when the drawing content changes. The approval and the revision letter are left out."""
    content = spec.model_dump(mode="json", exclude={"status", "approved_by", "approved_at", "revision"})
    return hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()[:16]


def _load_env_file(path: Path = Path(".env")) -> None:
    """Tiny .env reader: KEY=value lines. Real environment variables win."""
    if os.environ.get("EVENCAD_SKIP_DOTENV") or not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


def _cors_origins() -> list[str]:
    raw = os.environ.get("CORS_ALLOW_ORIGINS", "*")
    return [o.strip() for o in raw.split(",") if o.strip()] or ["*"]


def create_app(
    data_dir: Optional[Path] = None,
    interpreter: Optional[Interpreter] = None,
    stt: Optional[SttProvider] = None,
    drive: Union[DriveUploader, None, str] = "auto",
    auth: bool = True,
) -> FastAPI:
    """`drive`: an uploader, None (off), or "auto" (set up from the environment on first use).

    `auth`: every call to a session needs the session token. Only tests turn it off.
    """
    _load_env_file()
    data_dir = Path(data_dir or os.environ.get("DATA_DIR", "data"))
    store = SessionStore(data_dir)
    holder = {"interpreter": interpreter, "stt": stt, "drive": drive}

    app = FastAPI(title="EvenCAD", version="0.2.0")

    session_path = re.compile(rf"/(?:session|s)/({SESSION_ID_PATTERN})(?:/|$)")

    @app.middleware("http")
    async def check_token(request: Request, call_next):
        """The session id is short and can be guessed. The token cannot.

        It comes in the X-Session-Token header (the glasses app) or as ?k= (links on the phone page).
        """
        found = session_path.match(request.url.path)
        if auth and found and request.method != "OPTIONS":
            session = store.get(found.group(1))
            given = request.headers.get("x-session-token") or request.query_params.get("k") or ""
            if session is not None and not (session.token and secrets.compare_digest(given, session.token)):
                return JSONResponse(status_code=401, content={"detail": "Session token is missing or wrong"})
        return await call_next(request)

    # The glasses app runs in a WebView. Its origin is not documented,
    # so the default is "*". We use no cookies and no credentials.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "X-Session-Token"],
        allow_credentials=False,
    )

    def load(sid: str) -> Session:
        session = store.get(sid)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")
        return session

    def the_interpreter() -> Interpreter:
        if holder["interpreter"] is None:
            holder["interpreter"] = get_interpreter()
        return holder["interpreter"]

    def the_stt() -> SttProvider:
        if holder["stt"] is None:
            holder["stt"] = get_stt()
        return holder["stt"]

    def upload_to_drive(session: Session, kinds: Optional[list[str]] = None) -> None:
        """Copy the output files to Google Drive. A Drive problem never blocks the drawing."""
        sid = session.spec.id
        t0 = time.perf_counter()
        try:
            if holder["drive"] == "auto":
                holder["drive"] = get_uploader()
            uploader = holder["drive"]
            if uploader is None:
                session.drive = None
                return
            paths = {k: store.out_dir(sid) / name for k, name in FILE_NAMES.items() if not kinds or k in kinds}
            result = uploader.upload(sid, paths)
            previous = (session.drive or {}).get("files", {}) if (session.drive or {}).get("status") == "ok" else {}
            session.drive = {"status": "ok", "folder_url": result["folder_url"], "files": {**previous, **result["files"]}, "at": now_iso()}
            session.record("drive_upload", files=sorted(result["files"]), ms=round((time.perf_counter() - t0) * 1000))
        except DriveError as e:
            holder["drive"] = "auto"  # try to set up again next time
            session.drive = {"status": "error", "message": str(e)}
            session.record("drive_error", message=str(e))
            log.warning("drive upload failed for %s: %s", sid, e)

    def active_of(session: Session) -> Optional[int]:
        """The marked segment, or None when it no longer exists."""
        n = session.active_segment
        return n if n and n <= len(session.spec.segments) else None

    def state(session: Session, **extra) -> dict:
        """The one answer shape for every session call."""
        spec = session.spec
        report = validate(spec)
        files = {}
        key = f"?k={session.token}" if auth and session.token else ""
        if session.finished:
            files = {kind: f"/session/{spec.id}/files/{kind}{key}" for kind in FILE_NAMES}
        return {
            "id": spec.id,
            "spec": spec.model_dump(mode="json"),
            "readback": readback(spec),
            "mass": mass(spec),
            "validation": report.model_dump(),
            "can_undo": bool(session.history) or session.pending_diameter is not None,
            "active_segment": active_of(session),
            "guide": None if session.finished else next_step(spec, session.pending_diameter),
            "finished": session.finished,
            "revision": spec.revision if session.finished else None,
            "files": files,
            "drive": session.drive if session.finished else None,
            "phone_page": f"/s/{spec.id}{key}",
            "views_3d": list(YAW_STEPS),
            "heard": None,
            "ask": None,
            "error": None,
            "needs_confirm": False,
            "undone": False,
            **extra,
        }

    def mark_changed(session: Session) -> None:
        """The drawing content changed: it is not finished, and an approval no longer holds."""
        session.finished = False
        spec = session.spec
        if spec.status != "draft" or spec.approved_by:
            session.record("approval_reset", was_approved_by=spec.approved_by, revision=spec.revision)
        spec.status, spec.approved_by, spec.approved_at = "draft", None, None

    def do_undo(session: Session) -> Optional[str]:
        if session.pending_diameter is not None:
            # A half-entered segment is undone first. The shaft itself does not change.
            session.record("undo", undone_pending_diameter=session.pending_diameter)
            session.pending_diameter = None
            return None
        if not session.history:
            return "Nothing to undo"
        turn = session.history.pop()
        session.spec = type(session.spec).model_validate(turn.before)
        session.active_segment = turn.active_before
        mark_changed(session)
        session.record("undo", undone=turn.ops)
        return None

    def archive(out: Path, revision: str) -> None:
        """Keep a copy of each revision in its own folder."""
        keep = out / f"rev_{revision}"
        keep.mkdir(parents=True, exist_ok=True)
        for name in FILE_NAMES.values():
            if (out / name).exists():
                shutil.copyfile(out / name, keep / name)

    def do_finish(session: Session, confirm_warnings: bool) -> dict:
        report = validate(session.spec)
        if not report.ok:
            return {"error": report.errors[0].text}
        if report.warnings and not confirm_warnings:
            return {"needs_confirm": True}
        t0 = time.perf_counter()
        # A new revision letter only when the drawing changed since the last finish.
        mark = _fingerprint(session.spec)
        if not session.revisions or session.revisions[-1]["fingerprint"] != mark:
            session.revisions.append({"rev": revision_name(len(session.revisions) + 1), "at": now_iso(), "fingerprint": mark})
        session.spec.revision = session.revisions[-1]["rev"]
        out = store.out_dir(session.spec.id)
        export_all(session.spec, out)
        archive(out, session.spec.revision)
        session.finished = True
        session.record("finish", revision=session.spec.revision, warnings_confirmed=[m.code for m in report.warnings], export_ms=round((time.perf_counter() - t0) * 1000))
        upload_to_drive(session)
        return {}

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.post("/session", status_code=201)
    def create_session():
        session = store.create()
        # The token is given once, here. No other answer repeats it as a field.
        return state(session, **({"token": session.token} if auth else {}))

    @app.get("/session/{sid}/spec")
    def get_spec(sid: str):
        return state(load(sid))

    @app.post("/session/{sid}/utterance")
    def utterance(sid: str, body: UtteranceIn):
        return handle_text(load(sid), body.text.strip(), {})

    @app.post("/session/{sid}/audio")
    async def audio(sid: str, request: Request):
        """One spoken sentence as a WAV body (16 kHz, 16-bit, mono).

        The audio stays in memory. It is not written to disk and not kept after STT.
        """
        session = load(sid)
        declared = request.headers.get("content-length")
        if declared and declared.isdigit() and int(declared) > MAX_WAV_BYTES:
            raise HTTPException(status_code=413, detail="Recording is too long")
        data = await request.body()
        try:
            pcm = wav_to_pcm(data)
        except AudioError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        del data

        def work():
            t0 = time.perf_counter()
            try:
                text = the_stt().transcribe(pcm)
            except SttError as e:
                raise HTTPException(status_code=503, detail=str(e)) from e
            timing = {"audio_s": round(len(pcm) / 32000, 1), "stt": round((time.perf_counter() - t0) * 1000)}
            if not text.strip():
                return state(session, ask="I did not hear anything", timing_ms=timing)
            return handle_text(session, text.strip()[:500], timing)

        return await run_in_threadpool(work)

    def handle_text(session: Session, text: str, timing: dict) -> dict:
        """Text -> interpreter -> operations -> new state. Shared by typed text and voice."""
        sid = session.spec.id
        t0 = time.perf_counter()

        # Quick fix: "no" or "wrong" alone takes the last entry back. No model call.
        if is_rejection(text):
            problem = do_undo(session)
            store.save(session)
            return state(session, heard=text, error=problem, undone=problem is None, timing_ms={**timing, "interpret": 0})

        # Guided measuring: a bare number answers the question on the display. No model call.
        field = "diameter" if session.pending_diameter is None else "length"
        number = None if session.finished else parse_number(text, field)
        if number is not None:
            extra = {"heard": text, "timing_ms": {**timing, "interpret": 0}}
            if field == "diameter":
                session.pending_diameter = number
                session.record("guide_diameter", utterance=text, diameter=number)
            else:
                op = AddSegment(op="add_segment", diameter=session.pending_diameter, length=number)
                ops_json = [op.model_dump(exclude_none=True)]
                try:
                    new_spec = apply_ops(session.spec, [op])
                except OpError as e:
                    session.record("rejected", utterance=text, ops=ops_json, reason=str(e), source="guide")
                    store.save(session)
                    return state(session, error=str(e), **extra)
                session.history.append(Turn(at=now_iso(), utterance=text, ops=ops_json, before=session.spec.model_dump(mode="json"), active_before=session.active_segment))
                session.active_segment = active_after(session.spec, [op], session.active_segment)
                session.spec = new_spec
                mark_changed(session)
                session.pending_diameter = None
                session.record("applied", utterance=text, ops=ops_json, source="guide")
            store.save(session)
            return state(session, **extra)

        try:
            result = the_interpreter().interpret(session.spec, text)
        except InterpreterError as e:
            raise HTTPException(status_code=503, detail=str(e)) from e
        timing["interpret"] = round((time.perf_counter() - t0) * 1000)
        log.info("turn %s timing_ms=%s", sid, timing)
        extra: dict = {"heard": text, "timing_ms": timing}

        if result.ask:
            session.record("ask", utterance=text, ask=result.ask)
            store.save(session)
            return state(session, ask=result.ask, **extra)

        ops_json = [op.model_dump(exclude_none=True) for op in result.ops]
        changes = [op for op in result.ops if not isinstance(op, (Undo, Finish))]
        if changes:
            try:
                new_spec = apply_ops(session.spec, changes)
            except OpError as e:
                session.record("rejected", utterance=text, ops=ops_json, reason=str(e))
                store.save(session)
                return state(session, error=str(e), **extra)
            session.history.append(Turn(at=now_iso(), utterance=text, ops=ops_json, before=session.spec.model_dump(mode="json"), active_before=session.active_segment))
            session.active_segment = active_after(session.spec, changes, session.active_segment)
            session.spec = new_spec
            mark_changed(session)
            session.pending_diameter = None  # a full sentence ends the half-entered segment
            session.record("applied", utterance=text, ops=ops_json)

        if any(isinstance(op, Undo) for op in result.ops):
            problem = do_undo(session)
            if problem:
                extra["error"] = problem
            else:
                extra["undone"] = True
        if any(isinstance(op, Finish) for op in result.ops):
            extra.update(do_finish(session, confirm_warnings=False))

        store.save(session)
        return state(session, **extra)

    @app.post("/session/{sid}/undo")
    def undo(sid: str):
        session = load(sid)
        problem = do_undo(session)
        store.save(session)
        return state(session, error=problem, undone=problem is None)

    @app.post("/session/{sid}/finish")
    def finish(sid: str, body: Optional[FinishIn] = None):
        session = load(sid)
        extra = do_finish(session, confirm_warnings=bool(body and body.confirm_warnings))
        store.save(session)
        return state(session, **extra)

    @app.get("/session/{sid}/render")
    def render(
        sid: str,
        tile: Optional[int] = Query(default=None, ge=0, le=1),
        view: Optional[int] = Query(default=None, ge=0, le=180),
    ):
        """Glasses image. No `tile`: the 576x144 band. tile=0 / tile=1: its 288x144 halves.

        No `view`: the 2D side view with dimensions. view=<degrees>: the 3D line view turned by that angle.
        """
        session = load(sid)
        spec, active = session.spec, active_of(session)
        if view is None:
            png = glasses_png(spec, active_segment=active, highlight=True) if tile is None else glasses_tiles(spec, active, True)[tile]
        elif tile is None:
            buf = io.BytesIO()
            render_glasses_3d(spec, view, active_segment=active).save(buf, format="PNG")
            png = buf.getvalue()
        else:
            png = glasses_3d_tiles(spec, view, active)[tile]
        return Response(content=png, media_type="image/png", headers={"Cache-Control": "no-store"})

    @app.get("/session/{sid}/files/{kind}")
    def download(sid: str, kind: str, rev: Optional[str] = None):
        """The current files, or with ?rev=A the kept files of an older revision."""
        session = load(sid)
        if kind not in FILE_NAMES:
            raise HTTPException(status_code=404, detail="Unknown file kind")
        if rev is not None:
            if rev not in [r["rev"] for r in session.revisions]:
                raise HTTPException(status_code=404, detail="Unknown revision")
            path = store.out_dir(sid) / f"rev_{rev}" / FILE_NAMES[kind]
            if not path.exists():
                raise HTTPException(status_code=404, detail="Unknown revision")
            return FileResponse(path, media_type=MEDIA[kind], filename=f"{sid}_rev{rev}.{kind}")
        path = store.out_dir(sid) / FILE_NAMES[kind]
        if not session.finished or not path.exists():
            raise HTTPException(status_code=404, detail="Not finished yet")
        return FileResponse(path, media_type=MEDIA[kind], filename=f"{sid}_rev{session.spec.revision}.{kind}")

    @app.post("/session/{sid}/approve")
    def approve(sid: str, body: ApproveIn):
        """Human approval, from the phone page only. The AI has no operation for this."""
        session = load(sid)
        if not session.finished:
            raise HTTPException(status_code=409, detail="Finish the drawing first")
        session.spec.status = "approved"
        session.spec.approved_by = body.name.strip()
        session.spec.approved_at = datetime.now(timezone.utc)
        rebuild_sheets(session.spec, store.out_dir(sid))
        archive(store.out_dir(sid), session.spec.revision or "A")
        upload_to_drive(session, kinds=["dxf", "pdf"])
        session.record("approved", by=session.spec.approved_by, revision=session.spec.revision)
        store.save(session)
        return state(session)

    @app.get("/s/{sid}", response_class=HTMLResponse)
    def phone_page(sid: str):
        session = load(sid)
        return phone_html(session, state(session), session.token if auth else None)

    return app


def phone_html(session: Session, st: dict, token: Optional[str] = None) -> str:
    spec = session.spec
    e = html.escape
    key = f"?k={token}" if token else ""
    and_key = f"&k={token}" if token else ""
    if not session.finished:
        body = "<p>The drawing is not finished yet. Say “finish” on the glasses.</p>"
    else:
        links = "".join(f'<a class="btn" href="{e(url)}">{e(kind.upper())}</a>' for kind, url in st["files"].items())
        if spec.status == "approved":
            mark = f"<p class='ok'>Approved for review by {e(spec.approved_by or '')}. Not a manufacturing release.</p>"
            form = ""
        else:
            mark = "<p class='draft'>DRAFT – requires engineering approval</p>"
            form = f"""<form onsubmit="approve(event)">
  <label>Your name <input id="name" required minlength="2" maxlength="60"></label>
  <button>Approve for review</button>
</form>
<script>
async function approve(ev) {{
  ev.preventDefault();
  const r = await fetch('/session/{e(spec.id)}/approve', {{method: 'POST', headers: {{'Content-Type': 'application/json', 'X-Session-Token': '{e(token or "")}'}},
    body: JSON.stringify({{name: document.getElementById('name').value}})}});
  if (r.ok) location.reload(); else alert('Approval failed');
}}
</script>"""
        drive = st.get("drive") or {}
        if drive.get("status") == "ok":
            links += f'<a class="btn drive" href="{e(drive["folder_url"])}">Google Drive folder</a>'
        elif drive.get("status") == "error":
            mark += f"<p class='draft'>Google Drive: {e(drive['message'])}</p>"
        older = [r["rev"] for r in session.revisions if r["rev"] != spec.revision]
        history = ""
        if older:
            items = " · ".join(f'<a href="/session/{e(spec.id)}/files/pdf?rev={e(r)}{e(and_key)}">{e(r)} (PDF)</a>' for r in older)
            history = f"<p class='old'>Older revisions: {items}</p>"
        body = f"<p>Revision {e(spec.revision or '-')}</p>{mark}<p class='files'>{links}</p>{form}{history}"
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{e(spec.title)} – EvenCAD</title>
<style>
body{{font:16px/1.5 system-ui,sans-serif;margin:0;padding:20px;max-width:560px;margin:auto;background:#111;color:#eee}}
img{{width:100%;background:#000;border:1px solid #333}} .btn,button{{display:inline-block;margin:6px 8px 6px 0;padding:12px 18px;
border-radius:8px;background:#2e7d32;color:#fff;text-decoration:none;border:0;font-size:16px}}
.drive{{background:#1565c0}} .draft{{color:#ffb300;font-weight:600}} .ok{{color:#66bb6a;font-weight:600}} input{{font-size:16px;padding:8px;width:100%;box-sizing:border-box;margin:6px 0}}
code{{color:#9e9e9e}} .old a{{color:#90caf9}}
</style></head><body>
<h1>{e(spec.title)}</h1>
<p><code>{e(spec.id)}</code></p>
<img src="/session/{e(spec.id)}/render{e(key)}" alt="Side view">
<p>{e(st['readback'])}</p>
{body}
</body></html>"""


def warm_up_stt() -> None:
    """Load the speech model in the background, so the first sentence is not slow."""
    import threading

    def load():
        try:
            get_stt().transcribe(b"\x00\x00" * 8000)  # half a second of silence
            log.info("speech model is ready")
        except Exception as e:  # warm-up must never stop the server
            log.warning("speech model warm-up failed: %s", e)

    threading.Thread(target=load, name="stt-warmup", daemon=True).start()


app = create_app()
if os.environ.get("STT_WARMUP") == "1":
    warm_up_stt()
