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
