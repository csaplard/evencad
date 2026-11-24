# Even Hub SDK notes

Written on Nov 23, 2026 (hackathon day 1). Nothing here is guessed.
Each fact has a source tag:

- **[sdk]** `@evenrealities/even_hub_sdk` 0.0.16: README and `dist/index.d.ts`.
- **[cli]** `@evenrealities/evenhub-cli` 0.2.0: README, `--help`, output of `evenhub init`.
- **[sim]** `@evenrealities/evenhub-simulator` 0.9.5: README and `--help`.
- **[docs]** https://hub.evenrealities.com/docs (pages listed at the end).
- **[tpl]** https://github.com/even-realities/evenhub-templates (MIT): `minimal`, `image`, `asr`.
- **[seen]** We ran it ourselves in the simulator on Nov 23.

Not available: the kickoff briefing (not attended) and the DoraHacks page
(it blocks automated reading, HTTP 405). See `open-questions.md`.

## 1. What an app is

- A web page (HTML/TS) that runs in a WebView inside the Even Realities phone app. [docs]
- The page talks to the glasses through a bridge object. [sdk]
- The glasses do **not** render HTML. They render only "containers" that the page asks for. [docs]
- Requirements: SDK 0.0.16, Even App 2.2.10 or later, Node 20+ or 22+. [sdk]

```ts
import { waitForEvenAppBridge } from '@evenrealities/even_hub_sdk'
const bridge = await waitForEvenAppBridge()   // always first
```

## 2. Drawing on the display

### Basics
- 576 × 288 pixels, origin top-left. 4-bit greyscale: 16 levels of green. [docs]
- Three container types only: **text**, **list**, **image**. [docs][sdk]
- `createStartUpPageContainer(...)` must be called once, first. Later layout changes use `rebuildPageContainer(...)`. [sdk][docs]
- Result of create: `0` success, `1` invalid, `2` oversize, `3` out of memory. Rebuild returns a boolean. [sdk]
- Limits per page: `containerTotalNum` 1–12, at most 8 text containers, **at most 4 image containers**. [sdk]
- Each container has `xPosition`, `yPosition`, `width`, `height`, `containerID` (unique), `containerName` (max 16 chars, unique). [sdk][docs]
- `zOrderIndex` is optional. If one container sets it, all must set it, with unique values. Larger = closer to the front. [sdk]
- Exactly one container has `isEventCapture: 1`. It gets the input events. [sdk][docs]

### Text
- Plain text, left/top aligned. One firmware font. No font size, no bold, no alignment, no monospace. [docs]
- `\n` is a line break. Unsupported characters are dropped silently. [docs]
- Length limits: 1,000 chars on create and rebuild, 2,000 on `textContainerUpgrade`. [docs] The simulator caps a text container at 999 bytes. [sim]
- A full screen holds roughly 400–500 characters. [docs]
- `textColor` 0–4 is a brightness level (default 4). The SDK rejects other values. [sdk]
- Border on text and list: `borderWidth` 0–5, `borderColor` 0–15, `borderRadius` 0–10, `paddingLength` 0–32. No fill, no background. [docs]
- Fast text update without rebuild:

```ts
await bridge.textContainerUpgrade(new TextContainerUpgrade({
  containerID: 1, containerName: 'main', content: 'new text',
}))
```
  `containerID` and `containerName` must match exactly. A mismatch does nothing, with no error. [docs]
- Debounce text writes (the `asr` template uses 120 ms): the Bluetooth render queue is slow. [tpl]

### Image (this is how SayCAD draws the shaft)
- An image container is `width` 20–288, `height` 20–144. [sdk] So one image is at most **288 × 144**, a quarter of the screen. [docs]
- An image container cannot capture events. Put a full-screen text container with `content: ' '` and `isEventCapture: 1` behind it. [docs][tpl]
- The image cannot be sent in the create call. Create the container, then call `updateImageRawData`. [sdk][docs]

