# Open questions

Each item has a safe default. We work with the default until we know more.

## Needs an answer from Dániel

1. **App name.** The store rule says the name must not contain "Even". "EvenCAD" breaks this rule.
   Default: `app.json` uses `"name": "ShaftCAD Draft"`. Repo and project name stay EvenCAD for now. Please pick a final name.
2. **Kickoff briefing.** Not attended. If there is a recap or a recording, paste it. It may change the notes.
3. **DoraHacks page.** It blocks automated reading (HTTP 405). Submission rules and judging weights in the spec come from Nov 22 and are not re-checked.
4. **Real G2 access.** Which day is the device available? The spec plans the test for Nov 28. Earlier is safer: image speed and text size decide the layout.
5. **Even Hub account.** `evenhub login` is interactive. It is needed for `create` / `upload` and for a beta build (lock-screen test).
6. **Public HTTPS backend.** The glasses app needs an `https://` origin in the whitelist. `cloudflared` is installed on this PC. Default: a Cloudflare tunnel for the demo. A fixed hostname is needed, because the whitelist is baked into the `.ehpk`.
7. **Package id.** Default `com.csaplard.evencad`. Change it if you own a better namespace.

## Technical, to be measured or tested

8. **Full-width drawing.** One image container is at most 288 × 144, four per page. Default: two images side by side (576 × 144) for the drawing, text containers for status and read-back. Measure the refresh time on real G2. Fallback: one image.
9. **Raw image formats.** The simulator accepts raw Gray8 and packed Gray4, but the byte layout is not documented. Default: PNG only.
10. **1-bit drawing on a 4-bit panel.** The spec says 1-bit. The panel has 16 levels. Default: pure black and white PNG. Grey for the centre line is possible later.
11. **Text size on glass.** The font is fixed. Dimension numbers inside the image are our own pixels, so we choose their size. Minimum readable height must be checked on real G2.
12. **WebView origin.** Not documented. Default: `Access-Control-Allow-Origin: *` on our backend. No cookies, no credentials.
13. **Hold-to-talk.** Long press start/stop looks ideal for "talk", but the OS uses "tap then long press" for its own menu, and the docs call long press an extra. Default: tap toggles listening; long press is an optional second way. Decide on real G2.
14. **Undo gesture.** Double tap is reserved for exit. Default: voice ("undo") plus the contextual menu item "Undo".
15. **Hungarian.** `supported_languages` has no `hu`. This is only the store language. Hungarian dictation (stretch) is still possible through STT.
16. **Session id.** The spec example is `s_20261123_001`. The phone page `/s/{id}` must not be guessable. Default: `s_<date>_<6 random hex>`. A short pairing code for the DONE screen comes later.
17. **Node 26.** The SDK says Node 20 or 22+. It works on 26.4 here. The README will recommend Node 22 LTS.

## Added after the slice (Nov 23)

18. **Diameter dimensions on the sheet.** They are real DIMENSION entities, drawn across each segment. The dimension line crosses the centre line. Moving them outside the part is polish for Nov 27.
19. **Interpreter speed.** The CLI adapter takes about 8 seconds per sentence. This is expected (spec 4a). Speed is measured only with the API adapter.
20. **Tap mapping.** Today tap only accepts a warning. With voice, tap will start and stop listening. Swipe is still free.
21. **Session code on the DONE screen.** The glasses show the last 6 characters of the session id. A real pairing flow (short code → phone page) is still open.

## Added with voice (Nov 23)

22. **STT model.** Default `base.en`: about 1 s per sentence on this laptop CPU, correct on four clean test sentences (computer voice). `small.en` took about 3 s. Not tested yet: a human voice, a noisy workshop, the G2 microphones. Decide the model on real G2.
23. **Silence detection.** The app stops after 1.5 s below a fixed level (RMS 700). The level is a guess. The glasses audio is already processed, so it must be tuned on real G2.
24. **No spoken test in the simulator yet.** The simulator uses the PC microphone. Frames arrive and the silent case works ("I did not hear anything"). A person has to speak to test the full path there.
25. **First STT call is slow.** The Whisper model downloads (about 150 MB) and loads on the first sentence. The server should warm it up at start.

## Added with the API adapter (Nov 23)

26. **Live API run is still open.** The adapter is tested with a fake client and the recorded answers. Needed from Dániel: an `ANTHROPIC_API_KEY` in `.env` (with a spend limit). Then run `INTERPRETER=api pytest -m live` and compare the 14 golden cases and the timing.
27. **No temperature 0.** The spec asks for temperature 0. Current models reject sampling parameters, so none is sent. Stability comes from the strict schema check, thinking off and low effort.
28. **Plain JSON, not tool use.** The spec suggests tool use for structured output. Both adapters return plain JSON that Pydantic validates, so they stay identical. If the live run shows format errors, switch the API adapter to structured outputs (`output_config.format`).
29. **Model choice.** Default `claude-haiku-5-5` for speed and cost. If it guesses instead of asking in the live golden run, try `claude-sonnet-5-5` through `CLAUDE_MODEL`.

## Added with Google Drive (Nov 23)

30. **Real Drive run is still open.** The upload is tested with a fake Drive service. Needed from Dániel: a Google Cloud OAuth client (Desktop app) and one sign-in with `python -m tools.drive_auth` (README, "Google Drive").
31. **OAuth test mode.** While the consent screen is in "Testing", Google ends the sign-in after 7 days. Sign in again close to the demo, or publish the consent screen.
32. **One account for everyone.** The backend uses one Google account. Per-user Drive sign-in through a pairing page is part of "Path to launch", not of the hackathon build.
33. **Upload time.** The upload runs inside `finish`, so `finish` gets slower by the upload time. It is logged (`drive_upload` in the session log). Move it to the background if it is slow on the real account.

