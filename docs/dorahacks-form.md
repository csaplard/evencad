# DoraHacks form: text for each field

Copy each block into the field with the same name on the "Create a new Build" page.

## Logo

Upload `docs/img/logo.png`.

## Name of your Build

```
SayCAD
```

## Brief description of this Build

```
Measure a part with both hands, say the numbers, and your G2 glasses make the engineering drawing.
```

## Tags

```
AI, Wearables, Smart Glasses, CAD, Voice
```

## GitHub Repo

```
https://github.com/csaplard/saycad
```

## Video

```
https://github.com/csaplard/saycad/raw/main/demo/saycad-demo.mp4
```

## Description (the large editor on the right)

```markdown
## SayCAD: say the numbers, your glasses draw the part

**Track: 04 · AI Assistants & Work** (Claude + Google Drive)

SayCAD turns spoken measurements into an engineering drawing. A worker holds a part and a caliper and says each number. The G2 glasses draw the shaft step by step. "Finish" makes a STEP model, a DXF and a PDF drawing, on the phone and in Google Drive. The phone stays in the pocket until a person approves the draft.

### The problem

People who measure parts by hand need both hands: one for the part, one for the caliper. The hands are often oily. Today they write the numbers on paper, and later someone types them into a CAD program. Numbers get lost or swapped. A phone does not help: you cannot hold it and you do not want to touch it.

### Who it is for

Workshops, small machine shops, maintenance teams, field service and students. Anyone who has a part and a caliper, and no CAD seat at the bench.

### How it works (read and write)

- **Read:** the display always shows the part so far and asks for the next number: `Next: segment 2 diameter?`
- **Write:** tap once and say a number. A bare number needs no AI call and answers in about one second.
- Say "no" when a number is wrong. The last entry is taken back and the app listens again.
- Say a full sentence for details: "chamfer one by forty five on the right end", "keyway on the second one, twenty long", "the second one has an h six fit", "material C45".
- Swipe to turn the part: a 2D side view with dimensions, then a 3D line view.
- Say "finish". A STEP model, a DXF and a PDF drawing are on the phone and in Google Drive.
- A person approves the drawing on the phone. Until then every sheet says DRAFT. Any change makes it a draft again.

### How the AI is used, and where it is not

- Claude turns one sentence into a small list of typed operations, for example `{"op": "set_keyway", "index": 2, "length": 20}`. It never writes geometry.
- Plain, tested code applies the operations, checks them, draws the views and writes the files.
- Sizes that matter come from the speaker or from a table in the code: keyway sizes (DIN 6885-1), fit limits (ISO 286), densities. The AI cannot set them.
- If a number is missing, the AI asks. It does not guess.
- The AI cannot approve a drawing. There is no operation for it, and a test checks this.

### Tech stack

- Glasses app: TypeScript, Even Hub SDK 0.0.16. It sends audio and input events and shows text and images.
- Backend: Python, FastAPI. Speech to text with faster-whisper on our own server. Claude (Anthropic API) as the interpreter. CadQuery for STEP, ezdxf for DXF and PDF, Pillow for the glasses images. Google Drive API for the files.
- More than 600 automated tests.
- Audio is never stored. All keys stay on the server. No keys are in the repository.

### Status

- The full flow works in the Even Hub simulator. It was not tested on G2 hardware.
- The demo video shows one real run of the backend: every text, drawing, file and time in it is an answer of the server. The frame around the display and the voice were made for the video; details are in `demo/README.md` in the repository.

### What existed before Nov 23

Only the idea and a written specification. All code was written between Nov 23 and Nov 29.

### Feature requests for Even Hub

1. A full-screen image container (576 × 288), or a documented way to tile. Today a drawing needs several image sends.
2. Document the raw image formats (Gray8, packed Gray4), so apps can skip PNG encoding.
3. A small vector API: lines, rectangles and text at x/y. Line drawings are tiny as vectors and large as bitmaps.
4. Text size and alignment in text containers. Dimension numbers and status lines need two sizes.
5. Document the WebView origin, so servers can use a strict CORS rule.
```

## Team Info and Contact Info

Fill these in yourself: your name, your role, and a contact the organizers can use (they pay prizes in USDT on TON).
