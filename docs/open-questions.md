# Open questions

Each item has a safe default. We work with the default until we know more.

## Needs an answer from Dániel

1. **App name.** The store rule says the name must not contain "Even". "EvenCAD" breaks this rule.
   Default: `app.json` uses `"name": "ShaftCAD Draft"`. Repo and project name stay EvenCAD for now. Please pick a final name. **Done on Nov 24: the name is SayCAD (see 100).**
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

## Added with the AI hints (Nov 23)

63. **Hints run in the background.** The finish does not wait for them. With the Claude CLI adapter one review took about 50 s in a test. With the API it should take a few seconds, but this was not measured (no API key on this machine). Reload the phone page to see the hints.
64. **Hints are not on the glasses and not on the drawing.** AI text is kept off the sheet on purpose. Decide if one hint line on the glasses would help.
65. **Quality of the hints.** Two samples were looked at by hand. They were sensible but a bit generic ("chamfers are not mentioned"). Tune `REVIEW_PROMPT` in `server/ai/reviewer.py` after real use.

## Independent code review (Nov 23, evening)

A second agent reviewed the code of the day. It found 14 issues. All are fixed, each with a test in `tests/test_review_fixes.py`.

66. **Fixed: approval with a blank name.** The name is trimmed first and must have two characters.
67. **Fixed: "no" could delete the wrong thing.** With a question or a warning prompt on the display, "no" or "cancel" now only dismisses it. "Undo" always undoes.
68. **Fixed: a bare number after a question.** It now goes to the model together with the first sentence and the question, in the form `first sentence [you asked: question] answer`. The app listens for the answer at once.
69. **Fixed: the keyway could sit on a chamfer.** It is centred on the cylindrical part between the chamfers.
70. **Fixed: an approved revision could be overwritten.** A finish after an approval reset always gets a new letter.
71. **Fixed in the app:** the microphone cannot open while the app is in the background, two quick taps cannot open it twice, a failed call no longer starts listening again, a failed image send is sent again.
72. **Fixed: density table.** "Aluminium bronze", "1.6082", "S316", "S235JR", "C45E", "GG25" and others now match the right family or none.
73. **Fixed: smaller items.** A non-ASCII token gives 401, not 500. Session files are written in one step. One call at a time per session. Finish drops a half-entered diameter. "25?" is not read as a number.
74. **Still open from the review.** The token is in `?k=` links, so it is in access logs (item 60). The session lock is in memory, so it works for one server process only.
75. **Auto-listen after a question is new.** Check on real G2 that it feels right. A model that keeps asking would keep the microphone cycle going until the user is silent for 20 s or taps.

## Added on Nov 24: fit limits, fillet, undercut, Hungarian

76. **Check the fit table.** `server/core/fits.py` has the ISO 286 values (IT5 to IT11, letters d e f g h js k m n p r s, up to 500 mm). They were typed in from memory. 33 well known values are in `tests/test_fits.py`. An engineer must compare the whole table with the standard before anyone relies on a drawing.
77. **Fits outside the table** (for example j6, or grades below IT5) stay a text note with no numbers. This is on purpose: nothing is guessed.
78. **The undercut is a plain rectangular groove.** It is not a DIN 509 form E or F undercut. The sheet note says "plain groove". Decide if the standard shapes are needed.
79. **Fillet only at a shoulder.** A rounded outer edge of a shaft end is not built. The model is told to ask for a step.
80. **A fillet or undercut has no dimension of its own on the sheet.** The size is in a note at the top left ("Fillet R2 at step 1"). A leader with the radius would look better.
81. **Deleting or inserting a segment drops the fillet or undercut at that joint.** The shoulder they were made for is gone. The user sees this in the read-back. Chamfers at a step are not dropped the same way (older behaviour).
82. **Hungarian speech was not tried with a voice.** Only text was tested: the number parser (about 70 cases) and 11 recorded model answers. `STT_LANGUAGE=hu` needs the `small` Whisper model (about 460 MB download, slower than `base.en`). Its speed and accuracy on this laptop are not measured.
83. **Hungarian: the display stays English.** "Next: segment 2 diameter?" and the model questions are English. The glasses font was not checked for ő and ű, so the model is told to ask in English without accents.
84. **Hungarian number words that sound alike:** "hat" (6) and "hét" (7), "négy" (4) and "negyven" (40), "öt" (5) and "ötven" (50). The read-back shows the value at once and "nem" takes it back. Check with real speech how often this happens.
85. **Docker image and Hungarian.** The Dockerfile downloads the model named by the build argument `STT_MODEL` (default `base.en`). For Hungarian build with `--build-arg STT_MODEL=small`.

