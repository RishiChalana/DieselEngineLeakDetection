import { useEffect, useState } from 'react'

export default function Header({ flag, engineId, wsState, onLogout }) {
  const [elapsed, setElapsed] = useState(0)

  useEffect(() => {
    const t0 = Date.now()
    const id = setInterval(() => setElapsed(Date.now() - t0), 80)
    return () => clearInterval(id)
  }, [])

  const h  = String(Math.floor(elapsed / 3600000)).padStart(2, '0')
  const m  = String(Math.floor((elapsed % 3600000) / 60000)).padStart(2, '0')
  const s  = String(Math.floor((elapsed % 60000) / 1000)).padStart(2, '0')
  const ms = String(Math.floor((elapsed % 1000) / 10)).padStart(2, '0')

  const dotCls =
    wsState === 'connected' ? 'w-2 h-2 rounded-full bg-industrial-green shadow-[0_0_12px_rgba(52,199,89,0.4)]'
    : wsState === 'error'   ? 'w-2 h-2 rounded-full bg-industrial-red'
    :                         'w-2 h-2 rounded-full bg-on-surface-variant animate-pulse'

  const lblCls =
    wsState === 'connected' ? 'font-label-caps text-[10px] text-industrial-green uppercase tracking-widest'
    : wsState === 'error'   ? 'font-label-caps text-[10px] text-industrial-red uppercase tracking-widest'
    :                         'font-label-caps text-[10px] text-on-surface-variant uppercase tracking-widest'

  const wsLabel =
    wsState === 'connected' ? 'Live Link Established'
    : wsState === 'error'   ? 'Connection Error'
    : wsState === 'pending' ? 'Connecting…'
    :                         'Disconnected'

  const flagBadge =
    flag === 'FAIL'    ? <span className="font-label-caps text-[10px] uppercase tracking-widest px-3 py-1 bg-error-container border border-industrial-red text-industrial-red critical-text-blink flex items-center gap-2"><span className="material-symbols-outlined text-[14px]" style={{fontVariationSettings:"'FILL' 1"}}>warning</span>CRITICAL FAIL</span>
    : flag === 'WARNING' ? <span className="font-label-caps text-[10px] uppercase tracking-widest px-3 py-1 bg-[#2A2000] border border-primary-container text-primary-container animate-pulse">WARNING</span>
    : flag === 'PASS'    ? <span className="font-label-caps text-[10px] uppercase tracking-widest px-3 py-1 bg-[#0A2A0A] border border-industrial-green text-industrial-green">NOMINAL</span>
    : null

  return (
    <header className="h-20 flex items-center justify-between px-margin-desktop bg-[#050505] border-b border-white/5 z-50 shrink-0">
      {/* Left: brand */}
      <div className="flex items-center gap-8">
        <div className="flex items-center gap-3">
          <img src="/logo-icon-96.png" alt="" className="h-8 w-8" aria-hidden="true" />
          <span className="font-display-lg text-primary-container font-black text-[20px] uppercase tracking-wider">CAT</span>
          <div className="h-8 w-px bg-white/10" />
        </div>
        <h1 className="font-display-lg text-white/90 text-[18px] uppercase tracking-[0.3em] font-black">
          Monitoring Dashboard
        </h1>
        {flagBadge && <div className="ml-4">{flagBadge}</div>}
      </div>

      {/* Centre: asset ID + WS status */}
      <div className="flex items-center gap-10">
        <div className="flex flex-col items-end">
          <span className="font-label-caps text-on-surface-variant mb-1">ASSET IDENTIFIER</span>
          <span className="font-body-fixed text-primary-container text-[16px] font-bold tracking-wider">
            {engineId || 'CAT-3412-001'}
          </span>
        </div>
        <div className="h-10 w-px bg-white/10" />
        <div className="flex items-center gap-3 px-4 py-2 rounded-full bg-white/5 border border-white/10">
          <div className={dotCls} />
          <span className={lblCls}>{wsLabel}</span>
        </div>
      </div>

      {/* Right: timer + logout */}
      <div className="flex items-center gap-8">
        <div className="flex flex-col items-end">
          <span className="font-label-caps text-on-surface-variant mb-1">SESSION TIME</span>
          <div className="font-body-fixed text-white text-[18px] tracking-tight font-medium">
            {h}:{m}:{s}.{ms}
          </div>
        </div>
        <button
          onClick={onLogout}
          className="px-8 py-3 bg-transparent border border-industrial-red/50 text-industrial-red font-label-caps text-[10px] tracking-widest hover:bg-industrial-red hover:text-white transition-all duration-300 active:scale-95"
        >
          TERMINATE SESSION
        </button>
      </div>
    </header>
  )
}
