// Calls to the EvenCAD backend. All external calls go through this one server.

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
  validation: { errors: Message[]; warnings: Message[] }
  can_undo: boolean
  finished: boolean
  files: Record<string, string>
  phone_page: string
  drive: { status: 'ok' | 'error'; folder_url?: string; message?: string } | null
  heard: string | null
  ask: string | null
  error: string | null
  needs_confirm: boolean
}

async function call(path: string, body?: unknown): Promise<SessionState> {
  const res = await fetch(BACKEND + path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
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

export const createSession = () => call('/session')
export const sendUtterance = (id: string, text: string) => call(`/session/${id}/utterance`, { text })
export const undo = (id: string) => call(`/session/${id}/undo`)
export const finish = (id: string, confirmWarnings: boolean) =>
  call(`/session/${id}/finish`, { confirm_warnings: confirmWarnings })

// One spoken sentence as a WAV file (16 kHz, 16-bit, mono).
export async function sendAudio(id: string, wav: Uint8Array): Promise<SessionState> {
  const res = await fetch(`${BACKEND}/session/${id}/audio`, {
    method: 'POST',
    headers: { 'Content-Type': 'audio/wav' },
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
export async function fetchTile(id: string, tile: 0 | 1): Promise<Uint8Array> {
  const res = await fetch(`${BACKEND}/session/${id}/render?tile=${tile}`)
  if (!res.ok) throw new Error(`render failed: ${res.status}`)
  return new Uint8Array(await res.arrayBuffer())
}
