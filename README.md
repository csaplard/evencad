# EvenCAD — voice to engineering drawing on Even Realities G2

> Say it. See it. Sign it.

**Status: day 1, thin slice works in the simulator.** Sections marked *TODO* are filled in during the build week.

Built for the "Heads Up: Even Realities Hackathon" (Nov 23–29, 2026).
Track: **04 · AI Assistants & Work**.

Idea and spec were prepared before Nov 23. All code was written during the hackathon.

## Problem and user

A worker holds a part and a caliper. Their hands are busy. They say the shaft
dimensions out loud. The G2 glasses show a side view that grows as they speak.
They confirm with a tap or the R1 ring. At the end they get STEP, DXF and PDF files.
No computer and no CAD program is needed.

The output is always a **DRAFT**. A human must approve it. The system never approves by itself.

## How it works

```
G2 glasses app (TypeScript, Even Hub SDK)
   │  audio / input events / spec state
   ▼
Backend (Python, FastAPI)
   speech → text → Claude → typed operations → plain code applies, validates, draws, exports
```

The AI never writes geometry. It only returns small typed operations.
Full design: [EVENCAD_SPEC.md](EVENCAD_SPEC.md). SDK facts: [docs/sdk-notes.md](docs/sdk-notes.md).

## What works today

The end-to-end slice, by voice or by typed text:

speech → Whisper (on our server) → text → Claude (interpreter) → typed operations → ShaftSpec → validation → drawing on the glasses (simulator) → STEP, DXF, PDF.

- Operations, undo, validation (errors and warnings) and read-back, all in plain code with tests.
- One vector model of the side view. It feeds the glasses image, the DXF and the PDF.
- Glasses page: status line, drawing (two 288 × 144 image tiles), read-back and warnings.
- Tap on the glasses starts listening. It stops after 1.5 s of silence, on a second tap, or after 20 s.
- Tap also accepts a warning. Double tap opens the system exit dialog.
- Speech to text runs on the backend with faster-whisper (`base.en`, about 1 s per sentence on a laptop CPU).
- `finish` makes `data/out/<session id>/shaft.step`, `shaft.dxf`, `shaft.pdf`.
- Phone page `/s/<session id>`: downloads and the human "Approve for review" step.

- `finish` also copies the three files to a Google Drive folder (when Drive is set up). Approval replaces the DXF and PDF there.

Not done yet: real G2 test, one-command start.

The interpreter has two adapters with the same prompt and the same JSON answer:

- `INTERPRETER=api` (default): the Anthropic API. Needs `ANTHROPIC_API_KEY` in `.env`. Model: `CLAUDE_MODEL` (default `claude-haiku-5-5`).
- `INTERPRETER=cli`: the Claude Code CLI, for development without an API key. Slow (5–8 s per sentence).

The API adapter is tested with a fake client only. It has not been run against the real API yet (no key on the dev machine).

![The slice in the simulator](docs/img/slice-2-ask.png)

## Setup

Needs: Node.js 22 LTS (or newer), Python 3.11+.

### Backend

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-dev.txt     # Windows
# .venv/bin/python -m pip install -r requirements-dev.txt       # macOS / Linux
cp .env.example .env
.venv/Scripts/python -m uvicorn server.main:app --reload --port 8000
```

Open `http://localhost:8000/docs` for the API. Type a sentence in the app page (below), or call
`POST /session` and `POST /session/{id}/utterance` with `{"text": "diameter thirty, forty long"}`.

### Google Drive (optional)

The backend uploads with your own Google account. The glasses app never sees Google.
The app asks only for the `drive.file` scope: it can see only the files it creates.

