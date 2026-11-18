import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Heart, RefreshCw, X } from 'lucide-react'
import { api, ApiError } from '../lib/api'
import { useFlow } from '../flow/FlowContext'
import { mmss, totalMinutes } from '../lib/format'
import type { Analysis } from '../lib/types'
import { Logo } from '../components/Topbar'
import type { Track } from '../lib/types'

function EnergyBars({ energy }: { energy?: number | null }) {
  if (energy == null) return <span className="bars" aria-hidden="true" />
  const on = Math.max(1, Math.round(energy * 6))
  return (
    <span className="bars" role="img" aria-label={`Energy ${on} of 6`}>
      {[0, 1, 2, 3, 4, 5].map(i => <i key={i} className={i < on ? 'on' : ''} style={{ height: 3 + i * 2.2 }} />)}
    </span>
  )
}

export default function SetReview() {
  const nav = useNavigate()
  const { prefs, tracks, setTracks, editingSetId, setPlayed } = useFlow()
  const [favs, setFavs] = useState<Set<string>>(new Set())
  const [busy, setBusy] = useState<number | 'regen' | null>(null)
  const [toast, setToast] = useState('')
  const [cuts, setCuts] = useState<Record<string, Analysis['highlight']>>({})

  useEffect(() => {
    api.favorites().then(r => setFavs(new Set(r.favorites.map(f => f.track_id)))).catch(() => undefined)
  }, [])
  // Estimate each track's cut window in the background (2 at a time). Only tracks whose
  // licence allows segment playback get a cut; others keep their full duration.
  useEffect(() => {
    let live = true
    const queue = tracks.filter(t => t.rights.segment_playback && !t.youtube_id && !(t.id in cuts))
    const worker = async () => {
      for (let t = queue.shift(); t && live; t = queue.shift()) {
        try { const a = await api.analyze(t.id); if (live) setCuts(c => ({ ...c, [t.id]: a.highlight })) }
        catch { if (live) setCuts(c => ({ ...c, [t.id]: null })) }
      }
    }
    void worker(); void worker()
    return () => { live = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tracks])

  useEffect(() => {
    if (!toast) return
    const t = setTimeout(() => setToast(''), 3000)
    return () => clearTimeout(t)
  }, [toast])

  const fail = (e: unknown) => setToast(e instanceof ApiError ? e.message : 'Something went wrong')

  const remove = (i: number) => setTracks(tracks.filter((_, k) => k !== i))

  const replace = async (i: number) => {
    setBusy(i)
    try {
      const r = await api.replace(prefs, tracks, i)
      setTracks(tracks.map((t, k) => (k === i ? r.track : t)))
    } catch (e) { fail(e) } finally { setBusy(null) }
  }

  const regenerate = async () => {
    setBusy('regen')
    try {
      const r = await api.generate(prefs)
      setTracks(r.tracks)
    } catch (e) { fail(e) } finally { setBusy(null) }
  }

  const toggleFav = async (t: Track) => {
    const on = favs.has(t.id)
    setFavs(s => { const n = new Set(s); if (on) n.delete(t.id); else n.add(t.id); return n })
    try { if (on) await api.removeFavorite(t.id); else await api.addFavorite(t) }
    catch (e) {
      setFavs(s => { const n = new Set(s); if (on) n.add(t.id); else n.delete(t.id); return n })
      fail(e)
    }
  }

  return (
    <main className="page">
      <header className="topbar">
        <Logo />
        <div className="top-actions">
          <button className="link-btn" onClick={() => nav('/start')}>← Change answers</button>
          <button className="icon-btn" aria-label="Close" onClick={() => nav('/')}><X size={14} /></button>
        </div>
      </header>

      <h1 className="title display">{editingSetId ? 'Edit set' : 'Tonight’s set'}</h1>
      {tracks.length > 0 && (
        <>
          <p className="sub" style={{ marginBottom: 4 }}>{tracks.length} songs · about {totalMinutes(tracks)} minutes</p>
          <p className="note" style={{ margin: 0 }}>Plays through your browser from licensed catalogue sources. Energy bars appear when a provider supplies tempo data.</p>
        </>
      )}

      {tracks.length === 0 ? (
        <div className="empty">
          <div className="display">No songs to play</div>
          <p>The catalogue returned nothing playable for these answers. Try other languages or genres, or connect another music provider.</p>
          <div style={{ display: 'flex', gap: 10, justifyContent: 'center', flexWrap: 'wrap' }}>
            <button className="btn btn-primary btn-next" onClick={() => nav('/start')}>Change answers</button>
            <button className="btn btn-ghost btn-next" disabled={busy === 'regen'} onClick={() => void regenerate()}>Try again</button>
          </div>
        </div>
      ) : (
        <>
          <ol className="set-list">
            {tracks.map((t, i) => (
              <li key={`${t.id}-${i}`} className="row">
                <button className={`mini fav${favs.has(t.id) ? ' on' : ''}`} aria-label={favs.has(t.id) ? 'Remove favourite' : 'Add favourite'} aria-pressed={favs.has(t.id)} onClick={() => void toggleFav(t)}>
                  <Heart size={14} fill={favs.has(t.id) ? 'currentColor' : 'none'} />
                </button>
                <span className="idx">{i + 1}</span>
                <div className="meta"><div className="t">{t.title}</div><div className="a">{t.artist}</div></div>
                <EnergyBars energy={t.energy} />
                <span className="dur">{cuts[t.id] ? `${mmss(cuts[t.id]!.in_sec)}–${mmss(cuts[t.id]!.out_sec)}` : t.duration_sec ? mmss(t.duration_sec) : '–'}</span>
                <button className="mini" aria-label={`Replace ${t.title}`} disabled={busy !== null} onClick={() => void replace(i)}>
                  <RefreshCw size={14} className={busy === i ? 'spin' : ''} />
                </button>
                <button className="mini" aria-label={`Remove ${t.title}`} onClick={() => remove(i)}><X size={15} /></button>
              </li>
            ))}
          </ol>
          <div style={{ marginTop: 16 }}>
            <button className="link-btn" disabled={busy !== null} onClick={() => void regenerate()}>
              <RefreshCw size={14} /> {busy === 'regen' ? 'Regenerating…' : 'Regenerate set'}
            </button>
          </div>
          <div className="approve-bar">
            <button className="btn btn-primary" onClick={() => { setPlayed([]); nav('/live') }}>Approve &amp; Play</button>
          </div>
        </>
      )}
      {toast && <div className="toast" role="status">{toast}</div>}
    </main>
  )
}