## Added on Nov 24: first run on the real Anthropic API

86. **The API works with `claude-haiku-5-5`.** 39 recorded sentences, three runs each: 117 of 117 right. Median 0.54 s per call, slowest 1.3 s.
87. **The small model sometimes writes a note before the JSON.** The parser now takes the JSON object at the end of the text. The object is checked in full as before.
88. **Two prompt rules were made sharper for the small model:** with exactly one step it must not ask "which step", and a fit or roughness with no segment named must be asked, not put on the last segment.
89. **`claude-sonnet-5-5` gave "API error 400" with the same request.** The reason was not looked into. The adapter is tuned for the small model only.
90. **The first import of the Anthropic SDK took 7 s on the dev laptop.** The server now imports it (and CadQuery) in the background at start, when `STT_WARMUP=1`.
91. **Live tests do not read `.env`.** The values must be in the shell (see the README, "Tests").

## Added on Nov 24: first run with a real Google Drive

92. **Drive upload works with a real account.** `finish` made a sub-folder with `shaft.step`, `shaft.dxf`, `shaft.pdf`. The approval replaced the DXF and the PDF in place (same files, new versions).
93. **`finish` with the upload is slow.** 14 s on the first run in a fresh process. About 6 s of it is the three uploads, one after the other. The rest is the first import of CadQuery, which the warm-up now does at start. Done later on Nov 24: the upload runs in the background (see 95).
94. **The folder id line is easy to miss.** `tools.drive_auth` prints it, but the user must copy it into `.env`. On the dev machine it was missing after the sign-in. The tool could write it into `.env` itself.

## Added on Nov 24: upload in the background

95. **`finish` does not wait for Google Drive.** Measured with a real Drive and a warm server: `finish` answers in 1.0 s, the upload is done 6 s later. The state says `uploading`, then `ok` or `error`. The glasses app asks the server every 1.5 s, for 60 s at most. This was not seen in the simulator or on real glasses yet, only type-checked.
96. **The approval still waits for its upload** (about 4 s on the phone page). The output files of one session have a lock: they are not rewritten while an upload reads them.
97. **The phone page does not refresh by itself.** While the upload runs it says "Google Drive: uploading… Reload the page in a moment."
98. **An AI hint that is too long is dropped, the other hints stay.** Before, one long hint threw away all hints of that run (seen once with the real API).
99. **Store name.** The rule is in the Even Hub docs (`docs/sdk-notes.md`): the app `name` must not contain "Even". `app.json` uses "ShaftCAD Draft". The repo, the README and the submission still say "EvenCAD". Pick one final name before the submission.

## Added on Nov 24: new name

100. **The project is now called SayCAD.** Dániel chose it. Everything was renamed: the app name in `app.json`, the package id (`com.csaplard.saycad`), the display texts, the spec file (`SAYCAD_SPEC.md`), the docs and the GitHub repository. Older entries in this file still say "EvenCAD"; they are history.
101. **The name was not checked against trademarks.** One quick web search found no product called SayCAD. That is not a legal check.
102. **The Google Drive folder of the dev account is still called "EvenCAD drawings".** It works, because the server uses the folder id. New installs get "SayCAD drawings". Rename the old folder by hand if it will be in the video.
103. **The variable `EVENCAD_SKIP_DOTENV` is now `SAYCAD_SKIP_DOTENV`.** Only tests and scripts use it.

## Added on Nov 24: first try with a human voice