## Added with the one-command start (Nov 23)

34. **Docker build is not tested.** Docker Desktop did not finish starting on the dev machine, so `docker compose up --build` has never run. The Dockerfile is written from the known needs (OpenCascade system libraries, speech model inside the image). Test it before the README promise counts.
35. **`start.sh` is not tested.** Only `scripts/start.ps1` ran (Windows): backend and app came up, and a sentence without an API key gave a clear error. The bash script needs a run on macOS or Linux.
36. **Clean-machine test.** Planned for Nov 28: a fresh clone, only the README, on a machine without the dev tools.

## Added with the 3D view on the glasses (Nov 23)

40. **3D view on the glasses.** The glasses have a 3D line view. Swipe turns it in steps (30, 60, 90, 120, 150 degrees). It is a hidden-line drawing made on the server, sent as the same two image tiles as the 2D view.
41. **Speed on real G2.** In the simulator a view change takes about 40 ms. The docs say a full-screen image refresh took about 800 ms on the device. Two tiles are half a screen, so expect about half a second per step. Measure it on real G2. If it is too slow, use fewer steps or one 288 x 144 tile for the 3D view.
42. **No dimensions in the 3D view.** It is for checking the shape. The numbers stay in the 2D view and in the read-back line.
43. **Swipe direction.** Swipe down = next view. Check on real G2 that this feels right on the temple and on the ring.
44. **No 3D viewer on the phone page.** One was built by mistake and removed again. The STEP file can be opened in any CAD viewer.

## Added with guided measuring (Nov 23)

45. **Bare numbers skip the model.** `server/core/guide.py` reads a bare number with strict rules. Two numbers ("thirty forty"), a doubt ("15 or 50") or any other word go to the interpreter as before. Fifteen/fifty can still be misheard by speech recognition. The display shows the value (`Ø50 length?`), and undo drops it.
46. **Listening starts again by itself after a diameter.** The status line shows `Listening…`. It stops after 1.5 s of silence, on a tap, or after 20 s. Check on real G2 that this feels right. If not, remove the one line in `stopListening` in `app/src/main.ts`.
47. **Short words and Whisper.** One-word answers ("sixty") were tested as typed text only. Test them by voice. If recognition is weak, try `STT_MODEL=small.en`.

## Added with the active segment mark (Nov 23)

48. **Thicker lines on the glasses only.** The mark is in the glasses images. The DXF and the PDF do not have it. Check on real G2 that 5 px against 2 px is easy to see. The G2 has 16 grey levels, so a dimmer rest of the part is another option.
49. **After a delete there is no mark.** The deleted segment is gone, so nothing is marked until the next change.

## Added with the quick fix (Nov 23)

50. **"No" alone means undo.** The list of such sentences is short and strict (`is_rejection` in `server/core/guide.py`). "No chamfer" or "no, the second one is 28" still go to the interpreter. Test by voice that Whisper hears a lone "no" well. If not, long press does the same.
51. **Long press on real G2.** The OS uses "tap, then long press" for its own menu (docs/sdk-notes.md). Check that a plain long press reaches the app. In the simulator it does.

## Added with the keyway (Nov 23)

52. **Check the keyway table.** `server/core/keyway.py` holds b, h and t1 for shaft diameters over 6 up to 230 mm (DIN 6885-1, form A). The values were typed from memory of the standard, not copied from a licensed copy. Dániel: compare each row with your copy before the demo.
53. **One keyway per segment, centred, on top.** There is no position along the segment and no angle. The drawing note says "centred". Add an offset only if the demo needs it.
54. **No keyway dimensions as DIMENSION entities.** The sheet has a text note with width, length and depth. There is no section view that shows the depth.
55. **Tolerances are not on the drawing.** The standard also gives fits for the width (P9, N9). They are not shown.

## Added with the mass (Nov 23)

56. **Density table.** `server/core/mass.py` has ten material families with handbook densities. The name match is by pattern ("C45", "1.4301", "6082", "CuZn39Pb3"). Dániel: check the values and add the materials you use. An unknown name gives no mass, never a guess.
57. **The mass is an estimate.** The volume formula agrees with the CAD model within 0.2 % in the tests (the round keyway ends are approximated). The title block says "estimate".

## Added with revisions (Nov 23)

58. **Revision letters.** Each finish of a changed drawing gets the next letter (A, B, ...). The files of every revision are kept in `data/out/<session>/rev_<letter>/`. Google Drive still holds only the newest files. Decide if Drive should keep old revisions too.
59. **Fixed: approval survived a change.** Before this fix, a change after approval kept the "Approved" mark on the next sheet. Now every change (sentence, guided number, undo) sets the drawing back to DRAFT and writes `approval_reset` into the audit log.

## Added with the session token (Nov 23)

60. **Token in the link.** The phone page link has the token as `?k=`. It can show up in server logs and in the browser history. This is fine for the hackathon. For a real launch use a short-lived pairing code that the phone trades for a cookie.
61. **Sessions made before this change have no token.** They cannot be opened any more. Delete `data/sessions` if old test sessions are in the way.
62. **No rate limit.** Nothing stops many wrong tokens or many new sessions. Add a limit before the backend is public for long.
