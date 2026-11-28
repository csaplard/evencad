# Submission text

Text blocks for the hackathon form. Copy the block that fits each field.
The exact fields of the form were not checked. Cut or join the blocks as the form needs.

Every sentence here must be true on the day of the submission. Check the list at the end before you paste.

## Name

SayCAD

## Track

04 · AI Assistants & Work

## One line (under 100 characters)

Measure a part with both hands, say the numbers, and your G2 glasses make the engineering drawing.

## Short description (about 50 words)

SayCAD turns spoken measurements into an engineering drawing. A worker holds a part and a caliper and says each
number. The G2 glasses draw the shaft step by step. "Finish" makes a STEP model, a DXF and a PDF drawing. The phone
stays in the pocket until a person approves the draft.

## Long description

### The problem

People who measure parts by hand need both hands: one for the part, one for the caliper. The hands are often oily.
Today they write the numbers on paper. Later someone types them into a CAD program. Numbers get lost or swapped.
A phone does not help here. You cannot hold it and you do not want to touch it.

### What SayCAD does

- You tap the glasses once and say a number. The display asks for the next one: `Next: segment 2 diameter?`
- The shaft grows on the display as you speak. The segment you changed last has thick lines.
- Say "no" when a number is wrong. The last entry is taken back and the app listens again.
- Say a full sentence for details: "chamfer one by forty five on the right end", "keyway on the second one,
  twenty long", "fillet radius two at the first step", "the second one has an h six fit", "material C45".
- Swipe to turn the part: a 2D side view with dimensions, then a 3D line view from five angles.
- Say "finish". A STEP model, a DXF and a PDF drawing are on your phone and in Google Drive.
- A person approves the drawing on the phone. Until then every sheet says DRAFT.

### Why it needs glasses

The whole job is done with busy hands and with the eyes on the part. The read-back is in your view, so you catch a
wrong number at once. The only touch is a tap on the temple or on the R1 ring.

### How the AI is used, and where it is not

- Claude turns one sentence into a small list of typed operations. It never writes geometry.
- Plain, tested code applies the operations, checks them, draws the views and writes the files.
- Sizes that matter come from the speaker or from a table in the code: keyway sizes (DIN 6885-1),
  fit limits (ISO 286), densities. The AI cannot set them.
- If a number is missing, the AI asks. It does not guess.
- The AI cannot approve a drawing. There is no operation for it, and a test checks this.
- Bare numbers, "no" and "undo" need no AI call. They are read by plain code, in English and in Hungarian.

### How it is built

- Glasses app: TypeScript, Even Hub SDK. It sends audio and input events and shows text and images.
- Backend: Python, FastAPI. Speech to text with faster-whisper on our own server. Claude as the interpreter.
  CadQuery for STEP, ezdxf for DXF and PDF, Pillow for the glasses images.
- About 600 automated tests, and 39 recorded model answers that are checked again on demand.
- Audio is never stored. All keys stay on the server.

### Who it is for

Workshops, small machine shops, maintenance teams, field service and students. Anyone who has a part and a caliper,
and no CAD seat at the bench.

### What is next

- More part families: threads, cross holes, flanges, plates.
- Per-user Google Drive sign-in and a pairing code from the glasses to the phone.
- A hosted backend and the Even Hub store review.
- Standard undercut shapes (DIN 509) and geometric tolerances.

## What was built during the hackathon

Only the written specification existed before Nov 23. All code was written between Nov 23 and Nov 29.

## Links

- Code: https://github.com/csaplard/saycad
- Demo video: `demo/saycad-demo.mp4` in the repository (2:55). Upload it to the video site the form asks for and put the link here.
  Say in the form: "The video shows one real run of the pipeline. The voice is an AI voice made from my own voice. Tested in the Even Hub simulator, not on G2 hardware yet."
- Package: (add the `.ehpk` file or its link, if the form asks for it)

## Check before you paste

Change the text if one of these is still open on the day:

- [x] A demo video exists (Nov 28): a real run of the pipeline with an AI voice (made from the voice of the author). The end card says so.
- [ ] The demo video is recorded with a person speaking, and the link is in the README and above.
- [ ] The app ran on real G2 glasses. If not, write "tested in the Even Hub simulator" in the short description.
- [x] The real Anthropic API was used (Nov 24: 117 of 117 test calls right, about 0.5 s per call).
- [x] Google Drive upload ran with a real account (Nov 24).
- [ ] Hungarian speech was tried with a voice. If not, write "Hungarian text input" and not "Hungarian dictation".
- [ ] The test count is still right (`python -m pytest`).
- [ ] The repository is public.
