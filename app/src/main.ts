import {
  waitForEvenAppBridge,
  TextContainerProperty,
  ImageContainerProperty,
  ImageRawDataUpdate,
  CreateStartUpPageContainer,
  TextContainerUpgrade,
  OsEventTypeList,
} from '@evenrealities/even_hub_sdk'
import { BACKEND, createSession, fetchTile, finish, sendUtterance, undo } from './api'
import type { SessionState } from './api'

// ── Glasses page layout (576 x 288) ──────────────────────────────────────
//   y   0.. 44  status line: what was heard, a question, or an error
//   y  48..192  drawing: two image tiles of 288 x 144 (the largest allowed)
//   y 196..288  read-back, first warning, key hint
// A full-screen text container sits behind everything and captures input,
// because image containers cannot capture events (docs/sdk-notes.md).
const EVENTS = { id: 1, name: 'events' }
const STATUS = { id: 2, name: 'status' }
const INFO = { id: 3, name: 'info' }
const TILES = [
  { id: 4, name: 'tile-left' },
  { id: 5, name: 'tile-right' },
]

const bridge = await waitForEvenAppBridge()

const created = await bridge.createStartUpPageContainer(
  new CreateStartUpPageContainer({
    containerTotalNum: 5,
    textObject: [
      new TextContainerProperty({
        xPosition: 0, yPosition: 0, width: 576, height: 288,
        containerID: EVENTS.id, containerName: EVENTS.name, zOrderIndex: 1,
        borderWidth: 0, paddingLength: 0, content: ' ', isEventCapture: 1,
      }),
      new TextContainerProperty({
        xPosition: 0, yPosition: 0, width: 576, height: 44,
        containerID: STATUS.id, containerName: STATUS.name, zOrderIndex: 2,
        borderWidth: 0, paddingLength: 4, content: 'EvenCAD · connecting…', isEventCapture: 0,
      }),
      new TextContainerProperty({
        xPosition: 0, yPosition: 196, width: 576, height: 92,
        containerID: INFO.id, containerName: INFO.name, zOrderIndex: 3,
        borderWidth: 0, paddingLength: 4, content: ' ', isEventCapture: 0,
      }),
    ],
    imageObject: TILES.map((t, i) =>
      new ImageContainerProperty({
        xPosition: i * 288, yPosition: 48, width: 288, height: 144,
        containerID: t.id, containerName: t.name, zOrderIndex: 4 + i,
      }),
    ),
  }),
)
console.log('Page created:', created === 0 ? 'success' : `failed (${created})`)

// ── Display writes ───────────────────────────────────────────────────────
// Text writes and image sends go through one queue. Images must never
// overlap, and the Bluetooth link is slow.
let queue: Promise<unknown> = Promise.resolve()
function enqueue(job: () => Promise<unknown>) {
  queue = queue.then(job).catch(err => console.error('display write failed:', err))
  return queue
}

const shown: Record<string, string> = {}
function setText(target: { id: number; name: string }, content: string) {
  if (shown[target.name] === content) return
  shown[target.name] = content
  enqueue(() =>
    bridge.textContainerUpgrade(
      new TextContainerUpgrade({ containerID: target.id, containerName: target.name, content: content || ' ' }),
    ),
  )
}

function pushDrawing(id: string) {
  enqueue(async () => {
    const t0 = performance.now()
    for (const [i, tile] of TILES.entries()) {
      const bytes = await fetchTile(id, i as 0 | 1)
      const result = await bridge.updateImageRawData(
        new ImageRawDataUpdate({ containerID: tile.id, containerName: tile.name, imageData: bytes }),
      )
      if (result !== 'success') console.error('updateImageRawData:', tile.name, result)
    }
    console.log(`drawing pushed in ${Math.round(performance.now() - t0)} ms`)
  })
}

// ── App state ────────────────────────────────────────────────────────────
let state: SessionState | null = null
let lastDrawn = ''
let busy = false

function show(next: SessionState) {
  state = next
  const { ask, error, heard, needs_confirm, finished, validation } = next

  let status = heard ? `"${heard}"` : 'EvenCAD · ready'
  if (ask) status = `? ${ask}`
  else if (error) status = `! ${error}`
  setText(STATUS, status)

  const lines = [next.readback]
  const problem = validation.errors[0] ?? validation.warnings[0]
  if (problem) lines.push(`${validation.errors.length ? 'Error' : 'Warning'}: ${problem.text}`)
  if (needs_confirm) lines.push('Tap to accept the warning and finish')
  else if (finished) lines.push(`DRAFT files ready · code ${next.id.slice(-6)}`)
  setText(INFO, lines.join('\n'))

  const drawingKey = JSON.stringify(next.spec.segments)
  if (drawingKey !== lastDrawn) {
    lastDrawn = drawingKey
    pushDrawing(next.id)
  }
  renderPhone()
}

