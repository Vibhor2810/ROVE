import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, ApiError } from '../lib/api'
import { useFlow } from '../flow/FlowContext'
import { Logo } from '../components/Topbar'
import { prefChips } from '../lib/format'

export default function Complete() {
  const nav = useNavigate()
  const { played, prefs, reset, editingSetId } = useFlow()
  const heard = played.filter(p => !p.skipped)
  const skipped = played.length - heard.length
  const [name, setName] = useState(() => `${prefChips(prefs).slice(0, 3).join(' · ')} · ${new Date().toLocaleDateString()}`)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  const save = async () => {
    setBusy(true); setErr('')
    const body = { name: name.trim() || 'Untitled set', preferences: prefs, tracks: heard.map(p => p.track), completed: true, skipped_count: skipped }
    try {
      if (editingSetId) await api.updateSet(editingSetId, body)
      else await api.saveSet(body)
      reset()
      nav('/sets')
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : 'Could not save the set')
      setBusy(false)
    }
  }
  const discard = () => { reset(); nav('/start') }

  if (played.length === 0) {
    return (
      <main className="page"><header className="topbar"><Logo /></header>
        <div className="empty"><div className="display">Nothing played</div>
          <p>Start a set to see its summary here.</p>
          <button className="btn btn-primary btn-next" onClick={() => nav('/start')}>Start a set →</button></div>
      </main>
    )
  }

  return (
    <main className="page">
      <header className="topbar"><Logo /></header>
      <h1 className="title display">That was the set</h1>
      <p className="muted" style={{ margin: 0 }}>{heard.length} {heard.length === 1 ? 'song' : 'songs'} · {skipped} skipped</p>
      <ol className="done-list">
        {played.map((p, i) => (
          <li key={`${p.track.id}-${i}`} className={p.skipped ? 'skipped' : ''}>
            <span className="n">{i + 1}</span>
            <div><div className="dt">{p.track.title}</div><div className="da">{p.track.artist}{p.skipped ? ' · skipped' : ''}</div></div>
          </li>
        ))}
      </ol>
      <section className="save-block">
        <div className="display">Save this set?</div>
        {heard.length === 0 ? <p className="note">Every song was skipped, so there’s nothing to save.</p> : (
          <input className="name-input" value={name} onChange={e => setName(e.target.value)} maxLength={120} aria-label="Set name" />
        )}
        {err && <p className="err" role="alert">{err}</p>}
        <div className="save-actions">
          <button className="btn btn-primary" disabled={busy || heard.length === 0} onClick={() => void save()}>{busy ? 'Saving…' : 'Yes'}</button>
          <button className="btn btn-ghost" disabled={busy} onClick={discard}>No</button>
        </div>
      </section>
    </main>
  )
}
