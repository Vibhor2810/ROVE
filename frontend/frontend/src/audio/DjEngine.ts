/**
 * Two-deck playback engine built on HTMLAudioElement + shared Web Audio AnalyserNode.
 *
 * Crossfades ramp deck GainNodes (when Web Audio is attached) and element volume
 * so both CORS-enabled streams (with live FFT visualization) and non-CORS fallback
 * streams play reliably.
 */
import { YtDeck } from './YtDeck'
import type { PlaySource } from '../lib/types'

export type DeckId = 0 | 1

export class DjEngine {
  private decks: [HTMLAudioElement, HTMLAudioElement]
  private active: DeckId = 0
  private fadeRaf = 0
  private fading = false
  private yt: YtDeck | null = null
  private kind: 'audio' | 'yt' = 'audio'

  // Shared Web Audio graph for real-time visualization
  private ctx: AudioContext | null = null
  private analyser: AnalyserNode | null = null
  private sources: [MediaElementAudioSourceNode | null, MediaElementAudioSourceNode | null] = [null, null]
  private gains: [GainNode | null, GainNode | null] = [null, null]
  private freqBuf: Uint8Array | null = null
  private webAudioBroken = false

  onEnded: (() => void) | null = null
  onError: ((message: string) => void) | null = null
  /** A YouTube video became unavailable mid-play. */
  onUnavailable: (() => void) | null = null

  /** Give the engine the visible element the YouTube player will live in. */
  setYtHost(el: HTMLElement) {
    if (this.yt) return
    this.yt = new YtDeck(el)
    this.yt.onEnded = () => { if (this.kind === 'yt') this.onEnded?.() }
    this.yt.onUnavailable = () => { if (this.kind === 'yt') this.onUnavailable?.() }
  }

  constructor() {
    const make = () => {
      const a = new Audio()
      a.preload = 'auto'
      a.crossOrigin = 'anonymous'
      return a
    }
    this.decks = [make(), make()]
    this.decks.forEach((d, i) => {
      d.addEventListener('ended', () => { if (i === this.active) this.onEnded?.() })
      d.addEventListener('error', () => { if (i === this.active) this.onError?.('Audio failed to load') })
    })
  }

  /** Lazily initialize and resume the shared AudioContext + AnalyserNode. */
  private ensureAudioGraph() {
    if (this.webAudioBroken) return
    try {
      if (!this.ctx) {
        const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext
        if (!AudioCtx) {
          this.webAudioBroken = true
          return
        }
        const ctx = new AudioCtx()
        const analyser = ctx.createAnalyser()
        analyser.fftSize = 256
        analyser.smoothingTimeConstant = 0.8
        analyser.minDecibels = -85
        analyser.maxDecibels = -15
        analyser.connect(ctx.destination)

        this.ctx = ctx
        this.analyser = analyser
        this.freqBuf = new Uint8Array(analyser.frequencyBinCount)

        this.decks.forEach((el, idx) => {
          const src = ctx.createMediaElementSource(el)
          const gain = ctx.createGain()
          gain.gain.value = 1
          src.connect(gain)
          gain.connect(analyser)
          this.sources[idx] = src
          this.gains[idx] = gain
        })
      }
      if (this.ctx.state === 'suspended') {
        void this.ctx.resume().catch(() => undefined)
      }
    } catch {
      this.webAudioBroken = true
    }
  }

  /** Populates and returns live FFT frequency bins (0..255), or null when unavailable (e.g. YouTube). */
  getFrequencyData(): Uint8Array | null {
    if (this.kind !== 'audio' || !this.analyser || !this.freqBuf || this.paused()) return null
    this.analyser.getByteFrequencyData(this.freqBuf)
    return this.freqBuf
  }

  /** True when Web Audio FFT data is available for the active source. */
  isAudioAnalyzable(): boolean {
    return this.kind === 'audio' && !this.webAudioBroken
  }

  /** True while an active deck-to-deck crossfade is in progress. */
  isTransitioning(): boolean {
    return this.fading
  }

  private setDeckLevel(id: DeckId, level: number) {
    const clamped = Math.max(0, Math.min(1, level))
    const g = this.gains[id]
    if (g && this.ctx) {
      g.gain.setValueAtTime(clamped, this.ctx.currentTime)
      this.decks[id].volume = 1
    } else {
      this.decks[id].volume = clamped
    }
  }

  private get cur() { return this.decks[this.active] }

