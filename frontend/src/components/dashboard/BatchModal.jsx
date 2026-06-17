import { useState, useRef } from 'react'
import { analyzeSession } from '../../api/session.js'

export default function BatchModal({ isOpen, onClose }) {
  const [csvFile, setCsvFile]   = useState(null)
  const [loading, setLoading]   = useState(false)
  const [result,  setResult]    = useState(null)
  const [error,   setError]     = useState(null)
  const inputRef = useRef(null)
  const dzRef    = useRef(null)

  function reset() {
    setCsvFile(null); setResult(null); setError(null)
    if (inputRef.current) inputRef.current.value = ''
  }

  function handleClose() { reset(); onClose() }

  function handleDrop(e) {
    e.preventDefault()
    dzRef.current?.classList.remove('border-primary-container/70')
    const f = e.dataTransfer.files[0]
    if (f) setCsvFile(f)
  }

  async function handleSubmit() {
    if (!csvFile) { setError('No file selected — please choose a CSV'); return }
    setError(null); setResult(null); setLoading(true)
    try {
      const resp = await analyzeSession(csvFile)
      const data = await resp.json()
      if (resp.ok) {
        setResult(data)
      } else {
        setError((data.error || 'Analysis failed — check CSV format').toUpperCase())
      }
    } catch {
      setError('CONNECTION FAILED — VERIFY SERVER IS RUNNING')
    } finally {
      setLoading(false)
    }
  }

  function downloadReport() {
    if (!result) return
    const blob = new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = `leakguard-report-${Date.now()}.json`
    a.click()
  }

  if (!isOpen) return null

  const gn  = result?.header?.go_nogo || result?.go_nogo
  const summary = result?.session_summary || result?.recommendation

  return (
    <div
      className="fixed inset-0 z-[300] flex items-center justify-center modal-backdrop"
      onClick={(e) => { if (e.target === e.currentTarget) handleClose() }}
    >
      <div className="panel-glass rounded-lg w-full max-w-lg mx-4 overflow-hidden">
        {/* Header */}
        <div className="p-6 border-b border-white/5 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="material-symbols-outlined text-primary-container">upload_file</span>
            <span className="font-label-caps text-white uppercase tracking-widest">BATCH SESSION ANALYSIS</span>
          </div>
          <button onClick={handleClose} className="text-on-surface-variant hover:text-white">
            <span className="material-symbols-outlined">close</span>
          </button>
        </div>

        <div className="p-6 space-y-6">
          <p className="font-body-std text-on-surface/70 text-[13px]">
            Upload a CSV with all 12 sensor columns. Receive a structured Go/No-Go session report with zone-level leak analysis.
          </p>

          {/* Drop zone */}
          <div
            ref={dzRef}
            onClick={() => inputRef.current?.click()}
            onDragOver={(e) => { e.preventDefault(); dzRef.current?.classList.add('border-primary-container/70') }}
            onDragLeave={() => dzRef.current?.classList.remove('border-primary-container/70')}
            onDrop={handleDrop}
            className="border-2 border-dashed border-white/10 rounded-lg p-8 text-center hover:border-primary-container/50 transition-colors cursor-pointer"
          >
            <span className="material-symbols-outlined text-primary-container text-[48px] mb-4 block">cloud_upload</span>
            <p className="font-label-caps text-on-surface-variant uppercase tracking-widest text-[11px]">
              Click to select CSV or drag &amp; drop
            </p>
            <p className="font-body-fixed text-[11px] text-on-surface-variant/50 mt-2">
              {csvFile ? csvFile.name : 'No file selected'}
            </p>
          </div>
          <input
            ref={inputRef}
            type="file"
            accept=".csv"
            className="hidden"
            onChange={(e) => setCsvFile(e.target.files[0])}
          />

          {/* Result */}
          {result && (
            <div className="inner-panel-gradient p-4 rounded-lg space-y-3">
              <div className="flex items-center justify-between">
                <span className="font-label-caps text-[10px] text-on-surface-variant uppercase tracking-widest">Go/No-Go</span>
                <span
                  className={`font-label-caps text-[14px] font-black uppercase tracking-widest ${
                    gn === 'GO' ? 'text-industrial-green' : 'text-industrial-red'
                  }`}
                >
                  {gn || '—'}
                </span>
              </div>
              {summary && (
                <div className="text-[12px] text-on-surface/70 font-body-fixed whitespace-pre-wrap">
                  {typeof summary === 'object' ? JSON.stringify(summary, null, 2) : String(summary).substring(0, 400)}
                </div>
              )}
              <button
                onClick={downloadReport}
                className="font-label-caps text-[10px] text-primary-container hover:underline uppercase tracking-widest flex items-center gap-1"
              >
                <span className="material-symbols-outlined text-[14px]">download</span>
                DOWNLOAD REPORT
              </button>
            </div>
          )}

          {/* Error */}
          {error && (
            <div className="p-3 bg-error-container border border-error rounded">
              <span className="font-label-caps text-[10px] text-error uppercase tracking-widest">{error}</span>
            </div>
          )}

          <button
            onClick={handleSubmit}
            disabled={loading}
            className="w-full bg-primary-container text-on-primary font-label-caps text-[11px] uppercase tracking-widest py-4 hover:opacity-90 active:scale-[0.98] transition-all disabled:opacity-60"
          >
            {loading ? 'Analysing…' : 'Run Analysis'}
          </button>
        </div>
      </div>
    </div>
  )
}
