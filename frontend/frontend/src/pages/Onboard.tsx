import { useEffect, useMemo, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, X } from 'lucide-react'
import { api, ApiError } from '../lib/api'
import { useFlow } from '../flow/FlowContext'
import { DEFAULT_PREFS } from '../flow/defaults'
import { Logo } from '../components/Topbar'
import { Modal } from '../components/Modal'
import type { Crowd, Occasion, Preferences, Purpose, Stage } from '../lib/types'

const OCCASIONS: { id: Occasion; name: string; hint: string }[] = [
  { id: 'listening', name: 'Just listening', hint: 'A playlist for me' },
  { id: 'wedding', name: 'Wedding party', hint: 'The big night' },
  { id: 'baraat', name: 'Baraat', hint: 'Dhol-first, full volume' },
  { id: 'sangeet', name: 'Sangeet', hint: 'Dance-off energy' },
  { id: 'mehendi', name: 'Mehendi', hint: 'Easy and festive' },
  { id: 'haldi', name: 'Haldi', hint: 'Bright morning vibes' },
  { id: 'birthday', name: 'Birthday', hint: 'Make it a moment' },
  { id: 'house_party', name: 'House party', hint: 'Friends and speakers' },
  { id: 'club', name: 'Club event', hint: 'Floor-filling sets' },
  { id: 'corporate', name: 'Corporate party', hint: 'Fun, but office-safe' },
]
const PURPOSES: { id: Purpose; name: string; hint: string }[] = [
  { id: 'workout', name: 'Workout', hint: 'Keep me moving' },
  { id: 'focus', name: 'Focus', hint: 'Stay in the zone' },
  { id: 'chill', name: 'Chill', hint: 'Wind down, no rush' },
  { id: 'drive', name: 'Drive', hint: 'Windows down' },
]
const LANGUAGES = ['Hindi', 'Punjabi', 'English', 'Tamil / Telugu', 'Garba / Gujarati']
const GENRES: Record<string, string[]> = {
  Hindi: ['Dance', 'Retro', 'Romantic', 'Sufi', 'Desi Hip-Hop'],
  Punjabi: ['Party', 'Wedding', 'Sad', 'Gym / Workout'],
  English: ['Pop', 'Hip-Hop', 'Rock', 'Electronic'],
  'Tamil / Telugu': ['Dance', 'Melody'],
  'Garba / Gujarati': ['Garba', 'Folk'],
}
const STAGES: { id: Stage; name: string; hint: string }[] = [
  { id: 'warming_up', name: 'Warming up', hint: 'People arriving, building slowly' },
  { id: 'peak', name: 'Peak', hint: 'Full room, dancefloor energy' },
  { id: 'winding_down', name: 'Winding down', hint: 'Late, easing off' },
  { id: 'only_bangers', name: 'Only bangers', hint: 'High energy only, no slow songs.' },
]
const CROWDS: { id: Crowd; name: string; hint: string }[] = [
  { id: '4-6', name: '4-6', hint: 'Music you can talk over' },
  { id: '10-20', name: '10-20', hint: 'A proper party' },
  { id: '20+', name: '20+', hint: 'A dancefloor' },
]

type StepId = 'occasion' | 'purpose' | 'language' | 'genre' | 'stage' | 'crowd'

function stepsFor(p: Preferences): StepId[] {
  return p.occasion === 'listening'
    ? ['occasion', 'purpose', 'language', 'genre', 'stage']
    : ['occasion', 'language', 'genre', 'stage', 'crowd']
}

