import { useState } from 'react'

const NAV = [
  { icon: 'dashboard',             label: 'DASHBOARD',      active: true  },
  { icon: 'analytics',             label: 'TELEMETRY',      active: false },
  { icon: 'precision_manufacturing',label: 'DIAGNOSTICS',   active: false },
  { icon: 'history',               label: 'HISTORY',        active: false },
  { icon: 'upload_file',           label: 'BATCH ANALYSIS', active: false, onClick: 'batch' },
]

export default function Sidebar({
  isConnected,
  onStart,
  onStop,
  leakMode,
  leakType,
  onLeakToggle,
  onLeakTypeChange,
  engineModel,
  engineType,
  onEngineModelChange,
  onEngineTypeChange,
  onBatchOpen,
}) {
  return (
    <aside className="flex flex-col h-full py-panel-gap bg-surface border-r border-outline w-64 shrink-0">
      {/* Header */}
      <div className="px-6 py-4 mb-4">
        <div className="font-label-caps text-label-caps uppercase text-primary-container mb-1">CONTROL PANEL</div>
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-industrial-green' : 'bg-on-surface-variant/40'} ${isConnected ? '' : 'animate-pulse'}`} />
          <div className="font-body-fixed text-[10px] text-on-surface-variant tracking-wider uppercase">
            {isConnected ? 'SESSION ACTIVE' : 'SYSTEM READY'}
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-grow flex flex-col gap-1 px-2">
        {NAV.map((item) => (
          <button
            key={item.label}
            onClick={item.onClick === 'batch' ? onBatchOpen : undefined}
            className={`w-full px-4 py-3 flex items-center gap-3 transition-all text-left ${
              item.active
                ? 'bg-primary-container text-on-primary font-bold'
                : 'text-on-surface-variant hover:text-primary-container hover:bg-surface-container-high'
            }`}
          >
            <span className="material-symbols-outlined">{item.icon}</span>
            <span className="font-label-caps text-label-caps uppercase">{item.label}</span>
          </button>
        ))}
      </nav>

      {/* Engine inputs */}
      <div className="px-4 mt-4 space-y-3">
        <div className="space-y-1">
          <label className="font-label-caps text-[9px] text-on-surface-variant uppercase tracking-widest">Engine Model</label>
          <input
            className="w-full bg-surface-container border border-outline/50 text-on-surface font-body-fixed text-[12px] px-3 py-2 focus:border-primary-container focus:outline-none"
            value={engineModel}
            onChange={(e) => onEngineModelChange(e.target.value)}
          />
        </div>

        {/* Leak injection toggle */}
        <div className="flex items-center justify-between bg-white/[0.03] border border-white/5 px-3 py-2">
          <span className="font-label-caps text-[9px] text-white/60 uppercase tracking-widest">Inject Leak Sim</span>
          <button
            onClick={onLeakToggle}
            className={`relative inline-flex h-5 w-10 items-center rounded-full transition-colors ${
              leakMode === 'leak' ? 'bg-primary-container/20' : 'bg-white/10'
            }`}
          >
            <span
              className={`inline-block h-3 w-3 transform rounded-full transition duration-200 ${
                leakMode === 'leak' ? 'translate-x-6 bg-primary-container' : 'translate-x-1 bg-white/40'
              }`}
            />
          </button>
        </div>

        {/* Leak type buttons — shown when leak enabled */}
        {leakMode === 'leak' && (
          <div className="space-y-1">
            <span className="font-label-caps text-[9px] text-on-surface-variant uppercase tracking-widest">Leak Type</span>
            <div className="grid grid-cols-3 gap-1">
              {['charge_air', 'exhaust', 'precompressor'].map((lt) => (
                <button
                  key={lt}
                  onClick={() => onLeakTypeChange(lt)}
                  className={`py-2 font-label-caps text-[9px] uppercase tracking-widest border transition-colors ${
                    leakType === lt
                      ? 'border-primary-container text-primary-container'
                      : 'border-white/10 text-on-surface-variant hover:border-primary-container hover:text-primary-container'
                  }`}
                >
                  {lt === 'charge_air' ? 'Charge' : lt === 'exhaust' ? 'Exhaust' : 'Pre-comp'}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Start / Stop */}
        <div className="flex gap-2">
          <button
            onClick={onStart}
            disabled={isConnected}
            className="flex-1 py-3 bg-primary-container text-on-primary font-label-caps text-[10px] uppercase tracking-widest disabled:opacity-40 hover:opacity-90 active:scale-[0.98] transition-all"
          >
            START
          </button>
          <button
            onClick={onStop}
            disabled={!isConnected}
            className="flex-1 py-3 border border-industrial-red/50 text-industrial-red font-label-caps text-[10px] uppercase tracking-widest disabled:opacity-40 hover:bg-industrial-red hover:text-white transition-all"
          >
            STOP
          </button>
        </div>
      </div>

      {/* Emergency stop */}
      <div className="px-4 pb-4 mt-4">
        <button
          onClick={onStop}
          className="w-full py-4 bg-industrial-red text-white font-black font-label-caps uppercase tracking-widest hover:brightness-110 active:scale-95 transition-all border-2 border-white/20 shadow-[0_0_15px_rgba(255,59,48,0.5)]"
        >
          EMERGENCY STOP
        </button>
      </div>
    </aside>
  )
}
