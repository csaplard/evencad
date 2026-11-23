"""EvenCAD backend (FastAPI).

Run:  uvicorn server.main:app --reload --port 8000
"""

import html
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field

from server.ai.interpreter import Interpreter, InterpreterError, get_interpreter
from server.core.ops import Finish, OpError, Undo, apply_ops
from server.core.readback import readback
from server.core.validation import validate
from server.draw.glasses import glasses_png, glasses_tiles
from server.export import FILE_NAMES, export_all, rebuild_sheets
from server.sessions import Session, SessionStore, Turn, now_iso

log = logging.getLogger("evencad")

MEDIA = {"step": "model/step", "dxf": "image/vnd.dxf", "pdf": "application/pdf"}


class UtteranceIn(BaseModel):
    text: str = Field(min_length=1, max_length=500)


class FinishIn(BaseModel):
    confirm_warnings: bool = False


class ApproveIn(BaseModel):
    name: str = Field(min_length=2, max_length=60)


def _load_env_file(path: Path = Path(".env")) -> None:
    """Tiny .env reader: KEY=value lines. Real environment variables win."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


def _cors_origins() -> list[str]:
    raw = os.environ.get("CORS_ALLOW_ORIGINS", "*")
    return [o.strip() for o in raw.split(",") if o.strip()] or ["*"]


def create_app(data_dir: Optional[Path] = None, interpreter: Optional[Interpreter] = None) -> FastAPI:
    _load_env_file()
    data_dir = Path(data_dir or os.environ.get("DATA_DIR", "data"))
    store = SessionStore(data_dir)
    holder = {"interpreter": interpreter}

    app = FastAPI(title="EvenCAD", version="0.2.0")

    # The glasses app runs in a WebView. Its origin is not documented,
    # so the default is "*". We use no cookies and no credentials.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type"],
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

    def state(session: Session, **extra) -> dict:
        """The one answer shape for every session call."""
        spec = session.spec
        report = validate(spec)
        files = {}
        if session.finished:
            files = {kind: f"/session/{spec.id}/files/{kind}" for kind in FILE_NAMES}
        return {
            "id": spec.id,
            "spec": spec.model_dump(mode="json"),
            "readback": readback(spec),
            "validation": report.model_dump(),
            "can_undo": bool(session.history),
            "finished": session.finished,
            "files": files,
            "phone_page": f"/s/{spec.id}",
            "heard": None,
            "ask": None,
            "error": None,
            "needs_confirm": False,
            **extra,
        }

    def do_undo(session: Session) -> Optional[str]:
        if not session.history:
            return "Nothing to undo"
        turn = session.history.pop()
        session.spec = type(session.spec).model_validate(turn.before)
        session.finished = False
        session.record("undo", undone=turn.ops)
        return None

    def do_finish(session: Session, confirm_warnings: bool) -> dict:
        report = validate(session.spec)
        if not report.ok:
            return {"error": report.errors[0].text}
        if report.warnings and not confirm_warnings:
            return {"needs_confirm": True}
        t0 = time.perf_counter()
        export_all(session.spec, store.out_dir(session.spec.id))
        session.finished = True
        session.record("finish", warnings_confirmed=[m.code for m in report.warnings], export_ms=round((time.perf_counter() - t0) * 1000))
        return {}

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.post("/session", status_code=201)
    def create_session():
        return state(store.create())

    @app.get("/session/{sid}/spec")
    def get_spec(sid: str):
        return state(load(sid))

    @app.post("/session/{sid}/utterance")
    def utterance(sid: str, body: UtteranceIn):
        session = load(sid)
        text = body.text.strip()
        t0 = time.perf_counter()
        try:
            result = the_interpreter().interpret(session.spec, text)
        except InterpreterError as e:
            raise HTTPException(status_code=503, detail=str(e)) from e
        interpret_ms = round((time.perf_counter() - t0) * 1000)
        log.info("turn %s interpret_ms=%s", sid, interpret_ms)
        extra: dict = {"heard": text, "timing_ms": {"interpret": interpret_ms}}

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
            session.history.append(Turn(at=now_iso(), utterance=text, ops=ops_json, before=session.spec.model_dump(mode="json")))
            session.spec = new_spec
            session.finished = False
            session.record("applied", utterance=text, ops=ops_json)

        if any(isinstance(op, Undo) for op in result.ops):
            problem = do_undo(session)
            if problem:
                extra["error"] = problem
        if any(isinstance(op, Finish) for op in result.ops):
            extra.update(do_finish(session, confirm_warnings=False))

        store.save(session)
        return state(session, **extra)

    @app.post("/session/{sid}/undo")
    def undo(sid: str):
        session = load(sid)
        problem = do_undo(session)
        store.save(session)
        return state(session, error=problem)

    @app.post("/session/{sid}/finish")
    def finish(sid: str, body: Optional[FinishIn] = None):
        session = load(sid)
        extra = do_finish(session, confirm_warnings=bool(body and body.confirm_warnings))
        store.save(session)
        return state(session, **extra)

    @app.get("/session/{sid}/render")
    def render(sid: str, tile: Optional[int] = Query(default=None, ge=0, le=1)):
        """Glasses image. No `tile`: the 576x144 band. tile=0 / tile=1: its 288x144 halves."""
        spec = load(sid).spec
        png = glasses_png(spec) if tile is None else glasses_tiles(spec)[tile]
        return Response(content=png, media_type="image/png", headers={"Cache-Control": "no-store"})

    @app.get("/session/{sid}/files/{kind}")
    def download(sid: str, kind: str):
        session = load(sid)
        if kind not in FILE_NAMES:
            raise HTTPException(status_code=404, detail="Unknown file kind")
        path = store.out_dir(sid) / FILE_NAMES[kind]
        if not session.finished or not path.exists():
            raise HTTPException(status_code=404, detail="Not finished yet")
        return FileResponse(path, media_type=MEDIA[kind], filename=f"{sid}.{kind}")

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
        session.record("approved", by=session.spec.approved_by)
        store.save(session)
        return state(session)

    @app.get("/s/{sid}", response_class=HTMLResponse)
    def phone_page(sid: str):
        session = load(sid)
        return phone_html(session, state(session))

    return app


def phone_html(session: Session, st: dict) -> str:
    spec = session.spec
    e = html.escape
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
  const r = await fetch('/session/{e(spec.id)}/approve', {{method: 'POST', headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{name: document.getElementById('name').value}})}});
  if (r.ok) location.reload(); else alert('Approval failed');
}}
</script>"""
        body = f"{mark}<p class='files'>{links}</p>{form}"
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{e(spec.title)} – EvenCAD</title>
<style>
body{{font:16px/1.5 system-ui,sans-serif;margin:0;padding:20px;max-width:560px;margin:auto;background:#111;color:#eee}}
img{{width:100%;background:#000;border:1px solid #333}} .btn,button{{display:inline-block;margin:6px 8px 6px 0;padding:12px 18px;
border-radius:8px;background:#2e7d32;color:#fff;text-decoration:none;border:0;font-size:16px}}
.draft{{color:#ffb300;font-weight:600}} .ok{{color:#66bb6a;font-weight:600}} input{{font-size:16px;padding:8px;width:100%;box-sizing:border-box;margin:6px 0}}
code{{color:#9e9e9e}}
</style></head><body>
<h1>{e(spec.title)}</h1>
<p><code>{e(spec.id)}</code></p>
<img src="/session/{e(spec.id)}/render" alt="Side view">
<p>{e(st['readback'])}</p>
{body}
</body></html>"""


app = create_app()
