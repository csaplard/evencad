"""One-time Google sign-in for the Drive upload. Run it on the server machine:

    python -m tools.drive_auth

It opens a browser. You sign in and allow "See and manage files created by this app".
Then it saves the token (outside git) and creates the EvenCAD folder in your Drive.
Copy the printed GOOGLE_DRIVE_FOLDER_ID line into .env.

Before the first run: create an OAuth client of type "Desktop app" in the Google Cloud
Console, enable the Google Drive API, and download the client file (see README).
"""

import os
import sys
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

from server.drive import DEFAULT_TOKEN_FILE, FOLDER_MIME, SCOPES, build_service
from server.main import _load_env_file

ROOT_FOLDER_NAME = "EvenCAD drawings"


def main() -> int:
    _load_env_file()
    client_file = Path(os.environ.get("GOOGLE_OAUTH_CLIENT_FILE") or "data/google_client.json")
    token_file = Path(os.environ.get("GOOGLE_TOKEN_FILE") or DEFAULT_TOKEN_FILE)
    if not client_file.exists():
        print(f"OAuth client file not found: {client_file}")
        print("Download it from the Google Cloud Console (OAuth client, type Desktop app).")
        return 1

    flow = InstalledAppFlow.from_client_secrets_file(str(client_file), SCOPES)
    creds = flow.run_local_server(port=0)
    token_file.parent.mkdir(parents=True, exist_ok=True)
    token_file.write_text(creds.to_json(), encoding="utf-8")
    print(f"Token saved: {token_file} (this file must stay out of git)")

    folder_id = os.environ.get("GOOGLE_DRIVE_FOLDER_ID", "").strip()
    if folder_id:
        print(f"GOOGLE_DRIVE_FOLDER_ID is already set: {folder_id}")
        return 0
    service = build_service(creds)
    body = {"name": ROOT_FOLDER_NAME, "mimeType": FOLDER_MIME}
    folder = service.files().create(body=body, fields="id, webViewLink").execute()
    print(f'Created the folder "{ROOT_FOLDER_NAME}": {folder.get("webViewLink")}')
    print("Add this line to .env:")
    print(f"GOOGLE_DRIVE_FOLDER_ID={folder['id']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
