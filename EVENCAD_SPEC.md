# EvenCAD — Voice-to-Engineering for Even Realities G2

> Think it. Say it. Build it. (working slogan; see "Naming notes" at the end)

This file is the build specification for Claude Code.
Language rule: simple English, short sentences. Keep README and code comments in the same style.

## 0. Rules you must follow first

1. **Hackathon rules.** This project is for the "Heads Up: Even Realities Hackathon" (build week Nov 23–29, 2026). Track: **04 · AI Assistants & Work** (apps used: Claude, Google Workspace/Drive).
2. **No code before the kickoff (Nov 23).** This spec is a planning document. Make the first commit of the repo on Nov 23 and include this file. In the README say: "Idea and spec were prepared before Nov 23. All code was written during the hackathon."
3. **Start from zero.** Do not copy code from any earlier personal project. Use only open-source libraries and public APIs. List every library in the README.
4. **Do not guess the Even Hub SDK.** Read the official Even Hub docs and the kickoff briefing first. Write down what you learned in `docs/sdk-notes.md`. If a detail is unclear, put it in `FEATURE_REQUESTS.md` (the submission needs up to 5 such items) and use a safe fallback.
5. **Secrets.** API keys live only on the server in `.env`. Never commit them. Never put keys in the glasses app. Commit `.env.example` only.
6. **Safety.** The output is a **DRAFT drawing**. It is never approved for manufacture by the system. Every PDF carries a visible "DRAFT – requires engineering approval" mark until a human approves it (see 6.5).
7. **No real production data.** Use made-up parts for tests and for the demo.

## 1. Product in one paragraph

A worker holds a part and a caliper. They say the shaft dimensions out loud. The G2 glasses show a clean technical side view that grows as they speak. The system reads back what it understood. The worker confirms with a tap or the R1 ring, or corrects by voice. At the end, the backend creates STEP, DXF and PDF files. The worker needs no computer and no CAD program.

## 2. Scope

### In scope (MVP, must work end to end)
- **One part family: stepped shaft.** Axis horizontal. A list of cylindrical segments, left to right. Each segment has a diameter and a length. Optional chamfer on the two outer ends and on steps.
- Voice input → text → structured change to the part spec.
- Clarifying question when the input is unclear.
- Live drawing on the glasses display, with dimensions.
- Spoken-style read-back as text on the display, built from the spec by code (not by the AI).
- Voice correction and undo.
- Deterministic validation with errors and warnings.
- Export: STEP (3D), DXF (2D), PDF (2D sheet with title block).
- A simple phone page to download the files and to mark the drawing as approved by a human.
- **Save the files to a real Google Drive folder** from the backend (real account, one dedicated folder). The judges ask for real accounts and data, so this is part of the MVP, not a stretch. Sign-in happens on the server side, never in the WebView.

### Stretch (only if the MVP is stable and tested on real G2)
- Keyway section (a small table lookup, deterministic).
- Hungarian dictation (the STT language is a setting; test it).
- Second Claude call as a "plausibility reviewer" that can add warnings only.

### Out of scope
Discs, flanges, assemblies, threads, tolerances beyond a simple text note, GD&T, photo input, 3D view on the glasses, user accounts, Fusion/Inventor, any real manufacturing release.

## 2b. How we are judged (hackathon page checked on Nov 22 — the weights changed since Nov 18)

| Criterion | Weight | What it means for EvenCAD |
|---|---|---|
| Usefulness on G2 | 25% | A real moment: measuring a part with hands busy. Works at a glance and hands-free. |
| Read and write | 20% | Say a short phrase, confirm with one tap or the ring. Smart defaults and read-back, not long dictation. |
| Technical execution | 20% | **Works end to end on real accounts and data, not mocks.** Reliable, clean code, **easy to set up from the README.** |
| UX for display and voice | 15% | Clear on 576 × 288 monochrome. Natural by voice. |
| Business potential and safety | 20% | Real users and demand, **a clear path to launch in Even Hub**, careful with data. |

