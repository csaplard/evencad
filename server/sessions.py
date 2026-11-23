"""Session store: in memory, plus one JSON file per session.

The file holds the spec, the undo stack and an append-only log (audit trail).
"""

import json
import os
import threading
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from server.core.spec import ShaftSpec

SESSION_ID_PATTERN = r"s_\d{8}_[0-9a-f]{6}"
_ID_RE = re.compile(SESSION_ID_PATTERN)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Turn(BaseModel):
    """One accepted change. `before` is the spec before it, for undo."""

    at: str
    utterance: Optional[str] = None
    ops: list[dict]
    before: dict
    active_before: Optional[int] = None  # the marked segment before it


class Session(BaseModel):
    spec: ShaftSpec
    token: Optional[str] = None  # secret of this session. Needed for every call.
    history: list[Turn] = Field(default_factory=list)  # undo stack
    log: list[dict] = Field(default_factory=list)  # everything that happened, never shortened
    finished: bool = False
    drive: Optional[dict] = None  # result of the last Google Drive upload
    awaiting: Optional[dict] = None  # a question or a warning prompt is on the display: {kind, ask, utterance}
    review: Optional[dict] = None  # AI hints for one revision: {revision, notes}
    revisions: list[dict] = Field(default_factory=list)  # one entry per finished revision: rev, at, fingerprint
    active_segment: Optional[int] = None  # 1-based: the segment the last change touched
    pending_diameter: Optional[float] = None  # guided measuring: diameter given, length still missing

    def record(self, event: str, **data) -> None:
        self.log.append({"at": now_iso(), "event": event, **data})


def new_session_id(now: Optional[datetime] = None) -> str:
    now = now or datetime.now(timezone.utc)
    return f"s_{now:%Y%m%d}_{secrets.token_hex(3)}"


class SessionStore:
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self._dir = self.data_dir / "sessions"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, Session] = {}
        self._save_lock = threading.Lock()

    def out_dir(self, sid: str) -> Path:
        return self.data_dir / "out" / sid

    def create(self) -> Session:
        sid = new_session_id()
        while self._path(sid).exists():
            sid = new_session_id()
        session = Session(spec=ShaftSpec(id=sid), token=secrets.token_urlsafe(18))
        session.record("created")
        self.save(session)
        return session

    def get(self, sid: str) -> Optional[Session]:
        # The id becomes a file name, so it must match the pattern exactly.
        if not _ID_RE.fullmatch(sid):
            return None
        if sid in self._cache:
            return self._cache[sid]
        path = self._path(sid)
        if not path.exists():
            return None
        session = Session.model_validate_json(path.read_text(encoding="utf-8"))
        self._cache[sid] = session
        return session

    def save(self, session: Session) -> None:
        sid = session.spec.id
        self._cache[sid] = session
        # Requests and the review thread may save the same session. Write a temp file,
        # then swap it in, so a reader never sees half a file.
        with self._save_lock:
            text = json.dumps(session.model_dump(mode="json"), indent=2)
            tmp = self._dir / f".{sid}.tmp"
            tmp.write_text(text, encoding="utf-8")
            os.replace(tmp, self._path(sid))

    def _path(self, sid: str) -> Path:
        return self._dir / f"{sid}.json"