104. **An old `ANTHROPIC_API_KEY` in the Windows user variables beat the key in `.env`.** The first spoken test ended with "Anthropic API key is missing or not valid". Now a value in `.env` wins, and the log names what was replaced. The old Windows variable is still there; Dániel can delete it.
105. **"Thirty." was understood from a human voice** and taken without the model. The next spoken entry went to the model and hit the key error, so what was heard is not known: a failed model call does not log the heard text.

## Added on Nov 28: the app did not hear the laptop microphone

106. **The fixed speech level (RMS 700) was too high for a laptop microphone array.** The app waited and showed nothing, or "I did not hear anything". Now the level follows the room noise (speech = 3 times louder than the quiet frames). A tap to stop always sends the recording, and the server checks for speech. "I did not hear anything" now shows the loudest level. Not tested with a human voice after the change. The level of the real G2 microphone is not known.
107. **"Thirty, thirty." (the same number two times) goes to the model**, and the model asks "Diameter and length? One segment at a time." This is correct, but it came from a repeat, because the app did not react to the first word.
108. **Second voice try (Nov 28): the app heard the voice, but the talk went in circles.** Found and changed: (a) "20, and 30." and "Fourty and fifty." went to the model, which asked back. Now two numbers with a joining word (and, by, x, times, és) make a segment when a diameter is asked. No model call. (b) After "I did not hear anything" the app listened again by itself, heard the room, and asked again. Now it waits for a tap. (c) The recording is quiet (level near 139 of 32768). The server now makes a quiet recording louder before the speech check. Wrong texts like "What a people." and "Empty." came from such recordings. Not tested again with a human voice.
109. **Third voice try (Nov 28): the old server was still running**, so the changes of item 108 were not active. `start.ps1` now stops an older run on its ports first. The recogniser (base.en) heard "Venti" for "twenty" from a Hungarian accent. A bigger model (STT_MODEL=small.en) or Hungarian speech (STT_LANGUAGE=hu) may help; not measured. New prompt rule: a new command after a question ("we are done") is done by itself, and the old question is dropped. Checked with the real model, 14 of 14 calls.
110. **Speech model on the dev machine is now `small.en`** (set in `.env`; the default in the code stays `base.en`). Measured on this laptop CPU with a computer voice: base.en 1.0 s, small.en 3.1 s for a 2 s phrase. Both heard the three test phrases right. Whether small.en hears a Hungarian accent better is not tested yet.
111. **Fourth voice try (Nov 28): three sentences in 90 seconds.** The server heard them nearly right ("Diameter thirty, length fifty."), but the app was slow to notice speech and its end. The noise level in the app was a plain minimum; one silent frame made every later frame "speech", so the recording ran to the 20 s limit. Now the noise level is the quietest tenth of the last 4 seconds. Checked with made-up levels only (8 cases). Each recording now writes its level numbers (noise, peak, first speech second, length, heard text) into the session log. No sound is kept.
112. **`start.ps1 -Glasses`** sets the backend address to the Wi-Fi address of the PC and shows the QR code. Not tested on real G2. Open: does the QR dev mode enforce the `whitelist` of `app.json` (it has only `http://localhost:8000`)?
113. **Demo video made by tools (Nov 28).** `tools/demo_record.py` sends 15 spoken lines (computer voice, ElevenLabs) through the real server; `tools/demo_video.py` draws the video from the answers. With `base.en` all 15 lines were heard right, about 1 s for a number and about 2 s for a sentence (speech to text plus Claude). `small.en` heard the same and took about 3 s. The video is not a recording of the glasses or of the simulator, and it says so. Each recording run uploads two revisions to the Drive folder: test folders pile up there.
114. **Demo video, second cut (Nov 28).** The voice is now an AI voice made from the voice of Dániel (ElevenLabs). One of 15 lines was heard wrong with it ("diameter ninety, ten long" became "ninety-ten long", and the model asked back); the line was said again as "Diameter ninety, length ten." A turning 3D model made from `revA.step` was added. The small line at the bottom of the video was taken out at the wish of Dániel; the notes about what is real are in `demo/README.md` and on the end card.