  time(): number { return this.kind === 'yt' ? this.yt?.time() ?? 0 : this.cur.currentTime || 0 }
  duration(): number {
    if (this.kind === 'yt') return this.yt?.duration() ?? 0
    return Number.isFinite(this.cur.duration) ? this.cur.duration : 0
  }
  paused(): boolean { return this.kind === 'yt' ? this.yt?.isPaused() ?? true : this.cur.paused }
  seek(sec: number) {
    if (this.kind === 'yt') { this.yt?.seek(sec); return }
    try {
      const maxSeek = Number.isFinite(this.cur.duration) && this.cur.duration > 0 ? this.cur.duration : sec
      this.cur.currentTime = Math.max(0, Math.min(sec, maxSeek))
    } catch { /* not seekable yet */ }
  }

  private cancelFade() {
    cancelAnimationFrame(this.fadeRaf)
    this.fadeRaf = 0
    this.fading = false
  }

  private async load(el: HTMLAudioElement, url: string, startAt: number) {
    el.crossOrigin = 'anonymous'
    el.src = url
    await new Promise<void>((resolve, reject) => {
      const ok = () => { cleanup(); resolve() }
      const bad = () => { cleanup(); reject(new Error('load failed')) }
      const cleanup = () => { el.removeEventListener('loadedmetadata', ok); el.removeEventListener('error', bad) }
      el.addEventListener('loadedmetadata', ok, { once: true })
      el.addEventListener('error', bad, { once: true })
      el.load()
    })
    if (startAt > 0) el.currentTime = startAt
  }

  /** Cut straight to a track (either source). */
  async start(src: PlaySource, startAt = 0): Promise<void> {
    this.cancelFade()
    if (src.kind === 'youtube') {
      if (!this.yt) throw new Error('YouTube player is not mounted')
      this.decks.forEach((d, idx) => { d.pause(); this.setDeckLevel(idx as DeckId, 1) })
      this.kind = 'yt'
      await this.yt.start(src.id, startAt)
      return
    }
    this.yt?.stop()
    this.kind = 'audio'
    this.ensureAudioGraph()
    await this.startAudio(src.url, startAt)
  }

  private async startAudio(url: string, startAt: number): Promise<void> {
    const otherId: DeckId = this.active === 0 ? 1 : 0
    this.decks[otherId].pause()
    this.setDeckLevel(this.active, 1)
    this.setDeckLevel(otherId, 1)
    await this.load(this.cur, url, startAt)
    await this.cur.play()
  }

  /** Bring the next track in on the other deck, fading this one out. fadeSec 0 = hard cut. */
  async transitionTo(src: PlaySource, startAt: number, fadeSec: number): Promise<void> {
    if (src.kind === 'youtube' || this.kind === 'yt') {
      this.cancelFade()
      this.decks.forEach((d, idx) => { d.pause(); this.setDeckLevel(idx as DeckId, 1) })
      this.yt?.stop()
      await this.start(src, startAt)
      return
    }
    this.ensureAudioGraph()
    const url = src.url
    this.cancelFade()
    const outId = this.active
    const inId: DeckId = this.active === 0 ? 1 : 0
    const outgoing = this.decks[outId]
    const incoming = this.decks[inId]

    this.setDeckLevel(inId, fadeSec > 0 ? 0 : 1)
    await this.load(incoming, url, startAt)
    await incoming.play()
    this.active = inId

    if (fadeSec <= 0) {
      outgoing.pause()
      this.setDeckLevel(outId, 1)
      return
    }

    this.fading = true
    const t0 = performance.now()
    const step = () => {
      const k = Math.min(1, (performance.now() - t0) / (fadeSec * 1000))
      this.setDeckLevel(inId, k)
      this.setDeckLevel(outId, 1 - k)
      if (k < 1) {
        this.fadeRaf = requestAnimationFrame(step)
      } else {
        outgoing.pause()
        this.setDeckLevel(outId, 1)
        this.fadeRaf = 0
        this.fading = false
      }
    }
    this.fadeRaf = requestAnimationFrame(step)
  }

  /** Pre-buffer the next track on the idle deck so transitions are gapless. */
  preload(url: string) {
    const idle = this.decks[this.active === 0 ? 1 : 0]
    if (idle.paused && idle.getAttribute('src') !== url) {
      idle.crossOrigin = 'anonymous'
      idle.src = url
      idle.load()
    }
  }

  async pause() {
    if (this.kind === 'yt') { this.yt?.pause(); return }
    this.cancelFade()
    const idleId: DeckId = this.active === 0 ? 1 : 0
    this.decks[idleId].pause()
    this.setDeckLevel(idleId, 1)
    this.setDeckLevel(this.active, 1)
    this.cur.pause()
  }

  async resume() {
    if (this.kind === 'yt') { this.yt?.resume(); return }
    this.ensureAudioGraph()
    await this.cur.play()
  }

  stop() {
    this.yt?.stop()
    this.cancelFade()
    this.decks.forEach((d, idx) => {
      d.pause()
      d.removeAttribute('src')
      d.load()
      this.setDeckLevel(idx as DeckId, 1)
    })
  }
}
