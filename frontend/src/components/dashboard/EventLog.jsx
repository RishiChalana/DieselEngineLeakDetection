import { useRef, useEffect } from 'react'

function entryStyle(flag) {
  if (flag === 'CRITICAL' || flag === 'FAIL') {
    return {
      wrap: 'p-3 bg-industrial-red/10 border-l-2 border-industrial-red flex flex-col gap-1',
      ts:   'font-body-fixed text-[11px] text-industrial-red font-bold',
      fl:   'text-[9px] font-label-caps text-industrial-red tracking-widest font-black',
      msg:  'text-[9px] text-industrial-red/70 uppercase',
    }
  }
  if (flag === 'WARNING') {
    return {
      wrap: 'flex items-center justify-between p-3 border-b border-white/[0.03]',
      ts:   'font-body-fixed text-[11px] text-on-surface-variant',
      fl:   'text-[9px] font-label-caps text-yellow-500/70 tracking-widest',
      msg:  null,
    }
  }
  if (flag === 'NOMINAL' || flag === 'PASS') {
    return {
      wrap: 'flex items-center justify-between p-3 border-b border-white/[0.03]',
      ts:   'font-body-fixed text-[11px] text-on-surface-variant',
      fl:   'text-[9px] font-label-caps text-industrial-green/70 tracking-widest',
      msg:  null,
    }
  }
  return {
    wrap: 'flex items-center justify-between p-3 border-b border-white/[0.03]',
    ts:   'font-body-fixed text-[11px] text-on-surface-variant',
    fl:   'text-[9px] font-label-caps text-on-surface-variant/50 tracking-widest',
    msg:  null,
  }
}

export default function EventLog({ events }) {
  const logRef = useRef(null)

  function exportLog() {
    if (!events.length) return
    const lines = events.map((e) => `${e.ts}\t${e.flag}\t${e.message || ''}`)
    const blob = new Blob(['TIMESTAMP\tFLAG\tMESSAGE\n' + lines.join('\n')], { type: 'text/plain' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = `leakguard-session-${Date.now()}.tsv`
    a.click()
  }

  return (
    <div className="flex-1 panel-glass rounded-lg flex flex-col overflow-hidden min-h-0">
      <div className="p-5 border-b border-white/5 bg-black/20 flex items-center justify-between flex-shrink-0">
        <span className="font-label-caps text-white/80 tracking-[0.2em]">EVENT LOG</span>
        <button
          onClick={exportLog}
          className="font-label-caps text-[9px] text-on-surface-variant hover:text-primary-container uppercase tracking-widest transition-colors flex items-center gap-1"
        >
          <span className="material-symbols-outlined text-[14px]">download</span>
          EXPORT
        </button>
      </div>
      <div ref={logRef} className="flex-1 overflow-y-auto p-4 space-y-1">
        {events.length === 0 ? (
          <div className="flex items-center justify-between p-3 border-b border-white/[0.03]">
            <span className="font-body-fixed text-[11px] text-on-surface-variant">—</span>
            <span className="text-[9px] font-label-caps text-on-surface-variant/40 tracking-widest">AWAITING</span>
          </div>
        ) : (
          events.slice(0, 60).map((e, i) => {
            const s = entryStyle(e.flag)
            const isCritFail = e.flag === 'CRITICAL' || e.flag === 'FAIL'
            return (
              <div key={i} className={s.wrap}>
                {isCritFail ? (
                  <>
                    <div className="flex items-center justify-between">
                      <span className={s.ts}>{e.ts}</span>
                      <span className={s.fl}>{e.flag}</span>
                    </div>
                    {e.message && <span className={s.msg}>{e.message}</span>}
                  </>
                ) : (
                  <>
                    <span className={s.ts}>{e.ts}</span>
                    <span className={s.fl}>
                      {e.flag}{e.message ? ` — ${e.message}` : ''}
                    </span>
                  </>
                )}
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}