Consequences:
- The final demo uses real speech-to-text, real Claude and a real Google Drive account. Mocks are for development only.
- Safety counts twice as much as before. Keep the DRAFT mark, the human approval step, no audio storage and no secrets in the app.
- A judge may try to run the project. The README must work on a clean machine. Provide one-command start (Docker or a script).
- We enter **one track (04)**. The page allows two tracks only if the app really connects apps from several tracks. We do not need it.
- The community award now needs a named community in the registration form ("How did you hear about this hackathon?"). Fill it in.

## 3. Hardware and platform facts (from the hackathon page — verify in the docs)

- Display: monochrome green, 576 × 288 pixels per eye.
- Input: microphone, touch on the glasses, R1 ring. No camera. No speaker.
- The app is a web app (HTML/CSS/JS/TS) in a WebView inside the Even Realities App. It talks to G2 over Bluetooth through the **Even Hub SDK**.
- Only one app is on screen at a time. The app cannot show anything when the user switches away.
- The SDK gives **raw microphone audio**. We send it to our own server for speech-to-text.
- External calls must be whitelisted in `app.json` and must pass CORS. Use our own backend for all calls.
- Google sign-in does not work in the WebView. Do not use it in the glasses app.
- Tools: `npm i -g @evenrealities/evenhub-cli @evenrealities/evenhub-simulator`. Start from the official minimal template. Test in the simulator first. Test on real G2 before submission.

## 4. Architecture

```
G2 glasses app (TypeScript, Even Hub SDK)
   │  audio (raw PCM) / button events / spec state
   ▼
Backend (Python, FastAPI)
   ├─ POST /session                create session, return id
   ├─ POST /session/{id}/audio     audio → STT → text
   ├─ POST /session/{id}/utterance text → interpreter (Claude) → ops → apply → validate
   ├─ GET  /session/{id}/spec      current ShaftSpec + readback + validation report
   ├─ POST /session/{id}/undo
   ├─ POST /session/{id}/finish    validate → build STEP/DXF/PDF → files
   ├─ GET  /session/{id}/render    1-bit PNG 576×288 (only if client-side drawing is not possible)
   └─ GET  /s/{id}                 phone page: downloads + approve button
```

Rules:
- The **AI never writes geometry**. Claude turns speech into a small set of typed operations (section 5). Plain code applies the operations, validates, draws and exports.
- The read-back text is made from the spec by a template. Never by the AI. This stops invented read-backs.
- Session state: in memory plus a JSON file per session (`data/sessions/<id>.json`) with the full operation history (this gives undo and an audit trail).
- Pluggable parts behind small interfaces: `SttProvider`, `Interpreter`, `StepExporter`. This lets us swap a library that fails to install.

### Suggested stack
- Python 3.11+, FastAPI, Pydantic v2, `anthropic` SDK, `pytest`.
- Geometry: **CadQuery** for STEP (fallback: build123d if CadQuery will not install).
- 2D: **ezdxf** for DXF with real dimension entities. PDF from the DXF (ezdxf drawing add-on with the matplotlib backend, or reportlab). Pillow for the 1-bit glasses image.
- STT: Whisper, either via an API or `faster-whisper` on the server. Provider is set by env var. Add a short domain prompt (diameter, millimetre, chamfer, shaft, step, length).
- Claude model: env var `CLAUDE_MODEL`. Use a fast model for interpretation. Use tool use (structured output). Temperature 0. Keep the prompt small.
- Glasses app: TypeScript, Vite or the official template build.

## 4a. Interpreter adapters: develop with the CLI, ship with the API

Decision: during development the interpreter calls Claude through the Claude Code CLI in headless mode (runs on the Max subscription, no API cost). At the end we switch to the Anthropic API. The demo and the submission use the API only.

Implementation:
- One interface `Interpreter.interpret(spec, utterance) -> {ops, ask}`. Two adapters: `ClaudeCliInterpreter` (dev only) and `AnthropicApiInterpreter` (default). Choose with the env var `INTERPRETER=cli|api`. The default in `.env.example` and in the README is `api`.
- Both adapters use the **same prompt** and return the **same JSON**. Validate every answer with the Pydantic schema. If the answer is invalid, retry once, then return an `ask` ("I did not understand, please say it again"). Never apply unvalidated output.
- The CLI adapter must run in a clean, minimal mode: no project memory files, no tools, no permission prompts, JSON-only output. Check the current CLI flags in its help text. Do not guess flags.
- The CLI is slower than the API and shares the subscription limits with the coding session. **Do not use CLI timings to judge the 4-second target.** Measure speed only with the API.
- Golden tests use recorded answers, so they pass with both adapters.

