import { useEffect, useRef } from 'react'
import type { DjEngine } from '../audio/DjEngine'
import { mmss } from '../lib/format'

interface Props {
  engine: DjEngine | null
  deck: 'A' | 'B'
  duration: number
  time: number
  inSec: number | null
  outSec: number | null
  paused: boolean
  mode: 'segment' | 'full'
  onSeek?: (sec: number) => void
}

const BAR_COUNT = 100
const NEON_PURPLE = '#A855F7'
const LIME_GREEN = '#A3E635'
const MIX_WHITE = '#FFFFFF'
const NEON_PINK = '#FF2D75'

export function CircularVisualizer({
  engine,
  deck,
  duration,
  time,
  inSec,
  outSec,
  paused,
  mode,
  onSeek,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const wrapRef = useRef<HTMLDivElement | null>(null)
  const smoothedRef = useRef<Float32Array>(new Float32Array(BAR_COUNT))
  const draggingRef = useRef(false)

  const stateRef = useRef({ engine, deck, duration, time, inSec, outSec, paused, mode })
  stateRef.current = { engine, deck, duration, time, inSec, outSec, paused, mode }

  useEffect(() => {
    let rafId = 0

    const render = () => {
      const canvas = canvasRef.current
      if (!canvas) {
        rafId = requestAnimationFrame(render)
        return
      }
      const ctx = canvas.getContext('2d')
      if (!ctx) return

      const dpr = Math.min(window.devicePixelRatio || 1, 2)
      const rect = canvas.getBoundingClientRect()
      const targetW = Math.max(1, Math.round(rect.width * dpr))
      const targetH = Math.max(1, Math.round(rect.height * dpr))
      if (canvas.width !== targetW || canvas.height !== targetH) {
        canvas.width = targetW
        canvas.height = targetH
      }

      const w = canvas.width
      const h = canvas.height
      const cx = w / 2
      const cy = h / 2
      const minDim = Math.min(w, h)

      const baseRadius = minDim * 0.27
      const maxOutward = minDim * 0.175
      const maxInward = minDim * 0.075
      const trackRingRadius = baseRadius - maxInward - minDim * 0.032

      const { engine: eng, deck: activeDeck, duration: dur, time: curTime, inSec: segIn, outSec: segOut, paused: isPaused } = stateRef.current
      const isMixing = !!eng?.isTransitioning()
      const freq = !isPaused ? eng?.getFrequencyData() ?? null : null
      const smoothed = smoothedRef.current

      for (let i = 0; i < BAR_COUNT; i++) {
        const symIndex = i < BAR_COUNT / 2 ? i : BAR_COUNT - 1 - i
        const normPos = symIndex / (BAR_COUNT / 2)

        let target = 0
        if (freq && freq.length > 0) {
          const usableBins = Math.min(freq.length - 1, 88)
          const bin = Math.min(usableBins, Math.max(1, Math.floor(Math.pow(normPos, 1.35) * usableBins)))
          const raw = freq[bin] / 255
          const bandWeight = normPos < 0.25 ? 1.25 : normPos < 0.65 ? 0.92 : 0.72
          target = Math.min(1, Math.pow(raw, 1.15) * bandWeight)
        }

        const attack = normPos < 0.25 ? 0.28 : 0.42
        const decay = isPaused ? 0.08 : normPos < 0.25 ? 0.14 : 0.22
        const alpha = target > smoothed[i] ? attack : decay
        smoothed[i] += (target - smoothed[i]) * alpha
      }

      ctx.clearRect(0, 0, w, h)

      const deckColor = isMixing ? MIX_WHITE : activeDeck === 'A' ? LIME_GREEN : NEON_PURPLE
      const secondaryColor = isMixing ? NEON_PINK : NEON_PURPLE

      const halo = ctx.createRadialGradient(cx, cy, baseRadius * 0.65, cx, cy, baseRadius + maxOutward * 1.15)
      halo.addColorStop(0, 'rgba(168, 85, 247, 0.02)')
      halo.addColorStop(0.55, isMixing ? 'rgba(255, 255, 255, 0.09)' : activeDeck === 'A' ? 'rgba(163, 230, 53, 0.08)' : 'rgba(168, 85, 247, 0.11)')
      halo.addColorStop(1, 'rgba(0, 0, 0, 0)')
      ctx.fillStyle = halo
      ctx.beginPath()
      ctx.arc(cx, cy, baseRadius + maxOutward * 1.15, 0, Math.PI * 2)
      ctx.fill()

      ctx.save()
      ctx.strokeStyle = 'rgba(168, 85, 247, 0.24)'
      ctx.lineWidth = Math.max(1, dpr)
      ctx.beginPath()
      ctx.arc(cx, cy, baseRadius, 0, Math.PI * 2)
      ctx.stroke()
      ctx.restore()

      const startAngle = -Math.PI / 2
      const step = (Math.PI * 2) / BAR_COUNT
      const barWidth = Math.max(1.8 * dpr, ((Math.PI * 2 * baseRadius) / BAR_COUNT) * 0.52)

      ctx.save()
      ctx.lineCap = 'round'
      ctx.lineWidth = barWidth

      for (let i = 0; i < BAR_COUNT; i++) {
        const angle = startAngle + i * step
        const val = smoothed[i]

        const outLen = Math.max(3 * dpr, val * maxOutward)
        const inLen = Math.max(1.5 * dpr, val * maxInward)

        const r1 = baseRadius - inLen
        const r2 = baseRadius + outLen

        const cos = Math.cos(angle)
        const sin = Math.sin(angle)
        const x1 = cx + cos * r1
        const y1 = cy + sin * r1
        const x2 = cx + cos * r2
        const y2 = cy + sin * r2

        const grad = ctx.createLinearGradient(x1, y1, x2, y2)
        grad.addColorStop(0, secondaryColor)
        grad.addColorStop(0.45, deckColor)
        grad.addColorStop(1, isMixing ? MIX_WHITE : NEON_PURPLE)

        ctx.strokeStyle = grad
        ctx.shadowColor = val > 0.35 ? deckColor : NEON_PURPLE
        ctx.shadowBlur = (6 + val * 14) * dpr

        ctx.beginPath()
        ctx.moveTo(x1, y1)
        ctx.lineTo(x2, y2)
        ctx.stroke()
      }
      ctx.restore()

      if (trackRingRadius > 12 * dpr) {
        ctx.save()
        ctx.lineWidth = 3 * dpr
        ctx.lineCap = 'round'

        ctx.strokeStyle = 'rgba(255, 255, 255, 0.1)'
        ctx.beginPath()
        ctx.arc(cx, cy, trackRingRadius, 0, Math.PI * 2)
        ctx.stroke()

        if (dur > 0 && segIn != null && segOut != null && segOut > segIn) {
          const aStart = startAngle + (segIn / dur) * Math.PI * 2
          const aEnd = startAngle + (Math.min(dur, segOut) / dur) * Math.PI * 2
          ctx.strokeStyle = 'rgba(255, 45, 117, 0.35)'
          ctx.beginPath()
          ctx.arc(cx, cy, trackRingRadius, aStart, aEnd)
          ctx.stroke()
        }

        if (dur > 0) {
          const frac = Math.min(1, Math.max(0, curTime / dur))
          const progEnd = startAngle + frac * Math.PI * 2
          ctx.strokeStyle = isMixing ? MIX_WHITE : deckColor
          ctx.shadowColor = isMixing ? MIX_WHITE : deckColor
          ctx.shadowBlur = 8 * dpr
          ctx.beginPath()
          ctx.arc(cx, cy, trackRingRadius, startAngle, progEnd)
          ctx.stroke()

          const px = cx + Math.cos(progEnd) * trackRingRadius
          const py = cy + Math.sin(progEnd) * trackRingRadius
          ctx.fillStyle = MIX_WHITE
          ctx.beginPath()
          ctx.arc(px, py, 3.6 * dpr, 0, Math.PI * 2)
          ctx.fill()
        }

        const drawMarker = (sec: number | null) => {
          if (sec == null || dur <= 0) return
          const a = startAngle + Math.min(1, Math.max(0, sec / dur)) * Math.PI * 2
          const mx = cx + Math.cos(a) * trackRingRadius
          const my = cy + Math.sin(a) * trackRingRadius
          ctx.fillStyle = NEON_PINK
          ctx.shadowColor = NEON_PINK
          ctx.shadowBlur = 10 * dpr
          ctx.beginPath()
          ctx.arc(mx, my, 4.2 * dpr, 0, Math.PI * 2)
          ctx.fill()
        }

        if (segIn != null && segIn > 0) drawMarker(segIn)
        if (segOut != null && segOut < dur) drawMarker(segOut)
        ctx.restore()
      }

      rafId = requestAnimationFrame(render)
    }

    rafId = requestAnimationFrame(render)
    return () => cancelAnimationFrame(rafId)
  }, [])

  const seekFromPointer = (clientX: number, clientY: number) => {
    if (!onSeek || duration <= 0 || !canvasRef.current) return
    const rect = canvasRef.current.getBoundingClientRect()
    const cx = rect.left + rect.width / 2
    const cy = rect.top + rect.height / 2
    const dx = clientX - cx
    const dy = clientY - cy
    let angle = Math.atan2(dy, dx) + Math.PI / 2
    if (angle < 0) angle += Math.PI * 2
    const frac = Math.min(1, Math.max(0, angle / (Math.PI * 2)))
    onSeek(frac * duration)
  }

  return (
    <div className="circ-vis-wrap" ref={wrapRef}>
      <div
        className="circ-vis-stage"
        role={onSeek ? 'slider' : undefined}
        aria-label="Circular audio visualizer and track scrubber"
        aria-valuemin={0}
        aria-valuemax={Math.round(duration)}
        aria-valuenow={Math.round(time)}
        onPointerDown={(e) => {
          if (!onSeek || duration <= 0) return
          draggingRef.current = true
          e.currentTarget.setPointerCapture(e.pointerId)
          seekFromPointer(e.clientX, e.clientY)
        }}
        onPointerMove={(e) => {
          if (!draggingRef.current) return
          seekFromPointer(e.clientX, e.clientY)
        }}
        onPointerUp={(e) => {
          if (!draggingRef.current) return
          draggingRef.current = false
          e.currentTarget.releasePointerCapture(e.pointerId)
        }}
      >
        <canvas ref={canvasRef} className="circ-vis-canvas" />
        <div className="circ-vis-center" aria-hidden="true">
          <span className={`circ-deck-badge ${deck === 'A' ? 'deck-a' : 'deck-b'}`}>
            DECK {deck}
          </span>
          <span className="circ-time">{mmss(time)}</span>
          <span className="circ-dur">/ {mmss(duration)}</span>
        </div>
      </div>

      {mode === 'segment' && (inSec != null || outSec != null) && (
        <div className="circ-markers-legend">
          {inSec != null && <span className="marker-tag">IN {mmss(inSec)}</span>}
          {outSec != null && outSec < duration && <span className="marker-tag">OUT {mmss(outSec)}</span>}
        </div>
      )}
    </div>
  )
}
