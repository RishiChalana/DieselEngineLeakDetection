import { RECOMMENDED_ACTIONS, ZONE_LABELS } from '../../lib/constants.js'

export default function StatusPanel({ flag, zone, confidence, isSteady, zScores, bufferState }) {
  const isPass = flag === 'PASS'
  const isWarn = flag === 'WARNING'
  const isFail = flag === 'FAIL'
  const isIdle = !flag || flag === 'IDLE'

  const flagText  = isFail ? 'FAIL' : isWarn ? 'WARNING' : isPass ? 'PASS' : 'IDLE'
  const flagColor = isFail ? '#FF3B30' : isWarn ? '#ffd100' : isPass ? '#34C759' : '#9a9077'

  const panelBorder = isFail
    ? 'border-industrial-red/30'
    : isWarn
    ? 'border-primary-container/20'
    : 'border-white/10'

  const bgOverlay = isFail
    ? 'rgba(255,59,48,0.08)'
    : isWarn
    ? 'rgba(255,209,0,0.05)'
    : isPass
    ? 'rgba(52,199,89,0.05)'
    : 'transparent'

  const zoneLabel  = zone ? ZONE_LABELS[zone]         : '—'
  const action     = zone ? RECOMMENDED_ACTIONS[zone] : 'Monitoring in progress. Awaiting first stable window result.'

  const advisoryBorder = isFail
    ? 'border-l-4 border-industrial-red'
    : isWarn
    ? 'border-l-4 border-primary-container'
    : 'border-l-4 border-white/10'

  const pct = confidence !== undefined ? Math.round(confidence * 100) : 0

  const zCards = [
    { id: 'boost',       label: 'Boost',  val: zScores?.boost },
    { id: 'dpf',         label: 'DPF',    val: zScores?.dpf },
    { id: 'maf',         label: 'MAF',    val: zScores?.maf },
    { id: 'exhaust',     label: 'Exhaust',val: zScores?.exhaust },
    { id: 'mahalanobis', label: 'Mahal.', val: zScores?.mahalanobis },
    { id: 'svm',         label: 'SVM',    val: zScores?.svm },
  ]

  function zColor(v) {
    if (v === undefined || v === null) return 'text-primary-container'
    const THRESH = 6.3156
    if (v >= THRESH)       return 'text-industrial-red'
    if (v >= THRESH * 0.6) return 'text-primary-container'
    return 'text-primary-container/70'
  }

  return (
    <div className="flex flex-col gap-panel-gap h-full">
      {/* Status badge */}
      <div className={`panel-glass rounded-lg overflow-hidden shadow-2xl relative flex-shrink-0`}>
        <div className="absolute inset-0" style={{ background: bgOverlay }} />
        <div className={`relative p-8 flex flex-col items-center justify-center border-b ${panelBorder}`}>
          <span
            className={`font-display-lg font-black text-[64px] leading-none mb-2 tracking-tighter ${isFail ? 'critical-text-blink' : ''}`}
            style={{ color: flagColor }}
          >
            {flagText}
          </span>
          <span
            className="font-label-caps uppercase tracking-[0.4em] text-[10px]"
            style={{ color: `${flagColor}B3` }}
          >
            {isFail ? 'Critical System Fault' : isWarn ? 'Anomaly Detected' : isPass ? 'System Nominal' : 'Awaiting Data'}
          </span>
        </div>

        {/* Diagnosis + z-cards */}
        <div className="p-6 inner-panel-gradient">
          <div className="font-label-caps text-on-surface-variant mb-3">CURRENT DIAGNOSIS</div>
          <div className="font-headline-md text-white/90 uppercase text-[15px] leading-tight">{zoneLabel}</div>

          {(isWarn || isFail) && (
            <div className="mt-8">
              <div className="flex justify-between items-end mb-3">
                <span className="font-label-caps text-on-surface-variant">CONFIDENCE INTERVAL</span>
                <span className="font-body-fixed text-primary-container text-[18px] font-bold">{pct}%</span>
              </div>
              <div className="h-1.5 bg-white/5 rounded-full overflow-hidden">
                <div
                  className="h-full bg-primary-container transition-all duration-500"
                  style={{ width: `${pct}%` }}
                />
              </div>
            </div>
          )}

          {/* Subsystem z-score cards */}
          <div className="mt-6 grid grid-cols-2 gap-2">
            {zCards.map((c) => (
              <div key={c.id} className="inner-panel-gradient p-3 flex flex-col gap-1">
                <span className="font-label-caps text-[9px] text-on-surface-variant uppercase tracking-widest">{c.label}</span>
                <span className={`font-body-fixed text-[14px] font-bold ${zColor(c.val)}`}>
                  {c.val !== undefined ? c.val.toFixed(2) : '—'}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Protocol advisory */}
      <div className={`panel-glass p-6 rounded-lg flex-shrink-0 ${advisoryBorder}`}>
        <div className={`font-label-caps mb-3 tracking-widest ${isFail || isWarn ? 'text-primary-container' : 'text-on-surface-variant'}`}>
          PROTOCOL ADVISORY
        </div>
        <p className="font-body-std text-on-surface/80 text-[13px] leading-relaxed font-light">{action}</p>
      </div>

      {/* Steady state indicator */}
      <div className="panel-glass p-5 rounded-lg flex items-center justify-between flex-shrink-0">
        <div className="flex items-center gap-4">
          <div
            className={`w-2.5 h-2.5 rounded-full transition-all ${
              isSteady
                ? 'bg-industrial-green/60 shadow-[0_0_8px_rgba(52,199,89,0.3)]'
                : bufferState
                ? 'bg-primary-container/60 animate-pulse'
                : 'bg-on-surface-variant/30'
            }`}
          />
          <span
            className={`font-label-caps uppercase tracking-widest text-[10px] ${
              isSteady ? 'text-white/70' : bufferState ? 'text-primary-container/70' : 'text-white/40'
            }`}
          >
            {isSteady ? 'Steady State Validated' : bufferState ? `Buffering ${bufferState}` : 'Awaiting Stability'}
          </span>
        </div>
        <span
          className={`material-symbols-outlined scale-90 ${
            isSteady ? 'text-industrial-green/80' : bufferState ? 'text-primary-container/60' : 'text-on-surface-variant/30'
          }`}
        >
          {isSteady ? 'verified' : 'pending'}
        </span>
      </div>
    </div>
  )
}
