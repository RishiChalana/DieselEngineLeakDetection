import { ZONE_LABELS } from '../../lib/constants.js'

const ZONE_IDS = ['zone_1', 'zone_2', 'zone_3', 'zone_4']
const ZONE_NUM = { zone_1: '01', zone_2: '02', zone_3: '03', zone_4: '04' }

export default function ZoneConfidenceBars({ zoneScores, detectedZone }) {
  const max = zoneScores
    ? Math.max(...ZONE_IDS.map((z) => zoneScores[z] || 0), 0.001)
    : 0.001

  return (
    <div className="h-56 panel-glass p-6 rounded-lg overflow-hidden flex-shrink-0">
      <div className="font-label-caps text-on-surface-variant/60 mb-6 tracking-widest">
        PROBABILITY DENSITY BY ZONE
      </div>
      <div className="space-y-4">
        {ZONE_IDS.map((zid) => {
          const score  = zoneScores ? (zoneScores[zid] || 0) : 0
          const pct    = zoneScores ? Math.round((score / max) * 100) : 0
          const isTop  = zid === detectedZone
          return (
            <div key={zid} className="flex items-center gap-6">
              <span
                className={`w-20 font-label-caps text-[10px] tracking-widest ${
                  isTop ? 'text-primary-container' : 'text-white/40'
                }`}
              >
                ZONE {ZONE_NUM[zid]}
              </span>
              <div className="flex-1 h-1 bg-white/5 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-700 ${
                    isTop
                      ? 'bg-primary-container shadow-[0_0_8px_rgba(255,209,0,0.4)]'
                      : 'bg-white/10'
                  }`}
                  style={{ width: `${pct}%` }}
                />
              </div>
              <span
                className={`w-12 font-body-fixed text-[10px] text-right transition-colors ${
                  isTop ? 'text-primary-container font-bold text-[11px]' : 'text-on-surface-variant'
                }`}
              >
                {pct}%
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
