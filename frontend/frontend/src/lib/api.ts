import { supabase } from './supabase'
import type { Analysis, Authorization, Preferences, SavedSet, Track } from './types'

export const API_BASE_URL: string = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8765'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init: RequestInit = {}, auth = true): Promise<T> {
  const headers = new Headers(init.headers)
  if (init.body) headers.set('Content-Type', 'application/json')
  if (auth) {
    const { data } = await supabase.auth.getSession()
    if (data.session) headers.set('Authorization', `Bearer ${data.session.access_token}`)
  }
  let res: Response
  try {
    res = await fetch(`${API_BASE_URL}${path}`, { ...init, headers })
  } catch {
    throw new ApiError(0, 'Cannot reach the RØVE server')
  }
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      if (typeof body.detail === 'string') detail = body.detail
    } catch { /* non-JSON error body */ }
    throw new ApiError(res.status, detail)
  }
  return (await res.json()) as T
}

const post = <T,>(path: string, body: unknown, auth = true) =>
  request<T>(path, { method: 'POST', body: JSON.stringify(body) }, auth)

export const api = {
  health: () => request<{ status: string }>('/health', {}, false),
  me: () => request<{ id: string; email: string | null; member: boolean }>('/api/auth/me'),
  validateInvite: (code: string) => post<{ valid: boolean }>('/api/invitations/validate', { code }, false),
  redeemInvite: (code: string) => post<{ member: boolean }>('/api/invitations/redeem', { code }),

  languages: () =>
    request<{ languages: { language: string; count: number | null; capped: boolean; open?: boolean }[]; errors: Record<string, string> }>(
      '/api/music/languages',
    ),
  search: (q: string, playableOnly = true) =>
    request<{ tracks: Track[]; errors: Record<string, string> }>(
      `/api/music/search?q=${encodeURIComponent(q)}&limit=12&playable_only=${playableOnly}`,
    ),

  generate: (preferences: Preferences, seed?: number) =>
    post<{ tracks: Track[]; errors: Record<string, string>; seed: number }>('/api/playlists/generate', { preferences, seed }),
  replace: (preferences: Preferences, current: Track[], index: number) =>
    post<{ track: Track }>('/api/playlists/replace', { preferences, current, index }),

  authorize: (track_id: string) => post<Authorization>('/api/playback/authorize', { track_id }),
  analyze: (track_id: string) => post<Analysis>('/api/audio/analyze', { track_id }),

  listSets: () => request<{ sets: SavedSet[] }>('/api/library/sets'),
  saveSet: (s: { name: string; preferences: Preferences; tracks: Track[]; completed: boolean; skipped_count: number }) =>
    post<SavedSet>('/api/library/sets', s),
  updateSet: (id: string, s: { name: string; preferences: Preferences; tracks: Track[]; completed: boolean; skipped_count: number }) =>
    request<SavedSet>(`/api/library/sets/${id}`, { method: 'PUT', body: JSON.stringify(s) }),
  deleteSet: (id: string) => request<{ deleted: boolean }>(`/api/library/sets/${id}`, { method: 'DELETE' }),

  favorites: () => request<{ favorites: { track_id: string; track: Track }[] }>('/api/library/favorites'),
  addFavorite: (track: Track) => post<{ favorited: boolean }>('/api/library/favorites', { track }),
  removeFavorite: (id: string) => request<{ favorited: boolean }>(`/api/library/favorites/${encodeURIComponent(id)}`, { method: 'DELETE' }),

  requestSong: (text: string, language?: string) => post<{ requested: boolean }>('/api/library/requests', { text, language }),

  recent: () => request<{ recent: { track_id: string; track: Track; played_at: string }[] }>('/api/library/recent'),
  logPlay: (track: Track, mode: 'segment' | 'full', completed: boolean) =>
    post<{ logged: boolean }>('/api/library/recent', { track, mode, completed }),
}
