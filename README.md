# EvenCAD — voice to engineering drawing on Even Realities G2

> Say it. See it. Sign it.

**Status: day 1 skeleton.** Sections marked *TODO* are filled in during the build week.

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

- Glasses app: official minimal template, text on the display, tap and swipe events (simulator).
- Backend: `GET /health`, `POST /session`, `GET /session/{id}/spec`, sessions saved as JSON files.

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

### Glasses app in the simulator

```bash
cd app
npm install
npm run dev          # terminal 1
npm run simulate     # terminal 2
```

### Glasses app on real G2

*TODO* (`npx evenhub qr --url http://<LAN-IP>:5173`, then scan in the Even app.)

### One-command start

*TODO* (Docker or a script.)

## Environment variables

See [.env.example](.env.example). Keys live only on the server, in `.env`. `.env` is never committed.

## Input mapping

*TODO* — decided after the real G2 test. Double tap is reserved for exit (store rule).

## Tests

```bash
.venv/Scripts/python -m pytest          # unit tests, no network
.venv/Scripts/python -m pytest -m live  # calls real services (needs keys)
```

## Privacy and safety

- Audio is deleted right after speech-to-text. *TODO: implemented with STT.*
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
| pytest, httpx | tests | MIT, BSD-3-Clause |

*More are added as they come in (CadQuery, ezdxf, …).*

## Path to launch in Even Hub

*TODO* — users, `.ehpk` build, hosted backend, per-user Drive sign-in, cost per drawing, safety model.

## Known limits

*TODO*

## Feature requests

See [FEATURE_REQUESTS.md](FEATURE_REQUESTS.md).
