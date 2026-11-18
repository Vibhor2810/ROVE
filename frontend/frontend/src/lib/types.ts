export interface Rights {
  full_playback: boolean
  seek_playback: boolean
  crossfade: boolean
  segment_playback: boolean
  dj_transition: boolean
  mixtape_sharing: boolean
  public_performance: boolean
}

export interface Track {
  id: string
  provider: string
  provider_track_id: string
  title: string
  artist: string
  album?: string | null
  duration_sec?: number | null
  artwork_url?: string | null
  audio_url?: string | null
  youtube_id?: string | null
  language?: string | null
  genres: string[]
  moods: string[]
  bpm?: number | null
  key?: string | null
  energy?: number | null
  energy_source?: 'provider' | 'analysis' | null
  license?: string | null
  rights: Rights
}

export type Occasion =
  | 'listening' | 'wedding' | 'baraat' | 'sangeet' | 'mehendi' | 'haldi'
  | 'birthday' | 'house_party' | 'club' | 'corporate'
export type Stage = 'warming_up' | 'peak' | 'winding_down' | 'only_bangers'
export type Crowd = '4-6' | '10-20' | '20+'
export type Purpose = 'workout' | 'focus' | 'chill' | 'drive'

export interface Preferences {
  occasion: Occasion
  languages: string[]
  genres: Record<string, string[]>
  purpose?: Purpose | null
  stage: Stage
  crowd?: Crowd | null
  target_minutes: number
}

export type PlaySource = { kind: 'audio'; url: string } | { kind: 'youtube'; id: string }

export interface Authorization {
  track_id: string
  playable: boolean
  audio_url: string | null
  source: PlaySource | null
  allowed: { full: boolean; segment: boolean; seek: boolean; crossfade: boolean }
  default_mode: 'segment' | 'full' | 'denied'
  reason: string | null
}

export interface Analysis {
  track_id: string
  duration_sec: number
  bpm: number | null
  key: string | null
  highlight: { in_sec: number; out_sec: number; source: 'estimated' } | null
  waveform: number[]
}

export interface SavedSet {
  id: string
  name: string
  preferences: Preferences
  tracks: Track[]
  completed: boolean
  skipped_count: number
  created_at: string
}