export default function Onboard() {
  const nav = useNavigate()
  const { prefs, setPrefs, setTracks, setEditingSetId, setPlayed } = useFlow()
  const [draft, setDraft] = useState<Preferences>({ ...DEFAULT_PREFS, ...prefs, genres: { ...prefs.genres } })
  const [stepIdx, setStepIdx] = useState(0)
  const [counts, setCounts] = useState<Record<string, { count: number | null; capped: boolean; open?: boolean }> | null>(null)
  const [catalogueErr, setCatalogueErr] = useState('')
  const [building, setBuilding] = useState(false)
  const [error, setError] = useState('')
  const [setsCount, setSetsCount] = useState<number | null>(null)
  const [reqOpen, setReqOpen] = useState(false)
  const [reqText, setReqText] = useState('')
  const [reqMsg, setReqMsg] = useState('')

  const steps = useMemo(() => stepsFor(draft), [draft])
  const step = steps[Math.min(stepIdx, steps.length - 1)]

  useEffect(() => {
    let live = true
    api.listSets().then(r => live && setSetsCount(r.sets.length)).catch(() => undefined)
    api.languages().then(r => {
      if (!live) return
      setCounts(Object.fromEntries(r.languages.map(l => [l.language, { count: l.count, capped: l.capped, open: l.open }])))
      const msgs = Object.values(r.errors)
      if (msgs.length) setCatalogueErr(msgs[0])
    }).catch(e => live && setCatalogueErr(e instanceof ApiError ? e.message : 'Catalogue unavailable'))
    return () => { live = false }
  }, [])

  const toggleLang = (l: string) => setDraft(d => {
    const on = d.languages.includes(l)
    const languages = on ? d.languages.filter(x => x !== l) : [...d.languages, l]
    const genres = { ...d.genres }
    if (on) delete genres[l]
    return { ...d, languages, genres }
  })
  const toggleGenre = (l: string, g: string) => setDraft(d => {
    const cur = d.genres[l] ?? []
    return { ...d, genres: { ...d.genres, [l]: cur.includes(g) ? cur.filter(x => x !== g) : [...cur, g] } }
  })

  const canNext = (() => {
    switch (step) {
      case 'occasion': return !!draft.occasion
      case 'purpose': return !!draft.purpose
      case 'language': return draft.languages.length > 0
      case 'genre': return true // optional
      case 'stage': return !!draft.stage
      case 'crowd': return !!draft.crowd
    }
  })()
  const isLast = stepIdx === steps.length - 1

  const build = async () => {
    setBuilding(true); setError('')
    const final: Preferences = {
      ...draft,
      crowd: draft.occasion === 'listening' ? null : draft.crowd,
      purpose: draft.occasion === 'listening' ? draft.purpose : null,
    }
    try {
      const r = await api.generate(final)
      setPrefs(final); setTracks(r.tracks); setEditingSetId(null); setPlayed([])
      nav('/review')
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not build the set')
      setBuilding(false)
    }
  }

  const next = () => { if (isLast) void build(); else setStepIdx(i => i + 1) }
  const back = () => setStepIdx(i => Math.max(0, i - 1))

  if (building) {
    return (
      <main className="loading-screen" role="status" aria-live="polite">
        <div style={{ textAlign: 'center' }}>
          <div className="spinner" style={{ margin: '0 auto 18px' }} />
          <div className="display" style={{ fontSize: 34 }}>Building tonight’s set…</div>
          <p className="muted" style={{ marginTop: 8 }}>Picking tracks, ordering the energy.</p>
        </div>
      </main>
    )
  }

  const OptionCard = ({ on, onClick, name, hint, tall, disabled }: { on: boolean; onClick: () => void; name: string; hint?: string; tall?: boolean; disabled?: boolean }) => (
    <button type="button" className={`card${on ? ' on' : ''}${tall ? ' tall' : ''}`} aria-pressed={on} onClick={onClick} disabled={disabled}>
      <span className="name">{name}</span>
      {hint && <span className="hint">{hint}</span>}
    </button>
  )

  return (
    <main className="page">
      <header className="topbar">
        <Logo />
        <div className="top-actions">
          {stepIdx > 0 && <button className="link-btn" onClick={back}><ArrowLeft size={14} /> Back</button>}
          <button className="mysets-link" onClick={() => nav('/sets')}>
            <span className="count">{setsCount ?? '–'}</span> My sets
          </button>
          <span className="step-count" aria-label={`Step ${stepIdx + 1} of ${steps.length}`}>{stepIdx + 1} / {steps.length}</span>
          {stepIdx > 0 && <button className="icon-btn" aria-label="Start over" onClick={() => { setDraft(DEFAULT_PREFS); setStepIdx(0) }}><X size={14} /></button>}
        </div>
      </header>

      <AnimatePresence mode="wait">
        <motion.section key={step} initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -12 }} transition={{ duration: 0.25 }}>
          {step === 'occasion' && (<>
            <h1 className="title display">What’s the occasion?</h1>
            <p className="sub">We’ll shape the set around it.</p>
            <div className="grid">
              {OCCASIONS.map(o => <OptionCard key={o.id} on={draft.occasion === o.id} name={o.name} hint={o.hint}
                onClick={() => setDraft(d => ({ ...d, occasion: o.id, crowd: o.id === 'listening' ? null : d.crowd, purpose: o.id === 'listening' ? d.purpose : null }))} />)}
            </div>
          </>)}

          {step === 'purpose' && (<>
            <h1 className="title display">What’s it for?</h1>
            <p className="sub">Just for you, so no crowd to plan around.</p>
            <div className="grid">
              {PURPOSES.map(o => <OptionCard key={o.id} on={draft.purpose === o.id} name={o.name} hint={o.hint} onClick={() => setDraft(d => ({ ...d, purpose: o.id }))} />)}
            </div>
          </>)}

          {step === 'language' && (<>
            <h1 className="title display">What are we playing?</h1>
            <p className="sub">Pick every language the room wants.</p>
            <div className="grid">
              {LANGUAGES.map(l => {
                const c = counts?.[l]
                const empty = !!c && !c.open && c.count === 0
                const hint = c ? (c.open ? 'Full catalogue ready' : `${c.count}${c.capped ? '+' : ''} songs ready`) : catalogueErr ? 'catalogue unavailable' : 'checking…'
                return <OptionCard key={l} on={draft.languages.includes(l)} name={l} hint={hint} disabled={empty} onClick={() => toggleLang(l)} />
              })}
            </div>
            <button className="pill" style={{ marginTop: 16 }} onClick={() => { setReqMsg(''); setReqOpen(true) }}>+ Missing a song? Request it</button>
            {catalogueErr && <p className="err" role="alert">{catalogueErr}</p>}
            {counts && LANGUAGES.every(l => !counts[l]?.open && counts[l]?.count === 0) && !catalogueErr && (
              <p className="note">No playable songs found yet. Connect a music provider (see README) and reload.</p>
            )}
          </>)}

          {step === 'genre' && (<>
            <h1 className="title display">What kind?</h1>
            <p className="sub">Optional. Skip a language to take anything in it.</p>
            {draft.languages.map(l => (
              <div key={l}>
                <div className="group-label">{l.split(' / ')[0]}</div>
                <div className="grid cols-4">
                  {(GENRES[l] ?? []).map(g => <OptionCard key={g} on={(draft.genres[l] ?? []).includes(g)} name={g} onClick={() => toggleGenre(l, g)} />)}
                </div>
              </div>
            ))}
          </>)}

          {step === 'stage' && (<>
            <h1 className="title display">Where in the night are we?</h1>
            <p className="sub">This sets the energy curve.</p>
            <div className="grid">
              {STAGES.map(o => <OptionCard key={o.id} tall on={draft.stage === o.id} name={o.name} hint={o.hint} onClick={() => setDraft(d => ({ ...d, stage: o.id }))} />)}
            </div>
          </>)}

          {step === 'crowd' && (<>
            <h1 className="title display">How many people?</h1>
            <div className="grid cols-3" style={{ marginTop: 22 }}>
              {CROWDS.map(o => <OptionCard key={o.id} tall on={draft.crowd === o.id} name={o.name} hint={o.hint} onClick={() => setDraft(d => ({ ...d, crowd: o.id }))} />)}
            </div>
          </>)}
        </motion.section>
      </AnimatePresence>

      {reqOpen && (
        <Modal title="Request a song" onClose={() => setReqOpen(false)}>
          <input className="search" autoFocus maxLength={200} placeholder="Song and artist" value={reqText} onChange={e => setReqText(e.target.value)} aria-label="Song and artist" />
          {reqMsg && <p className="note" role="status">{reqMsg}</p>}
          <button className="btn btn-primary" style={{ marginTop: 12, fontSize: 20, padding: '8px 18px' }} disabled={reqText.trim().length < 2}
            onClick={() => api.requestSong(reqText.trim(), draft.languages[0]).then(() => { setReqMsg('Noted. Requests are reviewed by hand, nothing is added automatically.'); setReqText('') })
              .catch(e => setReqMsg(e instanceof ApiError ? e.message : 'Could not send'))}>Send</button>
        </Modal>
      )}
      {error && <p className="err" role="alert">{error}</p>}
      <div className="next-dock">
        <button className="btn btn-primary btn-next" disabled={!canNext} onClick={next}>{isLast ? 'Build my set →' : 'Next →'}</button>
      </div>
    </main>
  )
}
