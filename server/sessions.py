"""Session store: in memory, plus one JSON file per session.

The file holds the spec and the full operation history.
The history gives undo and an audit trail (added in step 2).
"""

import json
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from server.core.spec import ShaftSpec

SESSION_ID_PATTERN = r"s_\d{8}_[0-9a-f]{6}"
_ID_RE = re.compile(SESSION_ID_PATTERN)


class Session(BaseModel):
    spec: ShaftSpec
    history: list[dict] = Field(default_factory=list)


def new_session_id(now: Optional[datetime] = None) -> str:
    now = now or datetime.now(timezone.utc)
    return f"s_{now:%Y%m%d}_{secrets.token_hex(3)}"


class SessionStore:
    def __init__(self, data_dir: Path):
        self._dir = Path(data_dir) / "sessions"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, Session] = {}

    def create(self) -> Session:
        sid = new_session_id()
        while self._path(sid).exists():
            sid = new_session_id()
        session = Session(spec=ShaftSpec(id=sid))
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
        text = json.dumps(session.model_dump(mode="json"), indent=2)
        self._path(sid).write_text(text, encoding="utf-8")

    def _path(self, sid: str) -> Path:
        return self._dir / f"{sid}.json"
