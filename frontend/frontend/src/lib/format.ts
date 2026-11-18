import type { Preferences, Track } from './types'

export function mmss(sec: number | null | undefined): string {
  if (sec == null || !Number.isFinite(sec) || sec < 0) return '0:00'
  const s = Math.floor(sec)
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}

export const STAGE_LABEL: Record<string, string> = {
  warming_up: 'Warming up', peak: 'Peak', winding_down: 'Winding down', only_bangers: 'Only bangers',
}
export const OCCASION_LABEL: Record<string, string> = {
  listening: 'Just listening', wedding: 'Wedding party', baraat: 'Baraat', sangeet: 'Sangeet',
  mehendi: 'Mehendi', haldi: 'Haldi', birthday: 'Birthday', house_party: 'House party',
  club: 'Club event', corporate: 'Corporate party',
}

/** Chips shown in the live header, e.g. HINDI · DANCE · ONLY BANGERS · 20+ */
export function prefChips(p: Preferences): string[] {
  const out: string[] = []
  for (const lang of p.languages) {
    out.push(lang.split(' / ')[0])
    out.push(...(p.genres[lang] ?? []))
  }
  out.push(STAGE_LABEL[p.stage] ?? p.stage)
  if (p.crowd) out.push(p.crowd)
  return out
}

export function totalMinutes(tracks: Track[]): number {
  return Math.round(tracks.reduce((a, t) => a + (t.duration_sec ?? 180), 0) / 60)
}