```ts
const result = await bridge.updateImageRawData(new ImageRawDataUpdate({
  containerID: 3, containerName: 'frame', imageData: pngBytes,
}))
// 'success' | 'imageException' | 'imageSizeInvalid' | 'imageToGray4Failed' | 'sendFailed'
```
- `imageData` type: `number[] | string (base64) | Uint8Array | ArrayBuffer`. [sdk]
- Content of `imageData`: **encoded image bytes (PNG, JPEG)**. The host decodes, resizes and converts to 4-bit grey. This is what the official `image` template does. [tpl] The simulator also accepts raw Gray8 and packed Gray4 since 0.9.2 [sim], but the layout of those raw formats is not documented. We use PNG.
- If the image size differs from the container size, it is resized to cover and centre-cropped. [sim]
- Only one image send at a time. Chain the calls. [docs][tpl] The SDK also paces sends at 100 ms. [docs]
- `success` means "accepted", not "pixels are lit". [docs]
- A full-screen image refresh took about 800 ms in the docs' own test. [docs]
- The simulator is faster than the glasses and does not enforce size limits. [sim]

**Consequence for SayCAD.** There is no pixel-drawing API ("no arbitrary pixel drawing" [docs]).
A drawing is a PNG pushed into an image container. Options:

| Option | Layout | Cost |
|---|---|---|
| A (default) | One image 288 × 144, text containers for status and read-back | 1 image send per change |
| B | Two images side by side, 576 × 144 drawing band, text above and below | 2 sends |
| C | Four images, 2 × 2 tiles = full 576 × 288 | 4 sends, about 800 ms or more |

A shaft is long and flat, so option B fits best. We start with B and measure on real G2.
Tiling is not described in the docs. It follows from the limits above. See `open-questions.md`.

### List
- Up to 20 items, up to 64 characters each (63 bytes in the simulator). [docs][sim]
- No in-place update. Rebuild the page to change a list. [docs]
- Scrolling inside a list is done by the firmware. The app gets `listEvent` with the selected item. [sdk]

### Contextual menu (new in SDK 0.0.14)
- `menuObject: { menuItems: [{ itemName, itemID }] }` on create or rebuild. Max 10 items, `itemID` non-zero and unique, name max 32 UTF-8 bytes. [sdk]
- A choice arrives as `event.menuItemClickEvent.itemID`. [sdk]
- Rebuild without `menuObject` clears the menu. [sdk]

## 3. Input events

All events come through one callback:

```ts
const unsubscribe = bridge.onEvenHubEvent(event => { /* listEvent | textEvent | sysEvent | audioEvent | menuItemClickEvent */ })
```

`OsEventTypeList` [sdk]:

| Name | Value | Meaning |
|---|---|---|
| `CLICK_EVENT` | 0 | single press |
| `SCROLL_TOP_EVENT` | 1 | swipe up / list reached the top |
| `SCROLL_BOTTOM_EVENT` | 2 | swipe down / list reached the bottom |
| `DOUBLE_CLICK_EVENT` | 3 | double press |
| `FOREGROUND_ENTER_EVENT` | 4 | app comes to the front |
| `FOREGROUND_EXIT_EVENT` | 5 | app leaves the front |
| `ABNORMAL_EXIT_EVENT` | 6 | abnormal exit |
| `SYSTEM_EXIT_EVENT` | 7 | system exit |
| `IMU_DATA_REPORT` | 8 | IMU sample |
| `LONG_PRESS_EVENT` | 9 | long press starts |
| `LONG_PRESS_RELEASE_EVENT` | 10 | long press ends |

Sources, `EventSourceType` [sdk]: `1` right temple, `2` **R1 ring**, `3` left temple.
The temple touchpads and the ring send the same gestures. [docs]
`sysEvent.eventSource` tells which one it was. [sdk] The simulator always reports `1`. [sim]

Rules we must follow:

1. **A single tap has no `eventType`.** `CLICK_EVENT` is 0 and the wire format drops zero values. Read the type *inside* the envelope: `envelope.eventType ?? CLICK_EVENT`, and only if the envelope exists. [tpl]
   [seen]: a click arrived as `{"sysEvent":{"eventSource":1}}`.
