/**
 * Wrapper around the OFFICIAL YouTube IFrame Player API.
 * The player must stay visible on screen (YouTube requires >= 200x200), and we only
 * use documented controls: load/seek/pause/play/stop. No stream extraction anywhere.
 */
interface YtPlayer {
  loadVideoById(o: { videoId: string; startSeconds?: number }): void
  playVideo(): void; pauseVideo(): void; stopVideo(): void
  seekTo(sec: number, allowSeekAhead: boolean): void
  getCurrentTime(): number; getDuration(): number; getPlayerState(): number
  destroy(): void
}
interface YtNamespace {
  Player: new (el: HTMLElement, opts: {
    width: string | number; height: string | number
    playerVars: Record<string, string | number>
    events: { onReady: () => void; onStateChange: (e: { data: number }) => void; onError: (e: { data: number }) => void }
  }) => YtPlayer
}
declare global { interface Window { YT?: YtNamespace; onYouTubeIframeAPIReady?: () => void } }

const ENDED = 0, PLAYING = 1, BUFFERING = 3

let apiPromise: Promise<YtNamespace> | null = null
function loadApi(): Promise<YtNamespace> {
  if (window.YT?.Player) return Promise.resolve(window.YT)
  if (!apiPromise) {
    apiPromise = new Promise<YtNamespace>((resolve, reject) => {
      const prev = window.onYouTubeIframeAPIReady
      window.onYouTubeIframeAPIReady = () => { prev?.(); if (window.YT) resolve(window.YT) }
      const s = document.createElement('script')
      s.src = 'https://www.youtube.com/iframe_api'
      s.onerror = () => { apiPromise = null; reject(new Error('YouTube player could not load (blocked or offline)')) }
      document.head.appendChild(s)
      setTimeout(() => { if (!window.YT?.Player) { apiPromise = null; reject(new Error('YouTube player timed out')) } }, 12000)
    })
  }
  return apiPromise
}

export class YtDeck {
  private player: YtPlayer | null = null
  private ready: Promise<YtPlayer> | null = null
  private pending: { resolve: () => void; reject: (e: Error) => void } | null = null
  onEnded: (() => void) | null = null
  /** Fired when a video dies mid-play (removed, blocked, embedding disabled). */
  onUnavailable: (() => void) | null = null
  active = false
  private host: HTMLElement

  constructor(host: HTMLElement) { this.host = host }

  private init(): Promise<YtPlayer> {
    if (!this.ready) {
      this.ready = loadApi().then(YT => new Promise<YtPlayer>((resolve) => {
        const mount = document.createElement('div')
        this.host.appendChild(mount)
        const p = new YT.Player(mount, {
          width: '100%', height: '100%',
          playerVars: { playsinline: 1, controls: 0, disablekb: 1, rel: 0, modestbranding: 1, enablejsapi: 1, origin: window.location.origin },
          events: {
            onReady: () => { this.player = p; resolve(p) },
            onStateChange: e => {
              if (e.data === PLAYING && this.pending) { this.pending.resolve(); this.pending = null }
              if (e.data === ENDED && this.active) this.onEnded?.()
            },
            onError: e => {
              const err = new Error(`YouTube cannot play this video (code ${e.data})`)
              if (this.pending) { this.pending.reject(err); this.pending = null }
              else if (this.active) this.onUnavailable?.()
            },
          },
        })
      }))
      this.ready.catch(() => { this.ready = null })
    }
    return this.ready
  }

  async start(videoId: string, startAt = 0): Promise<void> {
    const p = await this.init()
    this.active = true
    await new Promise<void>((resolve, reject) => {
      this.pending = { resolve, reject }
      p.loadVideoById({ videoId, startSeconds: Math.max(0, startAt) })
      setTimeout(() => {
        if (!this.pending) return
        this.pending = null
        const st = p.getPlayerState()
        // -1 unstarted / 5 cued after a load request = the browser blocked autoplay, not a bad video.
        if (st === -1 || st === 5) reject(new DOMException('autoplay blocked', 'NotAllowedError'))
        else if (st === BUFFERING) reject(new Error('YouTube timed out buffering'))
        else reject(new Error('YouTube did not start'))
      }, 15000)
    })
  }

  time() { return this.player?.getCurrentTime() ?? 0 }
  duration() { return this.player?.getDuration() ?? 0 }
  seek(sec: number) { this.player?.seekTo(Math.max(0, sec), true) }
  pause() { this.player?.pauseVideo() }
  resume() { this.active = true; this.player?.playVideo() }
  stop() { this.active = false; this.pending = null; try { this.player?.stopVideo() } catch { /* player gone */ } }
  isPaused() { const s = this.player?.getPlayerState(); return s !== PLAYING && s !== BUFFERING }
}
