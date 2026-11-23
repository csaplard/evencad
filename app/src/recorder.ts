// Collects microphone frames for one utterance and builds a WAV file.
// The glasses send PCM: 16 kHz, signed 16-bit little-endian, mono (docs/sdk-notes.md).
// Nothing is stored. The frames live in memory until the WAV is sent.

const SAMPLE_RATE = 16000
const BYTES_PER_SECOND = SAMPLE_RATE * 2
const MAX_SECONDS = 20 // hard stop
const SILENCE_SECONDS = 1.5 // stop this long after the speech ends
const SPEECH_LEVEL = 700 // RMS of int16 samples that counts as speech

export class Recorder {
  private chunks: Uint8Array[] = []
  private bytes = 0
  private heardSpeech = false
  private quietBytes = 0

  /** Add one frame. Returns true when the recording should stop by itself. */
  add(pcm: Uint8Array): boolean {
    this.chunks.push(pcm)
    this.bytes += pcm.length
    if (rms(pcm) >= SPEECH_LEVEL) {
      this.heardSpeech = true
      this.quietBytes = 0
    } else {
      this.quietBytes += pcm.length
    }
    if (this.bytes >= MAX_SECONDS * BYTES_PER_SECOND) return true
    return this.heardSpeech && this.quietBytes >= SILENCE_SECONDS * BYTES_PER_SECOND
  }

  get seconds(): number {
    return this.bytes / BYTES_PER_SECOND
  }

  get hasSpeech(): boolean {
    return this.heardSpeech
  }

  /** Build the WAV and forget the frames. */
  finish(): Uint8Array {
    const wav = new Uint8Array(44 + this.bytes)
    const view = new DataView(wav.buffer)
    const text = (offset: number, s: string) => [...s].forEach((c, i) => view.setUint8(offset + i, c.charCodeAt(0)))
    text(0, 'RIFF')
    view.setUint32(4, 36 + this.bytes, true)
    text(8, 'WAVE')
    text(12, 'fmt ')
    view.setUint32(16, 16, true) // fmt chunk size
    view.setUint16(20, 1, true) // PCM
    view.setUint16(22, 1, true) // mono
    view.setUint32(24, SAMPLE_RATE, true)
    view.setUint32(28, BYTES_PER_SECOND, true)
    view.setUint16(32, 2, true) // block align
    view.setUint16(34, 16, true) // bits per sample
    text(36, 'data')
    view.setUint32(40, this.bytes, true)
    let offset = 44
    for (const chunk of this.chunks) {
      wav.set(chunk, offset)
      offset += chunk.length
    }
    this.chunks = []
    this.bytes = 0
    return wav
  }
}

function rms(pcm: Uint8Array): number {
  const view = new DataView(pcm.buffer, pcm.byteOffset, pcm.byteLength - (pcm.byteLength % 2))
  const n = view.byteLength / 2
  if (n === 0) return 0
  let sum = 0
  for (let i = 0; i < n; i++) {
    const s = view.getInt16(i * 2, true)
    sum += s * s
  }
  return Math.sqrt(sum / n)
}
