"""Google Drive upload. A fake Drive service stands in for the network.

The real upload needs a one-time sign-in (python -m tools.drive_auth) and is checked by hand.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from server.core.ops import InterpreterResult
from server.drive import FOLDER_MIME, SCOPES, DriveError, GoogleDriveUploader, get_uploader, load_credentials
from server.main import create_app


# ── A small in-memory stand-in for the Drive v3 `files` resource ─────────
class _Call:
    def __init__(self, result):
        self._result = result

    def execute(self):
        return self._result


class FakeDriveService:
    def __init__(self):
        self.items = {}  # id -> {name, parents, mimeType, version}
        self.log = []

    def files(self):
        return self

    def _link(self, fid):
        return f"https://drive.example/{fid}"

    def list(self, q, fields, pageSize):
        self.log.append(("list", q))
        name = q.split("name = '")[1].split("' and '")[0].replace("\\'", "'").replace("\\\\", "\\")
        parent = q.split("' and '")[1].split("' in parents")[0]
        want_folder = FOLDER_MIME in q
        hits = [
            {"id": fid, "webViewLink": self._link(fid)}
            for fid, it in self.items.items()
            if it["name"] == name and parent in it["parents"] and (not want_folder or it["mimeType"] == FOLDER_MIME)
        ]
        return _Call({"files": hits[:1]})

    def create(self, body, fields, media_body=None):
        fid = f"id{len(self.items) + 1}"
        self.items[fid] = {"name": body["name"], "parents": body.get("parents", []), "mimeType": body.get("mimeType", "file"), "version": 1}
        self.log.append(("create", body["name"]))
        return _Call({"id": fid, "webViewLink": self._link(fid)})

    def update(self, fileId, media_body, fields):
        self.items[fileId]["version"] += 1
        self.log.append(("update", self.items[fileId]["name"]))
        return _Call({"id": fileId, "webViewLink": self._link(fileId)})


@pytest.fixture
def out_files(tmp_path):
    paths = {}
    for kind, name in (("step", "shaft.step"), ("dxf", "shaft.dxf"), ("pdf", "shaft.pdf")):
        p = tmp_path / name
        p.write_bytes(b"x" * 10)
        paths[kind] = p
    return paths


def test_scope_is_limited_to_files_made_by_the_app():
    assert SCOPES == ["https://www.googleapis.com/auth/drive.file"]


def test_first_upload_creates_a_session_folder_and_three_files(out_files):
    service = FakeDriveService()
    result = GoogleDriveUploader(service, "ROOT").upload("s_20261123_abc123", out_files)
    folder = next(it for it in service.items.values() if it["mimeType"] == FOLDER_MIME)
    assert folder["name"] == "s_20261123_abc123" and folder["parents"] == ["ROOT"]
    names = sorted(it["name"] for it in service.items.values() if it["mimeType"] != FOLDER_MIME)
    assert names == ["shaft.dxf", "shaft.pdf", "shaft.step"]
    assert result["folder_url"].startswith("https://") and set(result["files"]) == {"step", "dxf", "pdf"}


def test_second_upload_replaces_the_files_and_keeps_the_links(out_files):
    service = FakeDriveService()
    uploader = GoogleDriveUploader(service, "ROOT")
    first = uploader.upload("s_20261123_abc123", out_files)
    second = uploader.upload("s_20261123_abc123", {"pdf": out_files["pdf"]})
    assert len(service.items) == 4  # one folder, three files, nothing doubled
    assert second["files"]["pdf"] == first["files"]["pdf"]
    assert ("update", "shaft.pdf") in service.log
    pdf = next(it for it in service.items.values() if it["name"] == "shaft.pdf")
    assert pdf["version"] == 2


def test_missing_file_is_a_drive_error(tmp_path):
    with pytest.raises(DriveError):
        GoogleDriveUploader(FakeDriveService(), "ROOT").upload("s_20261123_abc123", {"pdf": tmp_path / "nope.pdf"})


def test_drive_is_off_without_a_folder_id():
    assert get_uploader() is None


def test_missing_sign_in_is_explained(tmp_path, monkeypatch):
    with pytest.raises(DriveError, match="tools.drive_auth"):
        load_credentials(tmp_path / "google_token.json")
    monkeypatch.setenv("GOOGLE_DRIVE_FOLDER_ID", "ROOT")
    monkeypatch.setenv("GOOGLE_TOKEN_FILE", str(tmp_path / "google_token.json"))
    with pytest.raises(DriveError, match="tools.drive_auth"):
        get_uploader()


# ── Through the API ──────────────────────────────────────────────────────
class FakeUploader:
    def __init__(self, fail=False):
        self.fail = fail
        self.calls = []

    def upload(self, session_id, paths):
        self.calls.append((session_id, {k: Path(p).name for k, p in paths.items()}))
        if self.fail:
            raise DriveError("Google Drive error 403")
        return {"folder_url": f"https://drive.example/{session_id}", "files": {k: f"https://drive.example/{k}" for k in paths}}


class FakeInterpreter:
    def interpret(self, spec, utterance):
        ops = {"add": [{"op": "add_segment", "diameter": 30, "length": 40}], "finish": [{"op": "finish"}]}[utterance]
        return InterpreterResult.model_validate({"ops": ops, "ask": None})


def run(tmp_path, drive):
    client = TestClient(create_app(data_dir=tmp_path, interpreter=FakeInterpreter(), drive=drive))
    sid = client.post("/session").json()["id"]
    client.post(f"/session/{sid}/utterance", json={"text": "add"})
    st = client.post(f"/session/{sid}/utterance", json={"text": "finish"}).json()
    return client, sid, st


def test_finish_uploads_the_three_files(tmp_path):
    drive = FakeUploader()
    client, sid, st = run(tmp_path, drive)
    assert st["finished"]
    assert drive.calls == [(sid, {"step": "shaft.step", "dxf": "shaft.dxf", "pdf": "shaft.pdf"})]
    assert st["drive"]["status"] == "ok" and st["drive"]["folder_url"].endswith(sid)
    assert set(st["drive"]["files"]) == {"step", "dxf", "pdf"}
    assert "Google Drive folder" in client.get(f"/s/{sid}").text


def test_approval_uploads_the_rebuilt_sheets_again(tmp_path):
    drive = FakeUploader()
    client, sid, _ = run(tmp_path, drive)
    st = client.post(f"/session/{sid}/approve", json={"name": "Kis Anna"}).json()
    assert drive.calls[-1] == (sid, {"dxf": "shaft.dxf", "pdf": "shaft.pdf"})
    assert set(st["drive"]["files"]) == {"step", "dxf", "pdf"}  # the STEP link is kept


def test_a_drive_failure_does_not_block_the_drawing(tmp_path):
    client, sid, st = run(tmp_path, FakeUploader(fail=True))
    assert st["finished"] and st["error"] is None
    assert st["drive"] == {"status": "error", "message": "Google Drive error 403"}
    assert client.get(st["files"]["pdf"]).status_code == 200
    assert "Google Drive: Google Drive error 403" in client.get(f"/s/{sid}").text


def test_drive_switched_off(tmp_path):
    _, _, st = run(tmp_path, None)
    assert st["finished"] and st["drive"] is None


def test_drive_info_is_hidden_until_the_drawing_is_finished_again(tmp_path):
    client, sid, _ = run(tmp_path, FakeUploader())
    st = client.post(f"/session/{sid}/utterance", json={"text": "add"}).json()
    assert not st["finished"] and st["drive"] is None
