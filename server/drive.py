"""Google Drive upload from the backend (EVENCAD_SPEC.md, section 2).

Sign-in happens on the server, never in the glasses WebView.
One-time setup:  python -m tools.drive_auth   (see README, "Google Drive").

Scope: `drive.file`. The app can only see files and folders that it created itself.
It cannot read anything else in the Drive. So the app makes its own root folder.
"""

import os
from pathlib import Path
from typing import Optional, Protocol

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
FOLDER_MIME = "application/vnd.google-apps.folder"
MIME = {".step": "model/step", ".dxf": "image/vnd.dxf", ".pdf": "application/pdf"}
DEFAULT_TOKEN_FILE = "data/google_token.json"


class DriveError(RuntimeError):
    """Upload failed or Drive is not set up."""


class DriveUploader(Protocol):
    def upload(self, session_id: str, paths: dict[str, Path]) -> dict:
        """Put the files into a folder named after the session.

        Returns {"folder_url": str, "files": {kind: url}}. Raises DriveError.
        """
        ...


class GoogleDriveUploader:
    def __init__(self, service, root_folder_id: str):
        self._service = service
        self._root = root_folder_id

    def _find(self, name: str, parent: str, mime: Optional[str] = None) -> Optional[dict]:
        safe = name.replace("\\", "\\\\").replace("'", "\\'")
        query = f"name = '{safe}' and '{parent}' in parents and trashed = false"
        if mime:
            query += f" and mimeType = '{mime}'"
        found = self._service.files().list(q=query, fields="files(id, webViewLink)", pageSize=1).execute()
        files = found.get("files", [])
        return files[0] if files else None

    def _session_folder(self, session_id: str) -> dict:
        existing = self._find(session_id, self._root, FOLDER_MIME)
        if existing:
            return existing
        body = {"name": session_id, "mimeType": FOLDER_MIME, "parents": [self._root]}
        return self._service.files().create(body=body, fields="id, webViewLink").execute()

    def upload(self, session_id: str, paths: dict[str, Path]) -> dict:
        from googleapiclient.errors import HttpError
        from googleapiclient.http import MediaFileUpload

        try:
            folder = self._session_folder(session_id)
            urls = {}
            for kind, path in paths.items():
                media = MediaFileUpload(str(path), mimetype=MIME.get(path.suffix, "application/octet-stream"))
                existing = self._find(path.name, folder["id"])
                if existing:
                    # A new finish or an approval replaces the content. The link stays the same.
                    done = self._service.files().update(fileId=existing["id"], media_body=media, fields="id, webViewLink").execute()
                else:
                    body = {"name": path.name, "parents": [folder["id"]]}
                    done = self._service.files().create(body=body, media_body=media, fields="id, webViewLink").execute()
                urls[kind] = done.get("webViewLink", "")
            return {"folder_url": folder.get("webViewLink", ""), "files": urls}
        except HttpError as e:
            raise DriveError(f"Google Drive error {e.resp.status}") from e
        except OSError as e:  # network problems, missing file
            raise DriveError(f"Google Drive upload failed: {e}") from e


def load_credentials(token_file: Path):
    """User credentials saved by tools/drive_auth.py. Refreshes the access token when needed."""
    from google.auth.exceptions import GoogleAuthError
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    if not token_file.exists():
        raise DriveError(f"No Google sign-in found ({token_file}). Run: python -m tools.drive_auth")
    try:
        creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)
        if not creds.valid:
            creds.refresh(Request())
            token_file.write_text(creds.to_json(), encoding="utf-8")
    except (GoogleAuthError, ValueError) as e:
        raise DriveError(f"Google sign-in is not valid any more. Run: python -m tools.drive_auth ({e})") from e
    return creds


def build_service(creds):
    from googleapiclient.discovery import build

    return build("drive", "v3", credentials=creds, cache_discovery=False)


def get_uploader() -> Optional[DriveUploader]:
    """None means: Drive upload is switched off (no folder id in the environment)."""
    folder_id = os.environ.get("GOOGLE_DRIVE_FOLDER_ID", "").strip()
    if not folder_id:
        return None
    token_file = Path(os.environ.get("GOOGLE_TOKEN_FILE") or DEFAULT_TOKEN_FILE)
    return GoogleDriveUploader(build_service(load_credentials(token_file)), folder_id)
