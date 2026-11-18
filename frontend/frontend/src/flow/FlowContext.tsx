import { createContext, useContext, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import type { Preferences, Track } from '../lib/types'
import { DEFAULT_PREFS } from './defaults'

export interface PlayedEntry { track: Track; skipped: boolean; mode: 'segment' | 'full' }

interface FlowValue {
  prefs: Preferences
  setPrefs: (p: Preferences) => void
  tracks: Track[]
  setTracks: (t: Track[]) => void
  /** id of a saved set being edited, if any */
  editingSetId: string | null
  setEditingSetId: (id: string | null) => void
  played: PlayedEntry[]
  setPlayed: (p: PlayedEntry[]) => void
  reset: () => void
}

const Ctx = createContext<FlowValue | null>(null)

export function FlowProvider({ children }: { children: ReactNode }) {
  const [prefs, setPrefs] = useState<Preferences>(DEFAULT_PREFS)
  const [tracks, setTracks] = useState<Track[]>([])
  const [editingSetId, setEditingSetId] = useState<string | null>(null)
  const [played, setPlayed] = useState<PlayedEntry[]>([])
  const value = useMemo<FlowValue>(() => ({
    prefs, setPrefs, tracks, setTracks, editingSetId, setEditingSetId, played, setPlayed,
    reset: () => { setPrefs(DEFAULT_PREFS); setTracks([]); setEditingSetId(null); setPlayed([]) },
  }), [prefs, tracks, editingSetId, played])
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useFlow(): FlowValue {
  const v = useContext(Ctx)
  if (!v) throw new Error('useFlow outside FlowProvider')
  return v
}
