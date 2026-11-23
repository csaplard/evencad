# Feature requests for Even Hub

Up to 5 items go into the submission. This is a working list.
Each item comes from a real limit we met. Details are in `docs/sdk-notes.md`.

## Candidates (day 1)

1. **A full-screen image container, or a documented way to tile.**
   One image container is at most 288 × 144 and a page holds four. A technical drawing wants the full 576 × 288. Today that means four sends, one after another.

2. **Document the raw image formats.**
   The simulator accepts raw Gray8 and packed Gray4, but the byte layout is not written down. A documented raw format would let apps skip PNG encoding and keep exact grey levels.

3. **A small vector API (lines, rectangles, text at x/y).**
   Line drawings are tiny as vectors and large as bitmaps. A few draw calls would make live drawings faster over Bluetooth.

4. **Text size and alignment in text containers.**
   One fixed font, left/top only. Dimension numbers and status lines need at least two sizes and right or centre alignment.

5. **Document the WebView origin.**
   The docs ask for CORS headers, but do not name the origin of the app. Servers must answer with `*`. A known origin would allow a strict CORS rule.

## Maybe

- A reliable push-to-talk gesture: long press is partly used by the OS menu.
- `hu` in `supported_languages`.
