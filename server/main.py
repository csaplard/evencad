"""EvenCAD backend (FastAPI).

Run:  uvicorn server.main:app --reload --port 8000
"""

import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from server.sessions import Session, SessionStore


def _cors_origins() -> list[str]:
    raw = os.environ.get("CORS_ALLOW_ORIGINS", "*")
    return [o.strip() for o in raw.split(",") if o.strip()] or ["*"]


def create_app(data_dir: Optional[Path] = None) -> FastAPI:
    data_dir = Path(data_dir or os.environ.get("DATA_DIR", "data"))
    store = SessionStore(data_dir)

    app = FastAPI(title="EvenCAD", version="0.1.0")

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

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.post("/session", status_code=201)
    def create_session():
        session = store.create()
        return {"id": session.spec.id, "spec": session.spec.model_dump(mode="json")}

    @app.get("/session/{sid}/spec")
    def get_spec(sid: str):
        # Read-back and the validation report are added to this answer in step 2.
        return {"spec": load(sid).spec.model_dump(mode="json")}

    return app


app = create_app()
