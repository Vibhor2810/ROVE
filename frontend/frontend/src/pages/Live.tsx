import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Pause, Play, RotateCcw, Search, X } from 'lucide-react'
import { api } from '../lib/api'
import { useFlow } from '../flow/FlowContext'
import type { PlayedEntry } from '../flow/FlowContext'
import { DjEngine } from '../audio/DjEngine'
import { CircularVisualizer } from '../components/CircularVisualizer'
import { Modal } from '../components/Modal'
import { mmss, prefChips } from '../lib/format'
import type { Analysis, Authorization, PlaySource, Track } from '../lib/types'

interface Cue { inSec: number; outSec: number | null; mode: 'segment' | 'full'; estimated: boolean }
const FADE_SEC = 3
const FALLBACK_SEGMENT = 75

const upper = (s: string) => s.toUpperCase()

export default function Live() {
  const nav = useNavigate()
  const { tracks: approved, prefs, setPlayed } = useFlow()

  const [queue, setQueue] = useState<Track[]>(approved)
  const [idx, setIdx] = useState(0)
  const [cue, setCue] = useState<Cue | null>(null)
  const [time, setTime] = useState(0)
  const [dur, setDur] = useState(0)
  const [paused, setPaused] = useState(false)
  const [agent, setAgent] = useState('Plugging in')
  const [loading, setLoading] = useState(true)
  const [confirmEnd, setConfirmEnd] = useState(false)
  const [showNext, setShowNext] = useState(false)
  const [deck, setDeck] = useState<'A' | 'B'>('A')
  const [playedTracks, setPlayedTracks] = useState<Track[]>([])

  const engine = useRef<DjEngine | null>(null)
  const queueRef = useRef(approved)
  const idxRef = useRef(0)
  const cueRef = useRef<Cue | null>(null)
  const pausedRef = useRef(false)
  const advancing = useRef(false)
  const entries = useRef<PlayedEntry[]>([])
  const authCache = useRef(new Map<string, Promise<Authorization | null>>())
  const analysisCache = useRef(new Map<string, Promise<Analysis | null>>())
  const session = useRef(0)
  const ytHost = useRef<HTMLDivElement | null>(null)
  const noticeRef = useRef('')
  const startedCount = useRef(0)

  const record = useCallback((e: PlayedEntry) => {
    entries.current.push(e)
    setPlayedTracks(entries.current.map(x => x.track))
  }, [])

  const getAuth = useCallback((t: Track) => {
    let p = authCache.current.get(t.id)
    if (!p) { p = api.authorize(t.id).catch(() => null); authCache.current.set(t.id, p) }
    return p
  }, [])
  const getAnalysis = useCallback((t: Track) => {
    let p = analysisCache.current.get(t.id)
    if (!p) { p = api.analyze(t.id).catch(() => null); analysisCache.current.set(t.id, p) }
    return p
  }, [])
  const withTimeout = <T,>(p: Promise<T>, ms: number): Promise<T | null> =>
    Promise.race([p, new Promise<null>(r => setTimeout(() => r(null), ms))])

  const finish = useCallback(() => {
    session.current++
    engine.current?.stop()
    setPlayed(entries.current)
    nav('/done', { replace: true })
  }, [nav, setPlayed])

  const fadeFor = (a: Track | undefined, b: Track | undefined) =>
    a && b && a.rights.crossfade && b.rights.crossfade ? FADE_SEC : 0

  const playFrom = useCallback(async (from: number, how: 'start' | 'transition', fade: number) => {
    const my = ++session.current
    const eng = engine.current
    if (!eng) return
    let k = from
    while (k < queueRef.current.length) {
      const t = queueRef.current[k]
      const auth = await getAuth(t)
      if (my !== session.current) return
      const source: PlaySource | null = auth?.source ?? null
      if (!auth || !auth.playable || !source) {
        record({ track: t, skipped: true, mode: 'full' })
        noticeRef.current = upper(`${t.title} isn't available, moving on`)
        setAgent(noticeRef.current)
        k++
        continue
      }
      const isYt = source.kind === 'youtube'
      const a = isYt ? null : await withTimeout(getAnalysis(t), how === 'start' ? 3500 : 1200)
      if (my !== session.current) return
      const segOk = auth.allowed.segment
      const seekOk = auth.allowed.seek
      let nextCue: Cue
      if (isYt) {
        nextCue = { inSec: 0, outSec: null, mode: 'full', estimated: false }
      } else if (segOk) {
        const h = a?.highlight
        nextCue = h
          ? { inSec: seekOk ? h.in_sec : 0, outSec: h.out_sec, mode: 'segment', estimated: true }
          : { inSec: 0, outSec: FALLBACK_SEGMENT, mode: 'segment', estimated: false }
      } else {
        nextCue = { inSec: 0, outSec: null, mode: 'full', estimated: false }
      }
      try {
        if (how === 'start') await eng.start(source, nextCue.inSec)
        else await eng.transitionTo(source, nextCue.inSec, fade)
      } catch (e) {
        if (my !== session.current) return
        if (e instanceof DOMException && e.name === 'NotAllowedError') {
          pausedRef.current = true; setPaused(true)
          setAgent('TAP RESUME TO START')
        } else {
          record({ track: t, skipped: true, mode: 'full' })
          noticeRef.current = upper(isYt ? `${t.title} is blocked on YouTube, moving on` : `${t.title} failed to load, moving on`)
          setAgent(noticeRef.current)
          k++
          how = 'transition'
          continue
        }
      }
      if (my !== session.current) return
      idxRef.current = k; setIdx(k)
      startedCount.current++; setDeck(startedCount.current % 2 === 1 ? 'A' : 'B')
      cueRef.current = nextCue; setCue(nextCue)
      setDur(eng.duration() || t.duration_sec || 0); setTime(eng.time())
      setLoading(false)
      advancing.current = false
      if (noticeRef.current) {
        setAgent(noticeRef.current); noticeRef.current = ''
      } else if (!pausedRef.current) {
        setAgent(isYt ? 'PLAYING FULL TRACK FROM YOUTUBE' : nextCue.mode === 'segment'
          ? (nextCue.estimated ? upper(`Cutting at ${mmss(nextCue.outSec)}, holding the energy`) : 'PLAYING FROM THE TOP, ANALYSIS NOT READY')
          : 'PLAYING THE FULL TRACK')
      }
      const nxt = queueRef.current[k + 1]
      if (nxt) {
        void getAuth(nxt).then(au => { if (au?.source?.kind === 'audio') eng.preload(au.source.url) })
        if (!nxt.youtube_id) void getAnalysis(nxt)
      }
      return
    }
    finish()
  }, [finish, getAnalysis, getAuth, record])

  const advance = useCallback((reason: 'skip' | 'auto' | 'error') => {
    if (advancing.current) return
    advancing.current = true
    const cur = queueRef.current[idxRef.current]
    const next = queueRef.current[idxRef.current + 1]
    if (cur) {
      record({ track: cur, skipped: reason !== 'auto', mode: cueRef.current?.mode ?? 'full' })
      if (reason === 'auto') void api.logPlay(cur, cueRef.current?.mode ?? 'full', true).catch(() => undefined)
    }
    if (!next) { finish(); return }
    if (reason === 'skip') setAgent(upper(`Skipped ${cur?.title ?? 'song'}, bringing in ${next.title}`))
    if (reason === 'error') { noticeRef.current = upper(`${cur?.title ?? 'That song'} stopped working on YouTube, bringing in ${next.title}`); setAgent(noticeRef.current) }
    const fade = reason === 'error' ? 0 : reason === 'skip' ? Math.min(1.5, fadeFor(cur, next)) : fadeFor(cur, next)
    void playFrom(idxRef.current + 1, 'transition', fade)
  }, [finish, playFrom, record])

  useEffect(() => {
    if (approved.length === 0) { nav('/review', { replace: true }); return }
    const sess = session
    const eng = new DjEngine()
    engine.current = eng
    eng.onEnded = () => advance('auto')
    eng.onError = () => setAgent('AUDIO HICCUP, MOVING ON')
    eng.onUnavailable = () => advance('error')
    if (ytHost.current) eng.setYtHost(ytHost.current)
    entries.current = []
    void playFrom(0, 'start', 0)
    return () => { sess.current++; eng.stop(); engine.current = null }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const hasYt = queue.some(t => !!t.youtube_id)
  useEffect(() => { if (hasYt && ytHost.current) engine.current?.setYtHost(ytHost.current) }, [hasYt])

  useEffect(() => {
    const id = setInterval(() => {
      const eng = engine.current
      if (!eng || pausedRef.current || advancing.current) return
      const t = eng.time()
      setTime(t)
      const d = eng.duration()
      if (d && d !== dur) setDur(d)
      const c = cueRef.current
      const cur = queueRef.current[idxRef.current]
      const nxt = queueRef.current[idxRef.current + 1]
      if (!c || !cur) return

      if (c.mode === 'segment' && c.outSec != null) {
        const fade = fadeFor(cur, nxt)
        if (c.outSec > 0 && t >= c.outSec - fade) {
          advance('auto')
        }
      }
    }, 250)
    return () => clearInterval(id)
  }, [advance, dur])

  const togglePause = useCallback(async () => {
    const eng = engine.current
    if (!eng || loading) return
    if (pausedRef.current) {
      pausedRef.current = false; setPaused(false)
      try { await eng.resume(); setAgent('BACK ON. RESUME PICKS UP EXACTLY HERE') }
      catch { pausedRef.current = true; setPaused(true) }
    } else {
      await eng.pause(); pausedRef.current = true; setPaused(true)
      setAgent(upper(`Paused at ${mmss(eng.time())}. Resume picks up exactly here`))
    }
  }, [loading])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (showNext) return
      const el = e.target as HTMLElement
      if (el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA')) return
      if (e.code === 'Space') { e.preventDefault(); void togglePause() }
      if (e.key.toLowerCase() === 's' && !pausedRef.current) advance('skip')
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [advance, showNext, togglePause])

  useEffect(() => {
    if (!confirmEnd) return
    const t = setTimeout(() => setConfirmEnd(false), 3000)
    return () => clearTimeout(t)
  }, [confirmEnd])

  const cur = queue[idx]
  const nextTrack = queue[idx + 1]
  const deckName = deck
  const full = cue?.mode === 'full'
  const canPlayFull = !!cue && cue.mode === 'segment'
  const chips = useMemo(() => prefChips(prefs), [prefs])

  const playFull = () => {
    const eng = engine.current
    if (!cue || cue.mode === 'full') return
    const startedMidSong = cue.inSec > 2 && (eng?.time() ?? 0) >= cue.inSec - 1
    const c: Cue = { ...cue, inSec: 0, outSec: null, mode: 'full', estimated: false }
    cueRef.current = c
    setCue(c)
    if (eng && startedMidSong) {
      eng.seek(0)
      setTime(0)
      setAgent('PLAYING COMPLETE TRACK FROM 0:00')
    } else {
      setAgent('LETTING IT RIDE, FULL TRACK')
    }
  }

  const seekTo = (sec: number) => {
    const eng = engine.current
    if (!eng || dur <= 0) return
    const clamped = Math.max(0, Math.min(sec, Math.max(0, dur - 0.25)))
    if (cue && cue.mode === 'segment') {
      const inSec = clamped
      const outSec = Math.min(dur, Math.max(cue.outSec ?? dur, inSec + 30))
      const c: Cue = { ...cue, inSec, outSec, estimated: false }
      cueRef.current = c
      setCue(c)
    }
    eng.seek(clamped)
    setTime(clamped)
  }

  const restartTrack = () => {
    const eng = engine.current
    if (!eng || loading) return
    eng.seek(0)
    setTime(0)
    if (cue) {
      const c: Cue = { ...cue, inSec: 0 }
      cueRef.current = c
      setCue(c)
    }
    setAgent('RESTARTED FROM 0:00')
  }

  const removeNext = () => {
    if (!nextTrack) return
    const q = queueRef.current.filter((_, i) => i !== idxRef.current + 1)
    queueRef.current = q; setQueue(q)
    setAgent(upper(`Removed ${nextTrack.title} from the set`))
  }

  const insertNext = (t: Track) => {
    const q = queueRef.current.filter((x, i) => !(x.id === t.id && i > idxRef.current))
    q.splice(idxRef.current + 1, 0, t)
    queueRef.current = q; setQueue(q)
    setAgent(upper(`Your pick: ${t.title} plays next`))
    setShowNext(false)
  }

  const endParty = () => {
    if (!confirmEnd) { setConfirmEnd(true); return }
    const c = queueRef.current[idxRef.current]
    if (c) record({ track: c, skipped: false, mode: cueRef.current?.mode ?? 'full' })
    finish()
  }

  if (!cur) return <div className="loading-screen"><div className="spinner" /></div>

  return (
    <main className={`live${paused ? ' is-paused' : ''}`} aria-label="RØVE Live">
      <div className="glow" />
      {cur.artwork_url && <div className="art" style={{ backgroundImage: `url(${cur.artwork_url})` }} aria-hidden="true" />}

      <div className="live-top">
        <span className="logo">RØVE</span>
        <div className="chips" aria-label="Set settings">
          {chips.join(' · ')}<button onClick={() => nav('/start')}>CHANGE</button>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {confirmEnd && <span className="end-confirm" role="status">End party? Tap again</span>}
          <button className="icon-btn" aria-label="Restart track" title="Restart track" onClick={restartTrack} disabled={loading}>
            <RotateCcw size={14} />
          </button>
          <button className={`timer-pill${paused ? ' paused' : ''}`} onClick={() => void togglePause()} aria-label={paused ? 'Resume' : 'Pause'}>
            {paused ? <Play size={18} fill="currentColor" /> : <Pause size={18} fill="currentColor" />}
            {mmss(time)} / {mmss(dur)}
          </button>
          <button className="icon-btn" aria-label="End party" onClick={endParty}><X size={14} /></button>
        </div>
      </div>

      {paused && !loading && (
        <button onClick={() => void togglePause()} aria-label="Resume" style={{ position: 'absolute', inset: 0, zIndex: 4, cursor: 'pointer' }}>
          <span className="paused-word">Paused</span>
          <span className="paused-at">At {mmss(time)} · Space or tap to resume</span>
        </button>
      )}

      <div className={`stage${hasYt ? ' has-yt' : ''}`}>
        <div>
          <div className="deck-label">Deck {deckName} <span className="live-dot" /> <b>Live{full ? ' · Full' : ''}</b></div>
          <h1 className="song display">{cur.title}</h1>
          <div className="artist">{cur.artist}</div>
          <CircularVisualizer
            engine={engine.current}
            deck={deckName}
            duration={dur}
            time={time}
            inSec={cue?.mode === 'segment' ? cue.inSec : 0}
            outSec={cue?.mode === 'segment' ? cue.outSec : null}
            paused={paused}
            mode={cue?.mode ?? 'full'}
            onSeek={seekTo}
          />
        </div>
        <div className="side">
          {hasYt && (
            <div className={`yt-tile${cur.youtube_id ? '' : ' idle'}`} aria-label="YouTube player">
              <div ref={ytHost} className="yt-host" />
            </div>
          )}
          <aside className="next-deck" aria-label="Up next">
            {nextTrack ? (<>
              <div className="deck-label">Deck {deckName === 'A' ? 'B' : 'A'} · Cueing</div>
              <div className="n-title">{nextTrack.title}</div>
              <div className="n-artist">{nextTrack.artist}</div>
            </>) : <div className="deck-label">Last song</div>}
          </aside>
        </div>
      </div>

      <div className="agent" aria-live="polite">
        <span className="who">Agent</span>
        <span className="msg">{agent}</span>
        <button className="pill" onClick={removeNext} disabled={!nextTrack}><X size={11} /> Remove next</button>
        <button className="pill accent" onClick={() => setShowNext(true)}><Search size={11} /> Play next</button>
      </div>

      {paused ? (
        <div className="live-actions single">
          <button className="btn btn-primary" onClick={() => void togglePause()}><Play size={34} fill="currentColor" /> Resume</button>
        </div>
      ) : (
        <div className="live-actions">
          <button className="btn btn-primary" onClick={() => advance('skip')} disabled={loading}>Skip</button>
          <button className={`btn btn-ghost${full ? ' btn-full-on' : ''}`} onClick={playFull} disabled={loading || (!canPlayFull && !full)} aria-pressed={full}>
            {full ? 'Playing full' : 'Play full'}
          </button>
        </div>
      )}

      {showNext && <PlayNext played={playedTracks} upcoming={queue.slice(idx + 1, idx + 6)} onPick={insertNext} onClose={() => setShowNext(false)} />}
    </main>
  )
}

function PlayNext({ played, upcoming, onPick, onClose }: { played: Track[]; upcoming: Track[]; onPick: (t: Track) => void; onClose: () => void }) {
  const [q, setQ] = useState('')
  const [results, setResults] = useState<Track[] | null>(null)
  const [err, setErr] = useState('')

  useEffect(() => {
    if (q.trim().length < 2) return
    let live = true
    const id = setTimeout(() => {
      api.search(q.trim()).then(r => { if (live) { setResults(r.tracks); setErr('') } })
        .catch(() => live && setErr('Search unavailable'))
    }, 300)
    return () => { live = false; clearTimeout(id) }
  }, [q])

  const Row = ({ t, label }: { t: Track; label: string }) => (
    <div className="res">
      <div><div className="rt">{t.title}</div><div className="ra">{t.artist}</div></div>
      <button className="pill accent" onClick={() => onPick(t)}>{label}</button>
    </div>
  )
  const uniquePlayed = played.filter((t, i, a) => a.findIndex(x => x.id === t.id) === i).slice(-4)

  return (
    <Modal title="Play next" onClose={onClose}>
      <input className="search" autoFocus placeholder="Search a song or artist" value={q} onChange={e => setQ(e.target.value)} aria-label="Search a song or artist" />
      <div className="res-scroll">
        {err && <p className="err">{err}</p>}
        {q.trim().length >= 2 && results ? (
          results.length ? results.map(t => <Row key={t.id} t={t} label="Play next" />) : <p className="note">No playable matches.</p>
        ) : (<>
          {upcoming.length > 0 && <div className="res-label">Coming up</div>}
          {upcoming.map(t => <Row key={t.id} t={t} label="Play next" />)}
          {uniquePlayed.length > 0 && <div className="res-label">Played tonight</div>}
          {uniquePlayed.map(t => <Row key={t.id} t={t} label="Play it again" />)}
        </>)}
      </div>
    </Modal>
  )
}


