import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { login as apiLogin, signup as apiSignup } from '../api/auth.js'

export default function Login() {
  const navigate = useNavigate()
  const [tab,         setTab]         = useState('login')
  const [loginUser,   setLoginUser]   = useState('')
  const [loginPwd,    setLoginPwd]    = useState('')
  const [regUser,     setRegUser]     = useState('')
  const [regEmail,    setRegEmail]    = useState('')
  const [regPwd,      setRegPwd]      = useState('')
  const [showLoginPw, setShowLoginPw] = useState(false)
  const [showRegPw,   setShowRegPw]   = useState(false)
  const [loading,     setLoading]     = useState(false)
  const [error,       setError]       = useState('')
  const [success,     setSuccess]     = useState(false)

  useEffect(() => {
    if (sessionStorage.getItem('cat_token')) navigate('/dashboard', { replace: true })
  }, [navigate])

  // Mouse parallax
  useEffect(() => {
    const onMove = (e) => {
      const x = e.clientX / window.innerWidth
      const y = e.clientY / window.innerHeight
      document.body.style.background =
        `radial-gradient(circle at ${x * 100}% ${y * 100}%, #231f14 0%, #110e05 100%)`
    }
    document.addEventListener('mousemove', onMove)
    return () => {
      document.removeEventListener('mousemove', onMove)
      document.body.style.background = ''
    }
  }, [])

  const handleLogin = useCallback(async (e) => {
    e.preventDefault()
    setError('')
    if (!loginUser || !loginPwd) { setError('OPERATOR ID AND ACCESS KEY REQUIRED'); return }
    setLoading(true)
    try {
      const res  = await apiLogin(loginUser, loginPwd)
      const data = await res.json()
      if (res.ok && data.token) {
        sessionStorage.setItem('cat_token',    data.token)
        sessionStorage.setItem('cat_username', loginUser)
        setSuccess(true)
        setTimeout(() => navigate('/dashboard', { replace: true }), 800)
      } else {
        const msg = data.error || (data.non_field_errors?.[0]) || 'AUTHENTICATION FAILED — CHECK CREDENTIALS'
        setError(msg.toUpperCase())
      }
    } catch {
      setError('CONNECTION FAILED — VERIFY SERVER IS RUNNING')
    } finally {
      setLoading(false)
    }
  }, [loginUser, loginPwd, navigate])

  const handleRegister = useCallback(async (e) => {
    e.preventDefault()
    setError('')
    if (!regUser || !regEmail || !regPwd) { setError('ALL FIELDS ARE REQUIRED'); return }
    setLoading(true)
    try {
      const res  = await apiSignup(regUser, regEmail, regPwd)
      const data = await res.json()
      if (res.ok && data.token) {
        sessionStorage.setItem('cat_token',    data.token)
        sessionStorage.setItem('cat_username', regUser)
        setSuccess(true)
        setTimeout(() => navigate('/dashboard', { replace: true }), 800)
      } else {
        const firstVal = Object.values(data)[0]
        const msg = Array.isArray(firstVal) ? firstVal[0] : (firstVal || 'REGISTRATION FAILED')
        setError(String(msg).toUpperCase())
      }
    } catch {
      setError('CONNECTION FAILED — VERIFY SERVER IS RUNNING')
    } finally {
      setLoading(false)
    }
  }, [regUser, regEmail, regPwd, navigate])

  return (
    <div
      className="cinematic-bg min-h-screen flex flex-col overflow-hidden"
      style={{ color: '#ebe2cf', fontFamily: 'Inter, sans-serif', WebkitFontSmoothing: 'antialiased' }}
    >
      {/* Scanline + carbon texture */}
      <div className="fixed inset-0 pointer-events-none z-0">
        <div className="scanline" />
        <div
          className="absolute inset-0 opacity-[0.03]"
          style={{ backgroundImage: "url('https://www.transparenttextures.com/patterns/carbon-fibre.png')" }}
        />
      </div>

      {/* Header */}
      <header
        className="fixed top-0 w-full z-50 flex justify-between items-center px-margin-desktop py-6 border-b border-outline-variant/30 backdrop-blur-sm"
        style={{ backgroundColor: 'rgba(23,19,9,0.4)' }}
      >
        <div className="flex items-center gap-unit">
          <span className="material-symbols-outlined text-primary-container" style={{ fontVariationSettings: "'FILL' 1" }}>shield_with_heart</span>
          <span className="font-headline-md text-[20px] font-bold text-primary-container tracking-tighter uppercase">LeakGuard Industrial</span>
        </div>
        <div className="hidden md:flex items-center gap-6">
          <div className="flex items-center gap-2 px-3 py-1 bg-surface-container border border-outline-variant">
            <div className="w-2 h-2 rounded-full bg-primary-container animate-pulse" />
            <span className="font-label-caps text-label-caps text-on-surface-variant uppercase">System Online</span>
          </div>
          <span className="font-body-fixed text-body-fixed text-on-surface-variant">NODE: CN-H821</span>
        </div>
      </header>

      {/* Main */}
      <main className="flex-grow flex items-center justify-center p-6 relative z-10">
        <div className="w-full max-w-[480px] space-y-panel-gap">
          <div className="glass-panel p-10 flex flex-col items-center">

            {/* Logo */}
            <div className="mb-6 flex flex-col items-center gap-2">
              <span className="material-symbols-outlined text-primary-container text-[48px]" style={{ fontVariationSettings: "'FILL' 1" }}>precision_manufacturing</span>
              <span className="font-label-caps text-label-caps text-on-surface-variant uppercase tracking-widest">Diesel Engine Leak Detection</span>
            </div>

            {/* Tabs */}
            <div className="w-full flex mb-8 border-b border-outline-variant/30">
              {['login', 'register'].map((t) => (
                <button
                  key={t}
                  onClick={() => { setTab(t); setError('') }}
                  className={`flex-1 py-3 font-label-caps text-label-caps uppercase tracking-widest transition-all ${
                    tab === t ? 'tab-active' : 'tab-inactive'
                  }`}
                >
                  {t === 'login' ? 'Login' : 'Register'}
                </button>
              ))}
            </div>

            {/* Error panel */}
            {error && (
              <div className="w-full mb-6 p-4 bg-error-container border border-error flex items-center gap-3">
                <span className="material-symbols-outlined text-error text-[18px]" style={{ fontVariationSettings: "'FILL' 1" }}>error</span>
                <span className="font-label-caps text-label-caps text-error uppercase tracking-widest">{error}</span>
              </div>
            )}

            {/* Success panel */}
            {success && (
              <div className="w-full mb-6 p-4 bg-surface-container border border-outline-variant flex items-center gap-3">
                <span className="material-symbols-outlined text-primary-container text-[18px]" style={{ fontVariationSettings: "'FILL' 1" }}>check_circle</span>
                <span className="font-label-caps text-label-caps text-primary-container uppercase tracking-widest">ACCESS GRANTED — REDIRECTING...</span>
              </div>
            )}

            {/* Login form */}
            {tab === 'login' && (
              <form className="w-full space-y-6" onSubmit={handleLogin}>
                <div className="text-center space-y-2 mb-8">
                  <h1 className="font-headline-md text-[20px] text-on-surface uppercase tracking-widest">Operator Authorization</h1>
                  <p className="font-label-caps text-label-caps text-on-surface-variant">Class III Heavy Machinery Telemetry Access</p>
                </div>

                <Field icon="badge" label="Operator ID" placeholder="EMP-XXXX-XXXX" type="text" value={loginUser} onChange={setLoginUser} autocomplete="username" />
                <PasswordField icon="vpn_key" label="Security Access Key" value={loginPwd} onChange={setLoginPwd} show={showLoginPw} onToggle={() => setShowLoginPw((v) => !v)} autocomplete="current-password" />

                <div className="pt-4">
                  <button
                    type="submit"
                    disabled={loading}
                    className="w-full bg-primary-container text-on-primary-fixed font-headline-md text-[18px] font-bold py-5 uppercase tracking-[0.2em] hover:opacity-90 active:scale-[0.98] transition-all duration-200 flex items-center justify-center gap-3 disabled:opacity-60"
                  >
                    {loading ? 'Authenticating…' : 'Login'}
                    <span className="material-symbols-outlined">login</span>
                  </button>
                </div>
                <div className="flex justify-between items-center pt-4 border-t border-outline-variant/30 mt-8">
                  <span className="font-label-caps text-label-caps text-on-surface-variant uppercase">Don't have access?</span>
                  <button type="button" className="font-label-caps text-label-caps text-primary-container hover:underline uppercase" onClick={() => setTab('register')}>Register</button>
                </div>
              </form>
            )}

            {/* Register form */}
            {tab === 'register' && (
              <form className="w-full space-y-6" onSubmit={handleRegister}>
                <div className="text-center space-y-2 mb-8">
                  <h1 className="font-headline-md text-[20px] text-on-surface uppercase tracking-widest">New Operator Registration</h1>
                  <p className="font-label-caps text-label-caps text-on-surface-variant">Request system access credentials</p>
                </div>

                <Field icon="badge"          label="Operator ID"    placeholder="EMP-XXXX-XXXX"              type="text"  value={regUser}  onChange={setRegUser}  autocomplete="username" />
                <Field icon="alternate_email" label="Email Address"  placeholder="engineer@caterpillar.com"  type="email" value={regEmail} onChange={setRegEmail} autocomplete="email" />
                <PasswordField icon="vpn_key" label="Security Access Key" value={regPwd} onChange={setRegPwd} show={showRegPw} onToggle={() => setShowRegPw((v) => !v)} autocomplete="new-password" />

                <div className="pt-4">
                  <button
                    type="submit"
                    disabled={loading}
                    className="w-full bg-primary-container text-on-primary-fixed font-headline-md text-[18px] font-bold py-5 uppercase tracking-[0.2em] hover:opacity-90 active:scale-[0.98] transition-all duration-200 flex items-center justify-center gap-3 disabled:opacity-60"
                  >
                    {loading ? 'Creating…' : 'Create Account'}
                    <span className="material-symbols-outlined">person_add</span>
                  </button>
                </div>
                <div className="flex justify-between items-center pt-4 border-t border-outline-variant/30 mt-8">
                  <span className="font-label-caps text-label-caps text-on-surface-variant uppercase">Already have access?</span>
                  <button type="button" className="font-label-caps text-label-caps text-primary-container hover:underline uppercase" onClick={() => setTab('login')}>Login</button>
                </div>
              </form>
            )}
          </div>

          {/* Footer glass bar */}
          <div className="flex items-center gap-panel-gap">
            <div className="flex-grow glass-panel py-3 px-6 flex items-center gap-4">
              <span className="material-symbols-outlined text-primary-container text-[18px]" style={{ fontVariationSettings: "'FILL' 1" }}>info</span>
              <span className="font-label-caps text-label-caps text-on-surface-variant uppercase">Secure Session: 256-Bit Encrypted</span>
            </div>
            <div className="glass-panel py-3 px-4 flex items-center gap-2">
              <span className="material-symbols-outlined text-on-surface-variant text-[18px]">language</span>
              <span className="font-label-caps text-label-caps text-on-surface-variant">EN-US</span>
            </div>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer
        className="w-full py-8 px-margin-desktop border-t border-outline-variant/30 flex flex-col md:flex-row justify-between items-center gap-6 backdrop-blur-sm"
        style={{ backgroundColor: 'rgba(17,14,5,0.5)' }}
      >
        <div className="flex items-center gap-8">
          <div className="flex items-center gap-3">
            <div className="w-2 h-2 rounded-full bg-primary-container" />
            <span className="font-label-caps text-label-caps text-on-surface uppercase tracking-widest">CAT Confidential</span>
          </div>
          <p className="font-label-caps text-label-caps text-on-surface-variant uppercase">© 2024 LeakGuard Systems. Precision Engineered for Heavy Industry.</p>
        </div>
        <div className="flex items-center gap-12">
          <div className="flex flex-col items-end">
            <span className="font-label-caps text-[10px] text-on-surface-variant uppercase mb-1">Local Latency</span>
            <span className="font-body-fixed text-body-fixed text-primary-container">—ms</span>
          </div>
          <div className="flex flex-col items-end">
            <span className="font-label-caps text-[10px] text-on-surface-variant uppercase mb-1">Station ID</span>
            <span className="font-body-fixed text-body-fixed text-on-surface uppercase">HMI-UNIT-042</span>
          </div>
        </div>
      </footer>
    </div>
  )
}

