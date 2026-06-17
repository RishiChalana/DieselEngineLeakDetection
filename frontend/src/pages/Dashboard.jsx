import { useState, useCallback, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useEngineWebSocket } from '../hooks/useEngineWebSocket.js'
import Header             from '../components/layout/Header.jsx'
import Sidebar            from '../components/layout/Sidebar.jsx'
import Footer             from '../components/layout/Footer.jsx'
import StatusPanel        from '../components/dashboard/StatusPanel.jsx'
import AnomalyChart       from '../components/dashboard/AnomalyChart.jsx'
import ZoneConfidenceBars from '../components/dashboard/ZoneConfidenceBars.jsx'
import SensorGrid         from '../components/dashboard/SensorGrid.jsx'
import EventLog           from '../components/dashboard/EventLog.jsx'
import BatchModal         from '../components/dashboard/BatchModal.jsx'

export default function Dashboard() {
  const navigate = useNavigate()

  // Auth guard
  useEffect(() => {
    if (!sessionStorage.getItem('cat_token')) navigate('/login', { replace: true })
  }, [navigate])

  // ── Session state ────────────────────────────────────────────────────
  const [flag,        setFlag]       = useState('IDLE')
  const [zone,        setZone]       = useState(null)
  const [zoneScores,  setZoneScores] = useState(null)
  const [confidence,  setConf]       = useState(0)
  const [isSteady,    setIsSteady]   = useState(false)
  const [bufferState, setBufState]   = useState(null)
  const [zScores,     setZScores]    = useState({})
  const [chartPoints, setChartPts]   = useState([])
  const [events,      setEvents]     = useState([])
  const [sample,      setSample]     = useState(null)
  const [leakMode,    setLeakMode]   = useState('healthy')
  const [leakType,    setLeakType]   = useState('charge_air')
  const [engineModel, setEngModel]   = useState('CAT-3412-001')
  const [isBatchOpen, setBatch]      = useState(false)
  const [wsState,     setWsState]    = useState('idle')
  const [showCrit,    setShowCrit]   = useState(false)
  const [critCount,   setCritCount]  = useState(0)
  const [testResult,  setTestResult] = useState(null)

  const disconnectRef = useRef(null)

  function tsNow() {
    return new Date().toLocaleTimeString('en-US', { hour12: false })
  }

  function addEvent(evFlag, message) {
    setEvents((prev) => [{ ts: tsNow(), flag: evFlag, message: message || '' }, ...prev].slice(0, 60))
  }

  // onMessage must not capture disconnect directly (defined after hook call)
  // — use disconnectRef instead.
  const onMessage = useCallback((msg) => {
    switch (msg.type) {
      case 'engine_registered':
        setWsState('connected')
        setEvents((prev) => [{ ts: tsNow(), flag: 'NOMINAL', message: 'Engine registered — streaming active' }, ...prev].slice(0, 60))
        break

      case 'buffering':
        setBufState(`${msg.buffered}/${msg.required}`)
        break

      case 'unstable':
        setIsSteady(false)
        setEvents((prev) => [{ ts: tsNow(), flag: 'WARNING', message: 'Transient state — stability check failed' }, ...prev].slice(0, 60))
        break

      case 'sample_result': {
        const z = msg.z_scores || {}
        setZScores(z)
        setConf(msg.confidence || 0)
        setBufState(null)
        const cum = z.cumulative ?? 0
        setChartPts((prev) => [...prev, { z: cum, pass: cum < 6.3156 }].slice(-60))
        break
      }

      case 'window_result': {
        const wf = msg.flag || (msg.window_leak ? 'FAIL' : 'PASS')
        setFlag(wf)
        setIsSteady(msg.is_steady_state || false)
        if (msg.window_leak && msg.zone) {
          setZone(msg.zone)
          if (msg.zone_scores) setZoneScores(msg.zone_scores)
        }
        const note = msg.zone_label ? `Zone: ${msg.zone_label}` : undefined
        setEvents((prev) => [{ ts: tsNow(), flag: wf, message: note || '' }, ...prev].slice(0, 60))
        break
      }

      case 'critical_alert':
        setFlag('FAIL')
        setCritCount(msg.consecutive_fail_windows)
        setShowCrit(true)
        setEvents((prev) => [
          { ts: tsNow(), flag: 'CRITICAL', message: `${msg.consecutive_fail_windows} consecutive FAIL windows` },
          ...prev,
        ].slice(0, 60))
        break

      case 'test_complete':
        setTestResult(msg)
        disconnectRef.current?.()
        setWsState('disconnected')
        setEvents((prev) => [
          { ts: tsNow(), flag: msg.leak_detected ? 'FAIL' : 'PASS', message: `Session complete: ${msg.leak_detected ? 'LEAK CONFIRMED' : 'NO LEAK'}` },
          ...prev,
        ].slice(0, 60))
        break

      default:
        break
    }
  }, [])

  const onSample = useCallback((s) => setSample(s), [])

  const { connect, disconnect, isConnected, setLeakConfig } = useEngineWebSocket({
    engineModel,
    engineType: 'diesel',
    onMessage,
    onSample,
  })

  // Keep disconnectRef current
  disconnectRef.current = disconnect

  // Detect unexpected disconnect (WS closed without test_complete)
  const prevConn = useRef(false)
  useEffect(() => {
    if (!isConnected && prevConn.current && wsState === 'connected') {
      setWsState('disconnected')
    }
    prevConn.current = isConnected
  }, [isConnected, wsState])

  // ── Handlers ─────────────────────────────────────────────────────────
  function handleStart() {
    setFlag('IDLE')
    setZone(null)
    setZoneScores(null)
    setChartPts([])
    setEvents([])
    setZScores({})
    setBufState(null)
    setIsSteady(false)
    setShowCrit(false)
    setTestResult(null)
    setSample(null)
    setWsState('pending')
    connect()
  }

  function handleStop() {
    disconnect()
    setWsState('disconnected')
    setEvents((prev) => [{ ts: tsNow(), flag: 'NOMINAL', message: 'Session terminated by operator' }, ...prev].slice(0, 60))
  }

  function handleLeakToggle() {
    const next = leakMode === 'healthy' ? 'leak' : 'healthy'
    setLeakMode(next)
    setLeakConfig(next, leakType)
  }

  function handleLeakType(lt) {
    setLeakType(lt)
    setLeakConfig(leakMode, lt)
  }

  function handleLogout() {
    disconnect()
    sessionStorage.clear()
    navigate('/login', { replace: true })
  }

  function handleNewSession() {
    setTestResult(null)
    setFlag('IDLE')
    setZone(null)
    setZoneScores(null)
    setChartPts([])
    setEvents([])
  }

  const username = sessionStorage.getItem('cat_username') || 'OPERATOR'

  return (
    <div
      className="h-screen flex flex-col overflow-hidden bg-[#0a0a0a]"
      style={{ color: '#ebe2cf', fontFamily: 'Inter, sans-serif', WebkitFontSmoothing: 'antialiased' }}
    >
      <Header
        flag={flag}
        engineId={engineModel}
        wsState={wsState}
        onLogout={handleLogout}
      />

      {/* Critical alert banner */}
      {showCrit && (
        <div
          className="flex-shrink-0 bg-industrial-red text-white flex items-center justify-between px-margin-desktop py-2 z-[100]"
          style={{ borderBottom: '1px solid rgba(255,255,255,0.2)' }}
        >
          <div className="flex items-center gap-3">
            <span className="material-symbols-outlined" style={{ fontVariationSettings: "'FILL' 1", fontSize: '18px' }}>emergency</span>
            <span className="font-label-caps text-[10px] uppercase tracking-widest">
              CRITICAL ALERT — {critCount} consecutive anomalous windows detected. Immediate inspection required.
            </span>
          </div>
          <button onClick={() => setShowCrit(false)} className="ml-6 text-white/80 hover:text-white">
            <span className="material-symbols-outlined text-[16px]">close</span>
          </button>
        </div>
      )}

      {/* Body */}
      <div className="flex-1 flex overflow-hidden">
        <Sidebar
          isConnected={isConnected}
          onStart={handleStart}
          onStop={handleStop}
          leakMode={leakMode}
          leakType={leakType}
          onLeakToggle={handleLeakToggle}
          onLeakTypeChange={handleLeakType}
          engineModel={engineModel}
          engineType="diesel"
          onEngineModelChange={setEngModel}
          onEngineTypeChange={() => {}}
          onBatchOpen={() => setBatch(true)}
        />

        {/* Three-column main area */}
        <main
          className="flex-1 flex overflow-hidden"
          style={{ padding: '12px', gap: '12px', backgroundColor: '#070707' }}
        >
          {/* Left: Status panel */}
          <aside id="panel-status" className="w-[28%] flex flex-col gap-[12px] overflow-y-auto flex-shrink-0">
            <StatusPanel
              flag={flag}
              zone={zone}
              confidence={confidence}
              isSteady={isSteady}
              zScores={zScores}
              bufferState={bufferState}
            />
          </aside>

          {/* Center: Chart + sensors + events */}
          <section className="flex-1 flex flex-col gap-[12px] min-w-0 overflow-hidden">
            <span id="panel-chart" style={{ display: 'block', height: 0 }} />
            <AnomalyChart points={chartPoints} />
            <SensorGrid sample={sample} />
            <span id="panel-log" style={{ display: 'block', height: 0 }} />
            <EventLog events={events} />
          </section>

          {/* Right: Zone bars + session info + zone key */}
          <aside id="panel-zones" className="w-[24%] flex flex-col gap-[12px] overflow-y-auto flex-shrink-0">
            <ZoneConfidenceBars zoneScores={zoneScores} detectedZone={zone} />

            {/* Session info */}
            <div className="panel-glass rounded-lg p-5 flex-shrink-0">
              <div className="font-label-caps text-on-surface-variant/60 tracking-widest mb-4 text-[10px]">SESSION INFO</div>
              <div className="space-y-3">
                <InfoRow label="Operator"  value={username.toUpperCase()} />
                <InfoRow label="Engine"    value={engineModel} />
                <InfoRow label="Mode"      value={leakMode === 'leak' ? leakType.replace('_', ' ').toUpperCase() : 'HEALTHY'} highlight={leakMode === 'leak'} />
                <InfoRow label="WS Status" value={wsState.toUpperCase()} highlight={wsState === 'connected'} />
                <InfoRow label="Samples"   value={String(chartPoints.length)} />
              </div>
            </div>

            {/* Zone key */}
            <div className="panel-glass rounded-lg p-5 flex-shrink-0">
              <div className="font-label-caps text-on-surface-variant/60 tracking-widest mb-4 text-[10px]">ZONE KEY</div>
              <div className="space-y-2">
                {[
                  { id: 'zone_1', label: 'Pre-Compressor', desc: 'Intake / MAF circuit' },
                  { id: 'zone_2', label: 'Charge-Air',     desc: 'Turbo → intercooler → intake' },
                  { id: 'zone_3', label: 'Exhaust Path',   desc: 'EGT / DPF / exhaust pressure' },
                  { id: 'zone_4', label: 'Test Ducting',   desc: 'Test cell ambient circuit' },
                ].map((z) => (
                  <div
                    key={z.id}
                    className={`px-3 py-2 border-l-2 flex flex-col gap-0.5 ${zone === z.id ? 'border-primary-container' : 'border-white/10'}`}
                  >
                    <span className={`font-label-caps text-[9px] uppercase tracking-widest ${zone === z.id ? 'text-primary-container' : 'text-on-surface-variant'}`}>
                      {z.label}
                    </span>
                    <span className="font-body-fixed text-[9px] text-on-surface-variant/50">{z.desc}</span>
                  </div>
                ))}
              </div>
            </div>
          </aside>
        </main>
      </div>

      <Footer wsState={wsState} />

      {/* Modals */}
      <BatchModal isOpen={isBatchOpen} onClose={() => setBatch(false)} />

      {/* Test complete modal */}
      {testResult && (
        <div className="fixed inset-0 z-[400] flex items-center justify-center modal-backdrop">
          <div className="panel-glass p-8 max-w-md w-full mx-4">
            <div className="text-center mb-6">
              <span
                className="material-symbols-outlined text-[64px] mb-2 block"
                style={{
                  color: testResult.leak_detected ? '#FF3B30' : '#34C759',
                  fontVariationSettings: "'FILL' 1",
                }}
              >
                {testResult.leak_detected ? 'warning' : 'check_circle'}
              </span>
              <h2
                className="font-display-lg font-black text-[28px] uppercase tracking-tighter mb-1"
                style={{ color: testResult.leak_detected ? '#FF3B30' : '#34C759' }}
              >
                {testResult.leak_detected ? 'Leak Confirmed' : 'No Leak Detected'}
              </h2>
              {zone && (
                <p className="font-label-caps text-[10px] text-on-surface-variant uppercase tracking-widest">
                  {zone.replace('_', ' ').toUpperCase()} ISOLATED
                </p>
              )}
            </div>

            <div className="inner-panel-gradient p-4 mb-6 text-[12px] text-on-surface/70 font-body-fixed leading-relaxed">
              {testResult.leak_detected
                ? zone
                  ? `Leak isolated to ${zone.replace(/_/g, ' ')}. Immediate inspection recommended per zone protocol.`
                  : 'Sustained anomaly confirmed. Zone isolation inconclusive — full engine inspection recommended.'
                : 'No sustained anomaly detected across the session. Engine performance within calibrated thresholds.'}
            </div>

            <div className="flex gap-3">
              <button
                onClick={handleNewSession}
                className="flex-1 bg-primary-container text-on-primary font-label-caps text-[10px] uppercase tracking-widest py-4 hover:opacity-90 active:scale-[0.98] transition-all"
              >
                New Session
              </button>
              <button
                onClick={handleLogout}
                className="flex-1 border border-white/10 text-on-surface-variant font-label-caps text-[10px] uppercase tracking-widest py-4 hover:border-white/30 transition-colors"
              >
                Logout
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function InfoRow({ label, value, highlight }) {
  return (
    <div className="flex items-center justify-between">
      <span className="font-label-caps text-[9px] text-on-surface-variant/60 uppercase tracking-widest">{label}</span>
      <span className={`font-body-fixed text-[10px] uppercase ${highlight ? 'text-industrial-green' : 'text-on-surface'}`}>
        {value}
      </span>
    </div>
  )
}
