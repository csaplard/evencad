// Collects microphone frames for one utterance and builds a WAV file.
// The glasses send PCM: 16 kHz, signed 16-bit little-endian, mono (docs/sdk-notes.md).
// Nothing is stored. The frames live in memory until the WAV is sent.

const SAMPLE_RATE = 16000
const BYTES_PER_SECOND = SAMPLE_RATE * 2
const MAX_SECONDS = 20 // hard stop
const SILENCE_SECONDS = 1.5 // stop this long after the speech ends
// Speech level (RMS of int16 samples). Microphones differ a lot, so the level follows the room noise.
// The noise level is the level of the quietest tenth of the last 4 seconds. A frame is speech when it
// is 2.5 times louder. One silent frame or one click does not move this level (a plain minimum did:
// then every frame was "speech" and the recording ran for the full 20 seconds).
const MIN_LEVEL = 40 // never speech below this
const OVER_NOISE = 2.5
const WINDOW_SECONDS = 4
const WARM_UP_SECONDS = 0.3 // too little sound to know the noise level

export class Recorder {
  private chunks: Uint8Array[] = []
  private bytes = 0
  private heardSpeech = false
  private quietBytes = 0
  private levels: { level: number; bytes: number }[] = [] // the last 4 seconds
  private levelBytes = 0
  private noise = 0
  private peak = 0
  private speechAt = -1 // second of the first speech frame

  /** Add one frame. Returns true when the recording should stop by itself. */
  add(pcm: Uint8Array): boolean {
    this.chunks.push(pcm)
    this.bytes += pcm.length
    const level = rms(pcm)
    this.peak = Math.max(this.peak, level)
    this.levels.push({ level, bytes: pcm.length })
    this.levelBytes += pcm.length
    while (this.levelBytes - this.levels[0].bytes >= WINDOW_SECONDS * BYTES_PER_SECOND) {
      this.levelBytes -= this.levels.shift()!.bytes
    }
    const sorted = this.levels.map(l => l.level).sort((a, b) => a - b)
    this.noise = sorted[Math.floor(sorted.length / 10)]
    const warm = this.bytes >= WARM_UP_SECONDS * BYTES_PER_SECOND
    const speechLevel = Math.max(MIN_LEVEL, this.noise * OVER_NOISE)
    // A person who speaks at once has no quiet start. Then the speech shows later, when the room is
    // quiet again: the loud tenth of the window is far over the new noise level.
    const loud = sorted[Math.floor(sorted.length * 0.9)]
    if (warm && !this.heardSpeech && loud >= speechLevel) {
      this.speechAt = this.seconds
      this.heardSpeech = true
      this.quietBytes = 0 // the silence is counted from here
    }
    if (warm && level >= speechLevel) {
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

  /** The loudest frame so far. Shown when nothing was heard, to help with a quiet microphone. */
  get peakLevel(): number {
    return Math.round(this.peak)
  }

  /** Numbers about the sound level, for the server log. No sound is in them. */
  get stats(): Record<string, string> {
    return {
      noise: String(Math.round(this.noise)),
      peak: String(this.peakLevel),
      speech_at: this.speechAt.toFixed(1),
      frames: String(this.chunks.length),
    }
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