async function run(label: string, action: () => Promise<SessionState>) {
  if (busy) return
  busy = true
  setText(STATUS, label)
  try {
    show(await action())
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err)
    console.error(label, message)
    setText(STATUS, `! ${message}`.slice(0, 60))
    logLine(`Error: ${message}`)
  } finally {
    busy = false
  }
}

const say = (text: string) => run(`"${text}" …`, () => sendUtterance(state!.id, text))

// ── Glasses input ────────────────────────────────────────────────────────
// CLICK_EVENT is 0 and zero values are dropped on the wire, so a tap has no
// eventType. Resolve the default inside the envelope check only.
function eventTypeOf(envelope?: { eventType?: OsEventTypeList }): OsEventTypeList | null {
  if (!envelope) return null
  return envelope.eventType ?? OsEventTypeList.CLICK_EVENT
}

const unsubscribe = bridge.onEvenHubEvent(event => {
  const sysType = eventTypeOf(event.sysEvent)
  const textType = eventTypeOf(event.textEvent)

  // Double tap on the root page must open the system exit dialog.
  if (sysType === OsEventTypeList.DOUBLE_CLICK_EVENT || textType === OsEventTypeList.DOUBLE_CLICK_EVENT) {
    bridge.shutDownPageContainer(1)
    return
  }

  if (sysType === OsEventTypeList.CLICK_EVENT || textType === OsEventTypeList.CLICK_EVENT) {
    // Tap = confirm. Today it confirms a warning. Later it also starts listening.
    if (state?.needs_confirm) run('Finishing…', () => finish(state!.id, true))
    return
  }

  if (sysType === OsEventTypeList.SYSTEM_EXIT_EVENT || sysType === OsEventTypeList.ABNORMAL_EXIT_EVENT) {
    unsubscribe()
  }
})

// ── Phone-side page: typed text instead of voice (development fallback) ──
const app = document.querySelector<HTMLDivElement>('#app')!
app.innerHTML = `
  <main>
    <h1>EvenCAD</h1>
    <p class="muted">Typed text stands in for voice. The drawing is on the glasses.</p>
    <form id="say">
      <input id="text" autocomplete="off" placeholder="diameter thirty, forty long" />
      <button>Send</button>
    </form>
    <p>
      <button id="undo" type="button">Undo</button>
      <button id="finish" type="button">Finish</button>
    </p>
    <p id="readback"></p>
    <p id="links"></p>
    <pre id="log"></pre>
  </main>
`
const input = app.querySelector<HTMLInputElement>('#text')!
const logBox = app.querySelector<HTMLPreElement>('#log')!

function logLine(text: string) {
  logBox.textContent = `${text}\n${logBox.textContent ?? ''}`.slice(0, 2000)
}

function renderPhone() {
  if (!state) return
  app.querySelector('#readback')!.textContent = state.readback
  const links = app.querySelector('#links')!
  links.innerHTML = state.finished ? `<a href="${BACKEND}${state.phone_page}" target="_blank">Open the files page</a>` : ''
  if (state.ask) logLine(`? ${state.ask}`)
  else if (state.error) logLine(`! ${state.error}`)
  else if (state.heard) logLine(`✓ ${state.heard}`)
}

app.querySelector<HTMLFormElement>('#say')!.addEventListener('submit', ev => {
  ev.preventDefault()
  const text = input.value.trim()
  if (!text || !state) return
  input.value = ''
  say(text)
})
app.querySelector('#undo')!.addEventListener('click', () => state && run('Undo…', () => undo(state!.id)))
app.querySelector('#finish')!.addEventListener('click', () => state && run('Finishing…', () => finish(state!.id, false)))

await run('EvenCAD · connecting…', createSession)

// Development hook: http://localhost:5173/?say=first sentence|second sentence
// sends the sentences one by one. It lets a script drive the simulator.
const scripted = import.meta.env.DEV ? new URLSearchParams(location.search).get('say') : null
for (const sentence of scripted?.split('|') ?? []) {
  if (state && sentence.trim()) await say(sentence.trim())
}
