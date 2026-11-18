import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Heart, Pencil, Play, Trash2 } from 'lucide-react'
import { api, ApiError } from '../lib/api'
import { useAuth } from '../auth/AuthContext'
import { useFlow } from '../flow/FlowContext'
import { Logo } from '../components/Topbar'
import { totalMinutes } from '../lib/format'
import type { SavedSet, Track } from '../lib/types'

export default function MySets() {
  const nav = useNavigate()
  const { signOut, email } = useAuth()
  const { setPrefs, setTracks, setEditingSetId, setPlayed, reset } = useFlow()
  const [sets, setSets] = useState<SavedSet[] | null>(null)
  const [favs, setFavs] = useState<{ track_id: string; track: Track }[] | null>(null)
  const [recent, setRecent] = useState<{ track_id: string; track: Track; played_at: string }[] | null>(null)
  const [err, setErr] = useState('')

  useEffect(() => {
    let live = true
    Promise.all([api.listSets(), api.favorites(), api.recent()]).then(([s, f, r]) => {
      if (!live) return
      setSets(s.sets); setFavs(f.favorites); setRecent(r.recent)
    }).catch(e => {
      if (!live) return
      setErr(e instanceof ApiError ? e.message : 'Could not load your library')
      setSets(x => x ?? []); setFavs(x => x ?? []); setRecent(x => x ?? [])
    })
    return () => { live = false }
  }, [])

  const open = (s: SavedSet, action: 'edit' | 'play') => {
    setPrefs(s.preferences); setTracks(s.tracks); setEditingSetId(s.id); setPlayed([])
    nav(action === 'edit' ? '/set' : '/live')
  }
  const del = async (s: SavedSet) => {
    if (!window.confirm(`Delete “${s.name}”?`)) return
    try { await api.deleteSet(s.id); setSets(list => (list ?? []).filter(x => x.id !== s.id)) }
    catch (e) { setErr(e instanceof ApiError ? e.message : 'Could not delete') }
  }
  const unfav = async (id: string) => {
    try { await api.removeFavorite(id); setFavs(l => (l ?? []).filter(f => f.track_id !== id)) }
    catch (e) { setErr(e instanceof ApiError ? e.message : 'Could not update favourites') }
  }

  return (
    <main className="page">
      <header className="topbar">
        <Logo />
        <div className="top-actions">
          <button className="link-btn" onClick={() => { reset(); nav('/start') }}>← Play</button>
          <button className="link-btn" onClick={() => void signOut().then(() => nav('/'))} title={email ?? undefined}>Log out</button>
        </div>
      </header>
      <h1 className="title display">My sets</h1>
      {err && <p className="err" role="alert">{err}</p>}
      {sets === null ? <div className="spinner" aria-label="Loading" /> : (<>
        {sets.length === 0 ? (
          <div className="empty"><div className="display">No saved sets yet</div><p>Finish a set and choose Yes to keep it here.</p>
            <button className="btn btn-primary btn-next" onClick={() => nav('/start')}>Start a set →</button></div>
        ) : sets.map(s => (
          <div key={s.id} className="set-card">
            <div><div className="sn">{s.name}</div>
              <div className="ss">{s.tracks.length} songs · about {totalMinutes(s.tracks)} min · {new Date(s.created_at).toLocaleDateString()}</div></div>
            <div className="acts">
              <button className="icon-btn" aria-label={`Play ${s.name}`} onClick={() => open(s, 'play')}><Play size={13} fill="currentColor" /></button>
              <button className="icon-btn" aria-label={`Edit ${s.name}`} onClick={() => open(s, 'edit')}><Pencil size={13} /></button>
              <button className="icon-btn" aria-label={`Delete ${s.name}`} onClick={() => void del(s)}><Trash2 size={13} /></button>
            </div>
          </div>
        ))}

        <div className="section-label">Favourites</div>
        {favs && favs.length > 0 ? favs.map(f => (
          <div key={f.track_id} className="res">
            <div><div className="rt">{f.track.title}</div><div className="ra">{f.track.artist}</div></div>
            <button className="icon-btn" aria-label={`Remove ${f.track.title} from favourites`} onClick={() => void unfav(f.track_id)}><Heart size={13} fill="currentColor" className="accent" /></button>
          </div>
        )) : <p className="note" style={{ marginTop: 0 }}>Tap the heart on any track in a set to keep it here.</p>}

        <div className="section-label">Recently played</div>
        {recent && recent.length > 0 ? recent.slice(0, 15).map(r => (
          <div key={`${r.track_id}-${r.played_at}`} className="res">
            <div><div className="rt">{r.track.title}</div><div className="ra">{r.track.artist} · {new Date(r.played_at).toLocaleString()}</div></div>
          </div>
        )) : <p className="note" style={{ marginTop: 0 }}>Songs that play to the end of their cut show up here.</p>}
      </>)}
    </main>
  )
}
