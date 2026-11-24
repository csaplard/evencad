# SayCAD — voice to engineering drawing on Even Realities G2

> Say it. See it. Sign it.

**Measure a part with both hands. Say the numbers. Get the drawing. The phone stays in your pocket.**

One hand holds the part. The other hand holds the caliper. Both are oily. You cannot write, and you cannot touch a phone.
With SayCAD you say each number as you measure it. The G2 glasses draw the shaft in front of you, step by step.
When you say "finish", a STEP model, a DXF and a PDF drawing are ready on your phone and in Google Drive.

![The shaft grows on the glasses as you speak](docs/img/active-segment.png)

**Demo video:** not recorded yet. The plan is in [docs/demo-script.md](docs/demo-script.md).

**Status (Nov 24): the full flow works in the simulator.** The interpreter runs on the real Anthropic API and the files go to a real Google Drive. Not tested yet: real G2 glasses, a human voice. See [Known limits](#known-limits).

Built for the "Heads Up: Even Realities Hackathon" (Nov 23–29, 2026).
Track: **04 · AI Assistants & Work**.

Idea and spec were prepared before Nov 23. All code was written during the hackathon.
Until Nov 24 the project was called "EvenCAD". The name changed because an Even Hub app name must not contain "Even".

## In 30 seconds

| You do | You say | The glasses show |
|---|---|---|
| Measure the first diameter | "Thirty." | `Next: segment 1 Ø30 length?` |
| Measure the length | "Forty." | The first segment is drawn |
| Hear a wrong number | "No." | `Undone.` The app listens again |
| Add a detail | "Keyway on the second one, twenty long." | The slot appears. Width and depth come from the standard table |
| End | "Finish." | `DRAFT rev A ready · saved to Drive` |

A bare number needs no AI call, so the answer is on the display at once. A full sentence goes to Claude.

## Why glasses

- **Hands busy.** Measuring needs two hands. A tap on the temple or on the R1 ring is the only touch.
- **Eyes on the part.** The read-back is in your view. You see a wrong number at once and say "no".
- **No phone, no PC, no CAD program at the bench.** The phone is needed only at the end, when a person approves the drawing.

## Why you can trust the drawing

- The AI never writes geometry. It turns a sentence into small typed operations. Plain code checks them and draws.
- Sizes that matter come from you or from a table in the code (keyway sizes, fit limits, densities). The AI cannot set them.
- If a number is missing, the AI asks. It does not guess.
- Every drawing is a **DRAFT** until a person approves it on the phone. The AI has no way to approve. Any later change makes it a DRAFT again.

## Problem and user

People who measure and make parts by hand: workshops, small machine shops, maintenance, field service, students.
Today they write the numbers on paper with dirty hands. Later someone types them into a CAD program.
Numbers get lost or swapped on the way.

With SayCAD the worker says the shaft dimensions out loud. The G2 glasses show a side view that grows as they speak.
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
Full design: [SAYCAD_SPEC.md](SAYCAD_SPEC.md). Demo plan: [docs/demo-script.md](docs/demo-script.md). SDK facts: [docs/sdk-notes.md](docs/sdk-notes.md).

## What works today

The end-to-end slice, by voice or by typed text:

speech → Whisper (on our server) → text → Claude (interpreter) → typed operations → ShaftSpec → validation → drawing on the glasses (simulator) → STEP, DXF, PDF.

- Operations, undo, validation (errors and warnings) and read-back, all in plain code with tests.
- One vector model of the side view. It feeds the glasses image, the DXF and the PDF.
- Glasses page: status line, drawing (two 288 × 144 image tiles), read-back and warnings.
- Tap on the glasses starts listening. It stops after 1.5 s of silence, on a second tap, or after 20 s.
- Guided measuring: the display always asks for the next number, for example `Next: segment 2 diameter?`.
  A bare number answers it ("twenty five", then "sixty"). The server reads the number itself. No model call, so it is fast.
  After a diameter the app listens for the length at once, with no extra tap. Full sentences still work at any time.
  Undo drops a half-entered segment first.

  ![Guided measuring](docs/img/guide-length.png)
- The segment that the last sentence changed is drawn with thicker lines, in the 2D view and in the 3D view.
  One look shows what the last sentence did. Undo moves the mark back.

  ![Active segment in 2D and 3D](docs/img/active-segment.png)
- Quick fix: say "no" or "wrong" (or long press) when the read-back is not what you said.
  The last entry is taken back without a model call, and the app listens again at once.
  With a question or a warning prompt on the display, "no" only closes that. "Undo" always undoes.
- When the model asks a question (`? What length for the keyway?`), the app listens for the answer at once. A short answer is enough ("twenty").
- Keyway: say "keyway on the second one, twenty long". The speaker gives only the segment and the length.
  Width and depth come from a table by the diameter (DIN 6885-1, form A). The AI cannot set them.
  The keyway is in the 2D view, the 3D view, the DXF and PDF (with a note) and it is cut into the STEP model.

  ![Keyway in 2D](docs/img/keyway-2d.png)

  ![Keyway in 3D](docs/img/keyway-3d.png)
- Fit and roughness: "the second one has an h six fit", "roughness one point six on the first one".
  They are notes: `Ø25 h6` in the diameter dimension and an `Ra 1.6` mark on the sheet. The fit must be a real ISO shaft fit.
  The sheet also gives the limits of the fit as a note, for example `Ø25 k6: +0.015/+0.002 (ISO 286)`.
  The numbers come from a table in the code (letters d to s, grades IT5 to IT11, sizes up to 500 mm). A fit outside the table has no numbers.
- Fillet and undercut at a shoulder: "fillet radius two at the first step", "undercut at step two, three wide and half a millimetre deep".
  The fillet is a real arc in the DXF and a round face in the STEP model. The undercut is a plain rectangular groove, not a DIN 509 shape.
  Both are in the 2D and 3D views, in the read-back (`R2 step 1`, `U3×0.5 step 2`), as notes on the sheet, and in the mass.

  ![Fillet and undercut](docs/img/fillet-undercut.png)
- Hungarian dictation: set `STT_LANGUAGE=hu` (the Whisper model is then `small`). Bare numbers ("huszonöt", "száz húsz",
  "huszonöt egész öt", "harmincas"), "nem" and "vissza" work without the model. Full sentences go to the model, which knows the
  Hungarian workshop words. The display texts and the questions of the model stay English.
- Mass: say the material ("material C45"). The read-back and the title block then show the mass, for example `424 g`.
  The volume comes from the spec by formula. The density comes from a small table by the material name (steel, stainless steel,
  cast iron, aluminium, brass, bronze, copper, titanium, POM, PA6). An unknown material shows no mass.
- Revisions: each finish of a changed drawing gets the next letter (A, B, ...). It is in the title block. Old revisions stay on the phone page.
  Any change after an approval makes the drawing a DRAFT again.
- AI hints: after `finish` a second model call looks at the shaft and gives up to three short hints (for example "Could segment 3 diameter be 30 not 13?").
  They are on the phone page only, marked as hints. They cannot change, approve or block anything. `REVIEWER=off` turns them off.
- Tap also accepts a warning. Double tap opens the system exit dialog.
- Swipe turns the drawing: 2D side view with dimensions, then a 3D line view at 30°, 60°, 90° (end view), 120°, 150°.
  The glasses show images only, so the 3D view turns in steps, one image per step.
- Speech to text runs on the backend with faster-whisper (`base.en`, about 1 s per sentence on a laptop CPU; `small` for Hungarian).
- `finish` makes `data/out/<session id>/shaft.step`, `shaft.dxf`, `shaft.pdf`.
- Phone page `/s/<session id>?k=<token>`: the 2D side view, downloads, and the human "Approve for review" step.
- Every session has a secret token. The server gives it once, when the session is made. Every call needs it, so the session id alone opens nothing.

- `finish` also copies the three files to a Google Drive folder (when Drive is set up). Approval replaces the DXF and PDF there.
  `finish` does not wait for the upload. The display says `saving to Drive…` and then `saved to Drive` or `Drive failed`.

Not done yet: real G2 test.

The interpreter has two adapters with the same prompt and the same JSON answer:

- `INTERPRETER=api` (default): the Anthropic API. Needs `ANTHROPIC_API_KEY` in `.env`. Model: `CLAUDE_MODEL` (default `claude-haiku-5-5`).
- `INTERPRETER=cli`: the Claude Code CLI, for development without an API key. Slow (5–8 s per sentence).

The API adapter was run against the real API on Nov 24 with `claude-haiku-5-5`: the 39 recorded sentences, three times each
(117 calls), all correct. One call takes about 0.5 s (median 0.54 s, slowest 1.3 s). The AI hints after `finish` work too.

![The slice in the simulator](docs/img/slice-2-ask.png)

![3D line view on the glasses](docs/img/glasses-3d-30.png)

## Quick start (one command)

Needs Node.js 22 LTS or newer, and Python 3.11+ (or Docker).

```bash
# Windows
powershell -ExecutionPolicy Bypass -File scripts\start.ps1

# macOS / Linux
./scripts/start.sh
```

The script creates `.env` from `.env.example`, installs everything, and starts the backend
(port 8000), the app dev server (port 5173) and the simulator. The first run takes a few minutes.
Then add your `ANTHROPIC_API_KEY` to `.env` and start it again.

In the simulator: **Click** = tap. Tap, speak into the PC microphone, wait. Or type a sentence in
the app page, for example `diameter thirty, forty long`. Say or type `finish` to get the files.

Options: `-NoSimulator` / `--no-simulator`, and `-Docker` / `--docker` to run the backend in a
container. Backend only: `docker compose up --build`.

Tested so far: `scripts\start.ps1` on Windows 11. The bash script and the Docker build are written but not run yet.

## Setup step by step

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
4. The tool creates the folder "SayCAD drawings" and prints a `GOOGLE_DRIVE_FOLDER_ID=...` line. Put it into `.env`.
   Without this line the upload stays off and nothing tells you.
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

Not tested yet. The planned steps, from the Even Hub docs:

1. The phone must reach the backend. Put the backend address into `app/.env.local` as
   `VITE_BACKEND_URL=...` and into the `whitelist` in `app/app.json` (full origin, for example
   `https://saycad.example.com`). Plain `http://` works only for a dev server on the same network.
2. `cd app && npm run dev`, then `npx evenhub qr --url http://<LAN-IP>:5173`.
3. In the Even Realities app (developer mode), open Even Hub and scan the QR code.
4. Package for upload: `npm run pack` makes an `.ehpk` file.

## Environment variables

See [.env.example](.env.example). Keys live only on the server, in `.env`. `.env` is never committed.

A value in `.env` wins over a variable of the same name in the shell or in Windows. An empty value in `.env` changes nothing.
The server log names the variables that `.env` replaced (names only).

## Input mapping

Current mapping (simulator). It is checked again on real G2.

| Input | Action |
|---|---|
| Tap (temple or R1 ring) | start listening / stop listening / accept a warning |
| Double tap | system exit dialog (store rule) |
| Voice: "undo", "finish" | undo the last change / build the files |
| Swipe down / swipe up | next view / previous view (2D, then 3D at 30°, 60°, 90°, 120°, 150°) |
| Long press | undo the last entry and listen again |

## Tests

```bash
.venv/Scripts/python -m pytest          # unit tests, no network
.venv/Scripts/python -m pytest -m live  # asks the real model (INTERPRETER=cli or api)
# Tests never read .env. For the live run with the API, put the values into the shell first:
#   bash:        set -a; . ./.env; set +a
#   PowerShell:  $env:INTERPRETER = 'api'; $env:ANTHROPIC_API_KEY = '...'
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

Only the specification ([SAYCAD_SPEC.md](SAYCAD_SPEC.md)). No code.

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

**Who needs it.** People who measure and make parts by hand: workshops, small machine shops,
field service, students. They have a part and a caliper, and no CAD seat at the bench.

**What is ready.** The app builds into an `.ehpk` package (`npm run pack`, checked with CLI 0.2.0).
It asks for two permissions only: `network` (one origin, our backend) and `g2-microphone`.

**What is needed to go live.**

- A hosted backend with a fixed HTTPS address (the whitelist is fixed inside the package).
- The store name must not contain the word "Even" (store rule). The name is "SayCAD". It was not checked against trademarks.
- Per-user Google Drive sign-in through a pairing page on the phone. Today the server uses one account.
- A short pairing code or a QR code that carries the phone page link from the glasses to the phone. Today the link is on the companion page.
- Usage limits per user, and a spend limit on the API key.
- Cost per drawing: a few short Claude calls with a small model, and speech-to-text on our own
  server. The Claude part is far below one cent per drawing at list prices. The server CPU is the main cost.
- Even Hub review: icon, privacy policy, beta test on real glasses with the phone locked.

**Safety model.**

- The output is a DRAFT. The mark is on every PDF and DXF until a person approves it on the phone page.
- The AI cannot approve. It has no operation for it, and a test checks that such an answer is refused.
- The AI never writes geometry. It returns small typed operations. Plain code validates and draws.
- If the AI is unsure, it asks. It does not guess a missing number.
- Audio is never stored. Secrets stay on the server. Tests and demos use made-up parts.

## Known limits

- **Not tested on real G2.** Image refresh speed, text size, the microphone level and the input
  mapping are checked only in the simulator.
- **Google Drive** was run with one real account on Nov 24: `finish` put the three files into a new sub-folder, and the approval
  replaced the DXF and the PDF. The upload takes about 6 s. It runs in the background: with a warm server `finish` answers in about 1 s.
- **Speed.** The target is under 4 seconds from the end of speech to the new drawing. Speech-to-text
  takes about 1 second here and the Claude call about 0.5 second. The whole chain with a human voice on real glasses is not measured.
- **The model answers are not the same on every run.** 117 of 117 test calls were right, but a wrong answer is possible.
  The read-back shows what was understood, and "no" takes it back.
- **Speech-to-text** was checked with a computer voice only. Human voices and workshop noise are open.
- **One part family:** stepped shafts with chamfers, shoulder fillets, plain undercuts and keyways. No threads, no cross holes,
  no geometric tolerances. Fits and roughness are notes.
- **Hungarian speech** was not tried with a real voice or with the `small` Whisper model. Only the text path is tested.
- **Drawing polish.** Diameter dimensions on the sheet cross the centre line.
- **One Google account, no user accounts.** A session is protected by its token only. The token is in the phone page link, so the link is the key: do not share it.
- **Languages:** English and Hungarian dictation. The display is English only.

More detail: [docs/open-questions.md](docs/open-questions.md).

## Feature requests

See [FEATURE_REQUESTS.md](FEATURE_REQUESTS.md).
