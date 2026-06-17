const CELLS = [
  { key: 'rpm',            label: 'Rotation', unit: 'RPM',   fmt: (v) => Math.round(v),      color: 'text-white' },
  { key: 'MAF',            label: 'Air Flow',  unit: 'G/S',   fmt: (v) => v.toFixed(1),        color: 'text-primary-container' },
  { key: 'boost_pressure', label: 'Boost Pres.',unit: 'BAR', fmt: (v) => v.toFixed(2),        color: 'text-primary-container' },
  { key: 'MAP',            label: 'Manifold',  unit: 'BAR',   fmt: (v) => v.toFixed(2),        color: 'text-white' },
  { key: 'EGT',            label: 'Exhaust',   unit: 'K',     fmt: (v) => Math.round(v),      color: 'text-white' },
  { key: 'turbo_speed',    label: 'Turbo Sp.', unit: 'KRPM',  fmt: (v) => (v / 1000).toFixed(1), color: 'text-white' },
]

export default function SensorGrid({ sample }) {
  return (
    <div className="h-72 panel-glass rounded-lg flex flex-col overflow-hidden flex-shrink-0">
      <div className="p-5 border-b border-white/5 bg-black/20">
        <span className="font-label-caps text-white/80 tracking-[0.2em]">SENSORY TELEMETRY</span>
      </div>
      <div className="flex-1 grid grid-cols-2 p-1 gap-1">
        {CELLS.map((cell) => {
          const raw = sample?.[cell.key]
          const val = raw !== undefined ? cell.fmt(raw) : '—'
          return (
            <div key={cell.key} className="inner-panel-gradient p-4 flex flex-col justify-between">
              <div className="text-[9px] font-label-caps text-on-surface-variant uppercase tracking-widest">
                {cell.label}
              </div>
              <div className="flex items-baseline gap-1">
                <span className={`font-metric-lg ${cell.color} text-[22px]`}>{val}</span>
                <span className="text-[9px] text-on-surface-variant font-body-fixed">{cell.unit}</span>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
