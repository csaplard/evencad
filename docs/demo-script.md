# Demo script (3 minutes)

This is the plan for the demo video. It is also the acceptance test (`EVENCAD_SPEC.md`, section 9).
The part is made up. No real production data.

Status on Nov 23: every step below works in the simulator with typed text.
Steps with voice, the Anthropic API, Google Drive and real G2 still need a run by Dániel (see "Before recording").

## The part

A small made-up drive shaft, 130 mm long:

| Segment | Diameter | Length | Extra |
|---|---|---|---|
| 1 | 30 | 40 | |
| 2 | 25 | 60 | keyway 20 long, fit h6, Ra 1.6 |
| 3 | 20 | 30 | chamfer 1 × 45° on the right end |

Have the part (or a dummy) and a caliper in the hands. The point of the demo: both hands are busy.

## Before recording

1. `.env`: `INTERPRETER=api`, `ANTHROPIC_API_KEY`, `GOOGLE_DRIVE_FOLDER_ID` set. Run `python -m tools.drive_auth` once.
2. Start everything: `powershell -ExecutionPolicy Bypass -File scripts\start.ps1`.
3. Wait for "speech model is ready" in the log. The first sentence is slow without the warm-up.
4. Open the Google Drive folder in a browser tab. Open the companion page on the phone.
5. Do one full dry run. Delete the test files from Drive after it.

## Shot list

Times are targets. Speak slowly and leave a short pause after each number.

| Time | What you do | What you say | What the display shows |
|---|---|---|---|
| 0:00 | Hold the part and the caliper. Glasses on. | (voice-over) "Measuring a part by hand means writing numbers with dirty hands. EvenCAD takes them by voice and makes the drawing." | `Tap and say a number. Next: segment 1 diameter?` |
| 0:15 | Tap. Measure the first diameter. | "Thirty." | `Next: segment 1 Ø30 length?` The app listens again by itself. |
| 0:22 | Measure the length. | "Forty." | The first segment is drawn. `Next: segment 2 diameter?` |
| 0:28 | Tap. Second segment. | "Twenty five." … "Sixty." | Two segments. The new one has thick lines. |
| 0:38 | Tap. Third segment, on purpose misheard or wrong. | "Fifty." | `Next: segment 3 Ø50 length?` |
| 0:43 | Quick fix. | "No." | `Undone. Listening… segment 3 diameter?` |
| 0:47 | Say the right value. | "Twenty." … "Thirty." | Three segments. Read-back: `3 steps  Ø30×40  Ø25×60  Ø20×30  L130` |
| 0:57 | Tap. A full sentence. | "Chamfer one by forty five on the right end." | The chamfer appears. `C1 right` in the read-back. |
| 1:05 | Tap. Keyway. | "Keyway on the second one, twenty long." | The slot appears on segment 2. `KW2 8×20`. Say in the voice-over: "I gave only the length. Width and depth come from the standard table, not from the AI." |
| 1:17 | Tap. Notes. | "The second one has an h six fit, roughness one point six." | `Ø25h6×60` and `Ra1.6 #2` |
| 1:27 | Tap. Material. | "Material C forty five." | The mass appears at the end of the read-back. |
| 1:35 | Swipe down two times. | (voice-over) "A swipe turns the part." | 3D line view at 30°, then 60°. The keyway is visible. Swipe up back to 2D. |
| 1:45 | Tap. Trigger a warning. | "Add a segment, diameter ninety, ten long." | `Warning: Large step: 20 to 90` |
| 1:53 | Tap. | "Finish." | `Tap to accept the warning and finish` |
| 1:57 | Long press instead: the flange was a mistake. | (nothing) | `Undone`. The flange is gone. Then say "Finish." |
| 2:05 | Wait. | | `DRAFT rev A ready · saved to Drive · code ……` |
| 2:10 | Phone: open the files page. | (voice-over) "The files are on the phone and in Google Drive." | Side view, STEP, DXF, PDF buttons, AI hints box. |
| 2:20 | Open the PDF. Zoom to the title block. | "It is a draft. The AI never approves." | `DRAFT – requires engineering approval`, `Rev: A`, keyway note, mass. |
| 2:30 | Show the Drive folder tab. | | The same three files. |
| 2:37 | Phone: type a name, press "Approve for review". Open the PDF again. | "A person approves it." | `Approved for review by: …` |
| 2:47 | Glasses: one more change. Tap. | "Make the first one thirty two." | The drawing is a DRAFT again. Say "Finish": `DRAFT rev B ready`. |
| 2:57 | End card. | "EvenCAD. From the part in your hand to a drawing, hands-free." | |

## If something goes wrong during recording

- A number is misheard: say "no" and say it again. This is a feature, keep it in the video.
- The model asks a question (`? …`): answer it with a full sentence.
- Speech recognition is slow or fails: type the sentence into the companion page. Do not use this take for the final video. The final video uses real speech.
- Drive fails: the display says `Drive failed`. The files are still on the phone page. Fix the sign-in and record again.

## What to say about safety (one sentence each, in the voice-over or as captions)

- The AI turns speech into a small set of typed operations. It never writes geometry.
- Sizes that matter come from the person or from a table in the code.
- Every drawing is a DRAFT until a person approves it. Any change makes it a draft again.
- Audio is not stored. Secrets stay on the server.
