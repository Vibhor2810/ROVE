import { useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { Topbar } from '../components/Topbar'

export default function Login() {
  const { access, signIn, signUp } = useAuth()
  const nav = useNavigate()
  const [mode, setMode] = useState<'in' | 'up'>('in')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [code, setCode] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const [info, setInfo] = useState('')

  if (access === 'member') return <Navigate to="/start" replace />

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setBusy(true); setErr(''); setInfo('')
    try {
      if (mode === 'in') {
        await signIn(email.trim(), password)
        nav('/start')
      } else {
        const r = await signUp(email.trim(), password, code)
        if (r.needsEmailConfirm) {
          setInfo('Check your email to confirm your account, then log in. You’ll be asked for your invitation code once if it wasn’t applied.')
          setMode('in')
        } else nav('/start')
      }
    } catch (e2) {
      setErr(e2 instanceof Error ? e2.message : 'Something went wrong')
    } finally { setBusy(false) }
  }

  return (
    <main className="page">
      <Topbar />
      <form className="form" onSubmit={submit}>
        <h1 className="title display" style={{ fontSize: 56 }}>{mode === 'in' ? 'Welcome back' : 'You’re invited'}</h1>
        <div className="tabs" role="tablist">
          <button type="button" role="tab" aria-selected={mode === 'in'} className={mode === 'in' ? 'on' : ''} onClick={() => { setMode('in'); setErr('') }}>Log in</button>
          <button type="button" role="tab" aria-selected={mode === 'up'} className={mode === 'up' ? 'on' : ''} onClick={() => { setMode('up'); setErr('') }}>I have a code</button>
        </div>
        <label className="field"><span>Email</span>
          <input type="email" value={email} onChange={e => setEmail(e.target.value)} autoComplete="email" required />
        </label>
        <label className="field"><span>Password</span>
          <input type="password" value={password} onChange={e => setPassword(e.target.value)} autoComplete={mode === 'in' ? 'current-password' : 'new-password'} required minLength={8} />
        </label>
        {mode === 'up' && (
          <label className="field"><span>Invitation code</span>
            <input value={code} onChange={e => setCode(e.target.value)} autoComplete="off" required minLength={4} maxLength={64} />
          </label>
        )}
        {err && <p className="err" role="alert">{err}</p>}
        {info && <p className="note" role="status">{info}</p>}
        <button className="btn btn-primary btn-next" disabled={busy} style={{ marginTop: 8 }}>
          {busy ? 'One sec…' : mode === 'in' ? 'Log in →' : 'Join RØVE →'}
        </button>
      </form>
    </main>
  )
}