Switch plan (hard dates):
- **Nov 27 (evening) at the latest:** switch to `api`. Run all tests, the full demo flow and one real G2 session with the API. Fix prompt differences now, not on the last day.
- After the switch, keep the CLI adapter only as a documented dev option, or remove it if it adds confusion. The README must work with an API key alone.
- Set a monthly spend limit on the API key. Use a fast model (see `CLAUDE_MODEL`). Cost estimate: well below 1 USD for thousands of calls.

## 5. Data model

Units: millimetres. Coordinates: axis along X, first segment starts at x = 0. Segment numbers are 1-based, left to right.

```json
{
  "id": "s_20261123_001",
  "title": "Shaft",
  "material": null,
  "segments": [
    {"diameter": 30, "length": 40, "chamfer_left": null, "chamfer_right": null},
    {"diameter": 25, "length": 60, "chamfer_left": null, "chamfer_right": null},
    {"diameter": 20, "length": 30, "chamfer_left": null, "chamfer_right": {"size": 1, "angle": 45}}
  ],
  "status": "draft",
  "approved_by": null,
  "approved_at": null
}
```

Derived values (never stored by hand): total length, maximum diameter, step list.

### Operations (the only thing the AI may output)

| op | fields |
|---|---|
| `add_segment` | diameter, length, at (index, default end) |
| `edit_segment` | index (number, or "last"), diameter?, length? |
| `delete_segment` | index |
| `set_chamfer` | where ("left_end", "right_end", or step number), size, angle (default 45) |
| `set_material` | text |
| `set_title` | text |
| `undo` | – |
| `finish` | – |

The interpreter returns one of:
- `{"ops": [...], "ask": null}`
- `{"ops": [], "ask": "Do you mean segment 2 or 3?"}`

Rules for the interpreter prompt:
- Output only operations from the table. No free text, no geometry.
- If a number or target is unclear, ask. Ask short questions. Never guess a missing dimension.
- Accept "diameter", "dia", "phi", "Ø", "round" for diameter. Accept spoken numbers ("thirty five point five").
- Give the interpreter the current spec as context, so that "make the second one 28" works.

## 6. Features in detail

### 6.1 Validation (deterministic code, runs after every change and again on finish)

**Errors (block `finish`):**
- no segments; any diameter or length ≤ 0; diameter > 500 or length > 2000 (limits in config)
- chamfer larger than the segment length, or larger than the radius available at that edge

**Warnings (shown on the display, user must confirm to continue):**
- adjacent diameter ratio > 2 (very large step)
- length/diameter ratio of the whole part > 20 (slender part)
- two equal adjacent diameters (probably one segment)
- a segment shorter than 2 mm

Each message has: code, short text (max 40 characters for the display), the segment it refers to. Add tests for every rule.

### 6.2 Read-back
Template, example: `3 steps  Ø30×40  Ø25×60  Ø20×30  C1 right  L130`.
Keep it under two display lines. Use it after every change.

### 6.3 Drawing (2D)
Make one function `draw_shaft(spec, style)` that returns a vector model. Use it for DXF, PDF and the glasses.
- Side view, thick outline, centre line (dash-dot), chamfers visible.
- Length dimensions under the part, diameter dimensions at the steps, overall length on the bottom row.
- **Glasses style:** 1-bit, line width ≥ 2 px, no grey, no fill, large text. The user said the drawing is readable on G2. Still check text height on a real device. If there are too many dimensions, show only the dimensions of the active segment plus the overall length, and show the full set on the review screen.
- **Sheet style (PDF/DXF):** A4 landscape, title block (title, material, units, scale, date, session id), the mark "DRAFT – requires engineering approval", and an empty field "Approved by / date".