2. Taps and double taps arrive in `sysEvent`. Swipes arrive in `textEvent` (when a text container captures). [tpl]
   [seen]: swipe down arrived as `{"textEvent":{"containerID":1,"containerName":"main","eventType":2}}`.
   Check both envelopes for double tap, so the user can always exit. [tpl]
3. **Double tap on the root page must call `bridge.shutDownPageContainer(1)`** (the system exit dialog). Mode `0` (exit at once) is not accepted by review. [docs]
   So double tap is reserved. SayCAD cannot use it for "undo".
4. Long press comes as two `sysEvent`s (start and release). The OS uses "tap, then long press" for its own menu. Treat long press as an extra, not as the only way. [docs]
5. No capture container → input is dropped silently. [docs][sim]
6. Do not listen for DOM `click`. [docs]

Free gestures for SayCAD: tap, swipe up, swipe down, long press (hold-to-talk fits well), contextual menu.
The final mapping is decided on real G2 and goes into the README.

Simulator inputs: Up, Down, Click, Double Click, Long Press, Long Press Release, Context Menu. [sim]

## 4. Microphone audio

```ts
await bridge.audioControl(true, AudioInputSource.Glasses)   // or AudioInputSource.Phone
bridge.onEvenHubEvent(e => { const pcm = e.audioEvent?.audioPcm /* Uint8Array */ })
await bridge.audioControl(false)
```

- Format: **PCM, 16 kHz, signed 16-bit little-endian, mono**. [docs] The simulator sends 100 ms per event = 3,200 bytes. [sim]
- Glasses mic needs the start-up page first, else `audioControl` returns `false`. [sdk]
- `audioEvent` also has `source`, `direction` (raw tag, may be `null`) and `speakerRole` (`self` / `other` / `unknown`, an app-side guess). [sdk]
- `app.json` needs the permission `g2-microphone` (or `phone-microphone` for the phone mic). [docs]
- There is no audio output. [docs]
- If Android suspends the WebView, audio stops. Turn it on again when the app returns to the front. [docs]
- The simulator uses the PC microphone (`--list-audio-input-devices`, `--aid`). [sim]

Plan: collect the PCM frames in the page, add a WAV header, POST to our backend. No streaming needed for one utterance.

## 5. app.json, network whitelist, CORS

`evenhub init` (CLI 0.2.0) writes this [cli]:

```json
{
  "package_id": "com.example.g2demo",
  "edition": "202601",
  "name": "G2 Demo",
  "version": "0.1.0",
  "min_app_version": "2.2.10",
  "min_sdk_version": "0.0.16",
  "entrypoint": "index.html",
  "permissions": [
    { "name": "network", "desc": "This app needs to access the network in order to ...", "whitelist": ["https://example.com"] },
    { "name": "location", "desc": "This app needs to access the location in order to ..." }
  ],
  "supported_languages": ["en"]
}
```

Field rules [docs]:

| Field | Rule |
|---|---|
| `package_id` | reverse domain, at least two parts, lowercase letters and digits, each part starts with a letter, no hyphens |
| `edition` | must be `"202601"` |
| `name` | max 20 characters. **Must not contain "Even"** (any case) |
| `version` | `x.y.z`, no `v`, no suffix |
| `min_app_version` | optional. `pack` stamps it from the SDK version [cli] |
| `min_sdk_version` | required string |
| `entrypoint` | must exist in the build folder |
| `permissions` | array of objects, may be `[]` |
| `supported_languages` | from: `en de fr es it zh ja ko`. **No `hu`.** |

Permission names: `network`, `location`, `g2-microphone`, `phone-microphone`, `album`, `camera`.
Each needs `desc` (1–300 chars). Only `network` has `whitelist`. [docs]
Declare only what the app uses. Unused permissions are flagged at review. [docs]

Network whitelist [docs]:
- One entry per **full origin**, for example `https://api.example.com`. No bare hostnames. No wildcards.
- HTTPS in production. Plain `http://` is only for a dev server on the LAN.
- The Even app checks the whitelist before the request leaves the WebView.

