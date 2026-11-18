import { Link } from 'react-router-dom'
import type { ReactNode } from 'react'

export function Logo() {
  return <Link to="/" className="logo" aria-label="RØVE home">RØVE</Link>
}

export function Topbar({ right }: { right?: ReactNode }) {
  return (
    <header className="topbar">
      <Logo />
      <div className="top-actions">{right}</div>
    </header>
  )
}

export function MySetsLink({ count }: { count?: number }) {
  return (
    <Link to="/sets" className="mysets-link">
      {count != null && <span className="count">{count}</span>}
      My sets
    </Link>
  )
}