1. In the Google Cloud Console: create a project, enable the **Google Drive API**, set up the OAuth consent screen (add yourself as a test user), and create an **OAuth client ID** of type **Desktop app**.
2. Download the client file to `data/google_client.json` (the `data/` folder is not in git).
3. Run `.venv/Scripts/python -m tools.drive_auth`. A browser opens. Sign in and allow access.
4. The tool creates the folder "EvenCAD drawings" and prints a `GOOGLE_DRIVE_FOLDER_ID=...` line. Put it into `.env`.
5. Restart the backend. Each finished session gets its own sub-folder with `shaft.step`, `shaft.dxf`, `shaft.pdf`.

If Drive fails, the drawing is still finished and the files stay downloadable from the phone page.

### Glasses app in the simulator

```bash
cd app
npm install
npm run dev          # terminal 1
npm run simulate     # terminal 2
```

The app talks to `http://localhost:8000`. Set `VITE_BACKEND_URL` in `app/.env.local` to change it.
Script a session without typing: `evenhub-simulator "http://localhost:5173/?say=diameter thirty, forty long|finish"`.

### Glasses app on real G2

*TODO* (`npx evenhub qr --url http://<LAN-IP>:5173`, then scan in the Even app.)

### One-command start

*TODO* (Docker or a script.)

## Environment variables

See [.env.example](.env.example). Keys live only on the server, in `.env`. `.env` is never committed.

## Input mapping

Current mapping (simulator). It is checked again on real G2.

| Input | Action |
|---|---|
| Tap (temple or R1 ring) | start listening / stop listening / accept a warning |
| Double tap | system exit dialog (store rule) |
| Voice: "undo", "finish" | undo the last change / build the files |
| Swipe up, swipe down, long press | not used yet |

## Tests

```bash
.venv/Scripts/python -m pytest          # unit tests, no network
.venv/Scripts/python -m pytest -m live  # asks the real model (INTERPRETER=cli or api)
.venv/Scripts/python -m tools.record_golden   # record fresh model answers into samples/golden.json
```

## Privacy and safety

- Audio is never stored. One sentence is held in memory, turned into text, and dropped. A test checks that no audio reaches the disk.
- The microphone is open only while the display says "Listening".
- Google Drive: scope `drive.file` only. The token stays on the server in `data/` (not in git).
- No secrets in the glasses app. All external calls go through our backend.
- Every PDF carries "DRAFT – requires engineering approval" until a human approves it.
- Tests and the demo use made-up parts only.

## What existed before Nov 23

Only the specification ([EVENCAD_SPEC.md](EVENCAD_SPEC.md)). No code.

## Open-source libraries and tools

| Name | Use | License |
|---|---|---|
| [evenhub-templates / minimal](https://github.com/even-realities/evenhub-templates) | starting point of `/app` | MIT |
| `@evenrealities/even_hub_sdk` | bridge to the glasses | MIT |
| `@evenrealities/evenhub-cli`, `@evenrealities/evenhub-simulator` | packaging, simulator | see npm |
| Vite, TypeScript | app build | MIT, Apache-2.0 |
| FastAPI, Uvicorn, Pydantic | backend | MIT, BSD-3-Clause, MIT |
| CadQuery (OpenCascade) | STEP export | Apache-2.0 |
| ezdxf | DXF with dimensions, DXF → PDF drawing | MIT |
| Matplotlib | PDF backend | PSF-style (BSD compatible) |
| Pillow | glasses image | MIT-CMU |
| faster-whisper (CTranslate2, Whisper `base.en` model) | speech to text on the server | MIT |
| `anthropic` (official SDK) | interpreter, default adapter | MIT |
| google-api-python-client, google-auth, google-auth-oauthlib | Google Drive upload | Apache-2.0 |
| pytest, httpx, pypdf | tests | MIT, BSD-3-Clause, BSD-3-Clause |
| Claude Code CLI | interpreter during development only | Anthropic terms |

## Path to launch in Even Hub

*TODO* — users, `.ehpk` build, hosted backend, per-user Drive sign-in, cost per drawing, safety model.

## Known limits

*TODO*

## Feature requests

See [FEATURE_REQUESTS.md](FEATURE_REQUESTS.md).