function Field({ icon, label, placeholder, type, value, onChange, autocomplete }) {
  return (
    <div className="space-y-unit group">
      <label className="font-label-caps text-label-caps text-on-surface-variant uppercase ml-1">{label}</label>
      <div className="industrial-glow relative flex items-center bg-surface-container-lowest border border-outline-variant/50 focus-within:border-primary-container transition-all duration-200">
        <span className="material-symbols-outlined px-4 text-on-surface-variant">{icon}</span>
        <input
          className="w-full bg-transparent border-none py-4 px-0 font-body-fixed text-body-fixed text-on-surface placeholder:text-outline-variant focus:ring-0 focus:outline-none"
          placeholder={placeholder}
          type={type}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          autoComplete={autocomplete}
        />
      </div>
    </div>
  )
}

function PasswordField({ icon, label, value, onChange, show, onToggle, autocomplete }) {
  return (
    <div className="space-y-unit group">
      <label className="font-label-caps text-label-caps text-on-surface-variant uppercase ml-1">{label}</label>
      <div className="industrial-glow relative flex items-center bg-surface-container-lowest border border-outline-variant/50 focus-within:border-primary-container transition-all duration-200">
        <span className="material-symbols-outlined px-4 text-on-surface-variant">{icon}</span>
        <input
          className="w-full bg-transparent border-none py-4 px-0 font-body-fixed text-body-fixed text-on-surface placeholder:text-outline-variant focus:ring-0 focus:outline-none"
          placeholder="••••••••••••"
          type={show ? 'text' : 'password'}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          autoComplete={autocomplete}
        />
        <button type="button" onClick={onToggle} className="px-4 text-on-surface-variant hover:text-primary-container transition-colors">
          <span className="material-symbols-outlined text-[18px]">{show ? 'visibility' : 'visibility_off'}</span>
        </button>
      </div>
    </div>
  )
}