### 6.4 Export
- STEP: revolve the profile. Apply chamfers. Check the file loads again (test).
- DXF: real `DIMENSION` entities, layers (`OUTLINE`, `CENTER`, `DIM`, `TEXT`).
- PDF: from the DXF. Test that it exists and has one page.
- Files go to `data/out/<session id>/`.

### 6.5 Human approval
- Default status is `draft`. The PDF carries the DRAFT mark.
- On the phone page `/s/{id}`, a person can press "Approve" and type a name. Then the status becomes `approved`, and the PDF is rebuilt with the name and date in the approval field. The DRAFT mark changes to "Approved for review by: <name> – not a manufacturing release".
- The system never approves by itself. The AI has no operation for approval.

### 6.6 Glasses UI states
`IDLE → LISTENING → HEARD (show text) → CHECK (drawing + read-back) → ASK (clarifying question) → REVIEW (warnings) → DONE (code to open the phone page)`

Layout idea (576×288): top line = status and heard text, centre = drawing, bottom line = read-back or the key hint. Map the confirm, undo and talk actions to the inputs that the SDK really supports (glasses touch and R1 ring). Decide after reading the docs; write the final mapping in the README.

### 6.7 Audio and speed
- Record one utterance (start and stop by input event or silence — whatever the SDK supports). Send as 16 kHz mono WAV.
- Do not store audio after STT (delete it). Say this in the README.
- Target: speech end → updated drawing in under 4 seconds. Log timing for STT, Claude and render on every turn.
- **Dev fallback:** a text box in the simulator, and an env flag to skip STT. The demo must still work if STT is slow or fails. Use the fallback for development only: the demo video and the final test use real STT, real Claude and real Drive. No mocks.

## 7. Repo layout

```
/app            glasses web app (TypeScript) + app.json
/server         FastAPI backend
  /core         spec, ops, validation, readback
  /draw         vector model, DXF, PDF, glasses render
  /cad          STEP export
  /ai           stt.py, interpreter.py (+ prompt)
  /web          phone page
/tests          pytest (unit + golden transcripts)
/samples        sample transcripts and expected specs
/docs           sdk-notes.md, demo-script.md
README.md  FEATURE_REQUESTS.md  .env.example  EVENCAD_SPEC.md
```

## 8. Tests (write them with the code, not after)

- Unit: every operation, undo, every validation rule, read-back text, exports load again.
- **Golden transcripts** in `/samples`: text in → expected ops out. Include:
  - "diameter thirty, forty long, then diameter twenty-five, sixty long"
  - a correction: "make the second one twenty-eight"
  - similar-sounding numbers: fifteen / fifty, thirteen / thirty (the interpreter must ask when unsure)
  - an unclear target: "make it bigger" → must ask
  - a chamfer: "one by forty-five on the right end"
- Run interpreter tests with recorded responses by default, and with the live API only on demand (`pytest -m live`).
- Manual test list for the real G2 (display readability, ring/touch mapping, audio quality in a noisy room).

## 9. Demo (3 minutes, also the acceptance test)

1. Open the app on the glasses (or the simulator). Show the empty state.
2. Dictate a 3–4 step shaft with one chamfer. The drawing grows.
3. The read-back shows the numbers. Correct one value by voice. Show undo.
4. Trigger one warning (for example a large step) and confirm it.
5. Say "finish". The phone page opens. Show STEP, DXF and PDF. Open the PDF: DRAFT mark visible. The same three files appear in the real Google Drive folder.
6. Approve on the phone. Show the PDF with the approval field filled.

Definition of done for the MVP: steps 1–6 work end to end, in the simulator and on real G2, with all tests passing and the README complete.

## 10. Work plan (Nov 23–29)

