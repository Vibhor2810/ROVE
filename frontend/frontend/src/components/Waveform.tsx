import { mmss } from '../lib/format'

interface Props {
  peaks: number[] | null
  duration: number
  time: number
  inSec: number | null
  outSec: number | null
  onPick?: (sec: number) => void
  /** No audio analysis available (e.g. YouTube): draw a seekable progress bar instead of a waveform. */
  progressOnly?: boolean
}

/** Bar waveform with IN/OUT markers and a playhead. Placeholder while analysing. */
export function Waveform({ peaks, duration, time, inSec, outSec, onPick, progressOnly }: Props) {
  const W = 1000, H = 86, mid = H / 2
  const hasData = !progressOnly && !!peaks && peaks.length > 0 && duration > 0
  const frac = (s: number) => (duration > 0 ? Math.min(1, Math.max(0, s / duration)) : 0)
  const bw = peaks ? W / peaks.length : 0

  const pick = (e: React.PointerEvent<HTMLDivElement>) => {
    if ((!hasData && !progressOnly) || duration <= 0 || !onPick) return
    const r = e.currentTarget.getBoundingClientRect()
    onPick(((e.clientX - r.left) / r.width) * duration)
  }

  return (
    <div className="wave-wrap">
      <div className="wave-marks" aria-hidden={!hasData}>
        {hasData && inSec != null && <span style={{ left: `${frac(inSec) * 100}%` }}>In {mmss(inSec)}</span>}
        {hasData && outSec != null && outSec < duration && (
          <span style={{ left: `${frac(outSec) * 100}%` }}>Out {mmss(outSec)}</span>
        )}
      </div>
      <div className="wave" onPointerDown={pick} role={onPick ? 'slider' : undefined}
           aria-label="Waveform. Click to choose where the song starts"
           aria-valuemin={0} aria-valuemax={Math.round(duration)} aria-valuenow={Math.round(time)}>
        {progressOnly ? (
          <div className="progress-track" aria-hidden="true"><i style={{ width: `${frac(time) * 100}%` }} /></div>
        ) : hasData ? (
          <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" aria-hidden="true">
            {peaks!.map((p, i) => {
              const h = Math.max(3, p * (H - 6))
              const x = i * bw
              const sec = (x / W) * duration
              const inWindow = inSec == null || (sec >= inSec && (outSec == null || sec <= outSec))
              const played = x / W * duration <= time
              const fill = inWindow ? (played ? '#ffffff' : '#d9d9de') : '#3a3a42'
              return <rect key={i} x={x + bw * 0.18} y={mid - h / 2} width={bw * 0.64} height={h} rx={1} fill={fill} />
            })}
            {inSec != null && <rect x={frac(inSec) * W - 1.5} y={0} width={3} height={H} fill="var(--accent)" />}
            {outSec != null && outSec < duration && <rect x={frac(outSec) * W - 1.5} y={0} width={3} height={H} fill="var(--accent)" />}
            <rect x={frac(time) * W - 1} y={0} width={2} height={H} fill="#fff" />
          </svg>
        ) : (
          <div className="analysing">ANALYSING…</div>
        )}
      </div>
    </div>
  )
}
