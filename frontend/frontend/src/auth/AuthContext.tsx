import { createContext, useContext, useMemo } from 'react'
import type { ReactNode } from 'react'
import type { Session } from '@supabase/supabase-js'

export type Access = 'loading' | 'signed_out' | 'needs_invite' | 'member' | 'server_down'

interface AuthValue {
  session: Session | null
  access: Access
  email: string | null
  signIn: (email: string, password: string) => Promise<void>
  signUp: (email: string, password: string, code: string) => Promise<{ needsEmailConfirm: boolean }>
  redeem: (code: string) => Promise<void>
  signOut: () => Promise<void>
  recheck: () => Promise<void>
}

const Ctx = createContext<AuthValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const value = useMemo<AuthValue>(() => ({
    session: null,
    access: 'member',
    email: 'guest@rove.local',
    signIn: async () => {},
    signUp: async () => ({ needsEmailConfirm: false }),
    redeem: async () => {},
    signOut: async () => {},
    recheck: async () => {},
  }), [])

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): AuthValue {
  const v = useContext(Ctx)
  if (!v) throw new Error('useAuth outside AuthProvider')
  return v
}