| Day | Goal |
|---|---|
| Nov 23 (kickoff) | Read docs and briefing. Simulator "hello world" with one input working. Backend skeleton. `docs/sdk-notes.md`. |
| Nov 24 | Core: spec, ops, validation, read-back + tests. CLI that builds STEP/DXF/PDF from a JSON file. |
| Nov 25 | STT and interpreter (CLI adapter first, API adapter written in parallel) with golden tests. Session API. Google Drive upload (real account). |
| Nov 26 | Glasses app loop in the simulator: listen → draw → confirm → undo. |
| Nov 27 | Display-optimised drawing, ASK and REVIEW states, phone page, approval. **Evening: switch the interpreter to the API (section 4a) and re-run everything.** |
| Nov 28 | Real G2 test. Fix readability and input mapping. Setup test on a clean machine, using only the README. Package the `.ehpk` build. Stretch items only if all green. |
| Nov 29 | README, demo video (max 3 min), `FEATURE_REQUESTS.md` (up to 5 items), final submit. **Deadline: Nov 29, 19:59 UTC** (23:59 in Dubai, 20:59 in Budapest). Submit with a safety margin. |

## 11. README must contain

Problem and user, how it works, track (04), setup steps (simulator and device; one-command start with Docker or a script; tested on a clean machine), env variables, architecture picture, input mapping, test commands, privacy note (audio deleted, keys on the server), "what existed before Nov 23" (spec only; list of open-source libraries), known limits, feature requests.

Also add a short section **"Path to launch in Even Hub"** (the judges score it): who needs this (people who measure and make parts by hand: workshops, small machine shops, field service, students), the packaged `.ehpk` build, what is needed to go live (hosted backend, per-user Google Drive sign-in through a pairing page, usage limits and cost per drawing), and the safety model (DRAFT mark, human approval, audio deleted after STT, no secrets in the app, no real production data).

## 12. Working method for Claude Code

- Read this file and the SDK docs before the first line of code.
- Work in small steps. After each step run the tests and commit.
- Do not add scope. If a stretch item needs more than half a day, drop it.
- Prefer boring and reliable over clever. A stable demo beats a wide demo.
- When something is unclear, write the question in `docs/open-questions.md` and choose the safest default.

## Appendix: first prompt for Claude Code (use at 09:00 Budapest / 12:00 Dubai on Nov 23, after the kickoff briefing)

```
Read EVENCAD_SPEC.md completely. This is the first day of the hackathon (the repo starts now).
1. Read the Even Hub docs and my notes from the kickoff briefing (I will paste them). Write docs/sdk-notes.md:
   how to draw on the display, how to get microphone audio, which input events exist (glasses touch, R1 ring),
   how app.json whitelisting and CORS work, packaging to .ehpk. Do not guess any API.
2. Create the repo layout from section 7. Add .gitignore, .env.example, README skeleton, FEATURE_REQUESTS.md.
3. Run the official minimal template in the simulator. Change one line of text. Make one input event work.
4. Build the backend skeleton (FastAPI, /session, /spec) with pytest running.
5. Stop and show me what works. Then continue with section 10, day 1.
Rules: small commits, tests first for core logic, no secrets in git, put open questions in docs/open-questions.md.
```

## Naming notes
"Build it" can suggest manufacturing. The system makes drawings and files only. Alternative slogan: **Say it. See it. Sign it.**

## Reality check (added Nov 23, after reading the SDK docs)

Details and sources are in `docs/sdk-notes.md`. These points change earlier sections:

- **Drawing (3, 6.3).** There is no pixel API. A drawing is a PNG sent to an image container. One image container is at most 288 × 144, and a page holds four. Default layout: two images side by side (576 × 144) for the drawing, text containers for status and read-back.
- **Display (3).** The panel has 16 grey levels, not 1 bit. We still draw in pure black and white.
- **Client-side drawing (4).** The glasses app cannot draw lines itself in a useful way. The backend renders the PNG (`GET /session/{id}/render`). This endpoint is now required, not a fallback.
- **Inputs (6.6).** Double tap on the root page must open the system exit dialog. It cannot be used for undo. Free gestures: tap, swipe up, swipe down, long press, contextual menu. A single tap arrives with no event type.
- **Audio (6.7).** The SDK gives PCM 16 kHz, 16-bit, mono, in about 100 ms frames. The app collects the frames and posts one WAV.
- **Name (naming notes).** The store name must not contain "Even". `app.json` uses a working name until a final name is chosen.
- **Session id (5).** Ids are `s_<date>_<6 random hex>`, so the phone page cannot be guessed.
- **Hungarian (2, stretch).** The store has no `hu` language. Dictation in Hungarian is still possible through STT.
