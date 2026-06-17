export default function Footer({ wsState }) {
  const dotCls = wsState === 'connected'
    ? 'w-1.5 h-1.5 rounded-full bg-industrial-green opacity-80'
    : wsState === 'error'
    ? 'w-1.5 h-1.5 rounded-full bg-industrial-red opacity-80'
    : 'w-1.5 h-1.5 rounded-full bg-on-surface-variant opacity-50'

  const statusTxt = wsState === 'connected'
    ? 'Core Systems: Nominal'
    : wsState === 'error'
    ? 'Core Systems: Error'
    : 'Core Systems: Initialising'

  return (
    <footer className="h-10 flex items-center justify-between px-margin-desktop bg-[#050505] border-t border-white/5 z-50 shrink-0">
      <div className="font-body-fixed text-[9px] text-on-surface-variant/60 uppercase tracking-[0.2em] font-light">
        © {new Date().getFullYear()} CATERPILLAR INC. | PROPRIETARY INDUSTRIAL DIAGNOSTICS SYSTEM
      </div>
      <div className="flex gap-10 font-label-caps text-[9px] text-on-surface-variant/60 uppercase tracking-widest">
        <div className="flex items-center gap-2">
          <div className={dotCls} />
          <span>{statusTxt}</span>
        </div>
      </div>
    </footer>
  )
}