CORS [docs]:
- The whitelist does **not** replace CORS. The WebView (Chromium on Android, WKWebView on iOS) still does the normal browser check.
- The server must answer with `Access-Control-Allow-Origin: *` (or the WebView origin, which the docs do not name).
- JSON bodies and custom headers cause a preflight. The server must answer `OPTIONS` with `Access-Control-Allow-Methods` and `Access-Control-Allow-Headers`.
- A third-party API without CORS must go through our own server.

For SayCAD: one whitelist entry, our backend origin. FastAPI gets `CORSMiddleware`.
The backend needs a public **HTTPS** address for the real G2 test (see `open-questions.md`).

Storage: `bridge.setLocalStorage(key, value)` / `getLocalStorage(key)` survive restarts. [sdk][docs]

## 6. Dev loop and packaging

```bash
npm run dev                                      # Vite on port 5173
evenhub-simulator http://localhost:5173           # simulator; the URL is required [seen]
evenhub qr --url http://<LAN-IP>:5173             # real glasses: scan in the Even app (developer mode)
npm run build
evenhub pack app.json dist -o saycad.ehpk        # package
```

- QR sideload stops when the phone app goes to the background. Lock-screen tests need a beta build. [docs]
- Permission prompts are skipped in dev mode. [docs]
- `pack` options: `-o`, `--check` (is the package id free), `--sdk-ver`, `--no-ignore`. [cli]
- The `.ehpk` can be unpacked by anyone. Never put secrets in it. [docs]
- Upload flow: `evenhub login` (interactive, by hand) → `evenhub create out.ehpk --name ... --tagline ... --icon icon.png` → `evenhub upload` → `evenhub promote <ver> --to beta` → `evenhub testers add <email>`. Public release needs review in the portal. [cli]
- Icon: PNG 24 × 24, every pixel transparent or `#F4F4F4`, lit pixels in 2 × 2 blocks. [cli]

Simulator automation (used by our checks) [sim]:

```bash
evenhub-simulator http://localhost:5173 --automation-port 9898
curl http://127.0.0.1:9898/api/ping
curl -o shot.png http://127.0.0.1:9898/api/screenshot/glasses
curl http://127.0.0.1:9898/api/console
curl -X POST -H 'Content-Type: application/json' -d '{"action":"click"}' http://127.0.0.1:9898/api/input
# actions: up, down, click, double_click, long_press, long_press_release, context_menu
```

## 7. Lifecycle and limits

- iOS keeps the WebView running in the background. Android may suspend it. Audio and WebSockets can stop. [docs]
- After exit, the phone-side WebView closes. [docs]
- First run must never show a black screen. [docs]
- The simulator is not an emulator. Fonts, timing and list scrolling differ from the glasses. Test on real G2. [sim]
- Not offered by the SDK: direct Bluetooth, pixel drawing, audio output, text alignment, font control, background colours, animations. [docs]

## 8. What we checked ourselves on Nov 23 [seen]

- Node 26.4.0, CLI 0.2.0 and simulator 0.9.5 install and run on Windows 11.
- The official `minimal` template runs in the simulator. `createStartUpPageContainer` returned success.
- Changed text shows on the display (`docs/img/sim-hello.png`).
- Click → tap counter updates (`docs/img/sim-tap.png`). Swipe up/down → text updates (`docs/img/sim-swipe.png`).

## Doc pages read

`/docs`, `/docs/get-started/quickstart/first-app`, `/docs/get-started/quickstart/templates`,
`/docs/build/display`, `/docs/build/device-apis`, `/docs/build/networking`,
`/docs/build/page-lifecycle`, `/docs/build/background-lifecycle`,
`/docs/test/simulator`, `/docs/test/local-testing`,
`/docs/ship/packaging`, `/docs/ship/app-submission`, `/docs/cli/index`, `/docs/cli/project`.

Not read yet: hardware / developer-mode page, design guidelines, contextual-menu page, beta testing, FAQ.
