// Calls to the SayCAD backend. All external calls go through this one server.

export const BACKEND: string = (import.meta.env.VITE_BACKEND_URL as string | undefined) ?? 'http://localhost:8000'

export interface Message {
  code: string
  text: string
  segment: number | null
}

export interface SessionState {
  id: string
  spec: { segments: unknown[]; status: string }
  readback: string
  // Mass estimate. null when the material is not in the density table.
  mass: { kg: number; text: string; material: string; density: number } | null
  validation: { errors: Message[]; warnings: Message[] }
  can_undo: boolean
  finished: boolean
  revision: string | null
  // AI hints for this revision. Shown on the phone page. They are not a check.
  review: { revision: string; notes: string[] } | null
  files: Record<string, string>
  phone_page: string
  views_3d: number[]
  // 1-based: the segment the last change touched. It is drawn with thicker lines.
  active_segment: number | null
  // Guided measuring: what the display asks for next. null when the drawing is finished.
  guide: { segment: number; field: 'diameter' | 'length'; diameter: number | null; text: string } | null
  // "uploading": finish does not wait for Google Drive. Ask again with fetchState until it is "ok" or "error".
  drive: { status: 'uploading' | 'ok' | 'error'; folder_url?: string; message?: string } | null
  heard: string | null
  ask: string | null
  error: string | null
  needs_confirm: boolean
  // True when this call took the last entry back. The app then listens again at once.
  undone: boolean
}

// The server gives a secret token when the session is made. Every later call sends it.
let token = ''
const auth = (): Record<string, string> => (token ? { 'X-Session-Token': token } : {})

async function call(path: string, body?: unknown): Promise<SessionState> {
  const res = await fetch(BACKEND + path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...auth() },
    body: JSON.stringify(body ?? {}),
  })
  if (!res.ok) {
    let detail = `${res.status}`
    try {
      detail = (await res.json()).detail ?? detail
    } catch {
      // keep the status code
    }
    throw new Error(String(detail))
  }
  return res.json()
}

export async function createSession(): Promise<SessionState> {
  const made = (await call('/session')) as SessionState & { token?: string }
  token = made.token ?? ''
  return made
}
export const sendUtterance = (id: string, text: string) => call(`/session/${id}/utterance`, { text })
export const undo = (id: string) => call(`/session/${id}/undo`)
export const finish = (id: string, confirmWarnings: boolean) =>
  call(`/session/${id}/finish`, { confirm_warnings: confirmWarnings })

// The current state, with no change. Used to wait for the Drive upload.
export async function fetchState(id: string): Promise<SessionState> {
  const res = await fetch(`${BACKEND}/session/${id}/spec`, { headers: auth() })
  if (!res.ok) throw new Error(`state failed: ${res.status}`)
  return res.json()
}

// One spoken sentence as a WAV file (16 kHz, 16-bit, mono).
export async function sendAudio(id: string, wav: Uint8Array): Promise<SessionState> {
  const res = await fetch(`${BACKEND}/session/${id}/audio`, {
    method: 'POST',
    headers: { 'Content-Type': 'audio/wav', ...auth() },
    body: wav as unknown as BodyInit,
  })
  if (!res.ok) {
    let detail = `${res.status}`
    try {
      detail = (await res.json()).detail ?? detail
    } catch {
      // keep the status code
    }
    throw new Error(String(detail))
  }
  return res.json()
}

// One 288 x 144 PNG tile of the drawing band. tile 0 = left, 1 = right.
// view = null: the 2D side view. view = degrees: the 3D line view turned by that angle.
export async function fetchTile(id: string, tile: 0 | 1, view: number | null): Promise<Uint8Array> {
  const query = view === null ? `tile=${tile}` : `tile=${tile}&view=${view}`
  const res = await fetch(`${BACKEND}/session/${id}/render?${query}`, { headers: auth() })
  if (!res.ok) throw new Error(`render failed: ${res.status}`)
  return new Uint8Array(await res.arrayBuffer())
}
