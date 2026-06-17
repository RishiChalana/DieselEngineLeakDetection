import { useRef, useEffect } from 'react'
import { ANOMALY_THRESHOLD } from '../../lib/constants.js'

const CHART_MAX_Z  = 12
const CHART_POINTS = 60

export default function AnomalyChart({ points }) {
  const canvasRef = useRef(null)

  function draw(canvas, pts) {
    const dpr = window.devicePixelRatio || 1
    const W   = canvas.offsetWidth
    const H   = canvas.offsetHeight
    canvas.width  = W * dpr
    canvas.height = H * dpr
    const ctx = canvas.getContext('2d')
    ctx.scale(dpr, dpr)

    const pad = { left: 38, right: 12, top: 12, bottom: 28 }
    const cW  = W - pad.left - pad.right
    const cH  = H - pad.top  - pad.bottom

    ctx.clearRect(0, 0, W, H)
    ctx.fillStyle = '#050505'
    ctx.fillRect(0, 0, W, H)

    // Grid
    ctx.strokeStyle = 'rgba(255,255,255,0.03)'
    ctx.lineWidth = 1
    for (let i = 0; i <= 4; i++) {
      const y = pad.top + cH * i / 4
      ctx.beginPath(); ctx.moveTo(pad.left, y); ctx.lineTo(W - pad.right, y); ctx.stroke()
    }

    // Threshold line
    const tyFrac = 1 - ANOMALY_THRESHOLD / CHART_MAX_Z
    const tY = pad.top + cH * tyFrac
    ctx.setLineDash([4, 4])
    ctx.strokeStyle = 'rgba(255,59,48,0.4)'
    ctx.lineWidth = 1
    ctx.beginPath(); ctx.moveTo(pad.left, tY); ctx.lineTo(W - pad.right, tY); ctx.stroke()
    ctx.setLineDash([])
    ctx.fillStyle = 'rgba(255,59,48,0.5)'
    ctx.font = '9px JetBrains Mono'
    ctx.textAlign = 'right'
    ctx.fillText('6.32σ', W - pad.right - 2, tY - 3)

    // Y-axis labels
    ctx.fillStyle = 'rgba(255,255,255,0.15)'
    ctx.font = '9px JetBrains Mono'
    for (let i = 0; i <= 4; i++) {
      const v = CHART_MAX_Z * (1 - i / 4)
      ctx.textAlign = 'right'
      ctx.fillText(v.toFixed(0), pad.left - 4, pad.top + cH * i / 4 + 3)
    }

    if (!pts || pts.length < 2) return

    const n = pts.length
    const startIdx = Math.max(0, CHART_POINTS - n)

    function ptX(i) { return pad.left + (i / (CHART_POINTS - 1)) * cW }
    function ptY(z) { return pad.top + cH * (1 - Math.min(z, CHART_MAX_Z) / CHART_MAX_Z) }

    // Gradient fill
    const grad = ctx.createLinearGradient(0, pad.top, 0, H - pad.bottom)
    grad.addColorStop(0, 'rgba(255,209,0,0.12)')
    grad.addColorStop(1, 'rgba(255,209,0,0)')

    ctx.beginPath()
    pts.forEach((pt, j) => {
      const i = startIdx + j
      j === 0 ? ctx.moveTo(ptX(i), ptY(pt.z)) : ctx.lineTo(ptX(i), ptY(pt.z))
    })
    const lastIdx = startIdx + n - 1
    ctx.lineTo(ptX(lastIdx), H - pad.bottom)
    ctx.lineTo(ptX(startIdx), H - pad.bottom)
    ctx.closePath()
    ctx.fillStyle = grad
    ctx.fill()

    // Line
    ctx.beginPath()
    pts.forEach((pt, j) => {
      const i = startIdx + j
      j === 0 ? ctx.moveTo(ptX(i), ptY(pt.z)) : ctx.lineTo(ptX(i), ptY(pt.z))
    })
    ctx.strokeStyle = 'rgba(255,209,0,0.85)'
    ctx.lineWidth = 1.5
    ctx.stroke()

    // Dots
    pts.forEach((pt, j) => {
      const i = startIdx + j
      ctx.beginPath()
      ctx.arc(ptX(i), ptY(pt.z), 2, 0, Math.PI * 2)
      ctx.fillStyle = pt.isLeak ? '#FF3B30' : '#34C759'
      ctx.fill()
    })
  }

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    draw(canvas, points)
  }, [points])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ro = new ResizeObserver(() => draw(canvas, points))
    ro.observe(canvas.parentElement)
    return () => ro.disconnect()
  }, [points])

  return (
    <div className="flex-1 panel-glass rounded-lg flex flex-col overflow-hidden">
      {/* Header */}
      <div className="flex justify-between items-center p-6 border-b border-white/5">
        <div className="flex items-center gap-4">
          <div className="w-1 h-4 bg-primary-container" />
          <div className="font-label-caps text-white tracking-widest">ANOMALY SCORE ANALYSIS — REAL-TIME</div>
        </div>
        <div className="flex gap-6">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-industrial-red" />
            <span className="text-[9px] font-label-caps text-on-surface-variant uppercase tracking-widest">Threshold 6.32σ</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-primary-container" />
            <span className="text-[9px] font-label-caps text-on-surface-variant uppercase tracking-widest">Z-Score Live</span>
          </div>
        </div>
      </div>

      {/* Canvas */}
      <div className="flex-1 p-6 flex flex-col">
        <div className="flex-1 data-inlay-deep rounded-md relative overflow-hidden">
          <canvas ref={canvasRef} className="w-full h-full" />
        </div>
      </div>
    </div>
  )
}
