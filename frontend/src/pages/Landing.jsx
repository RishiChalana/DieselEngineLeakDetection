import { useEffect } from 'react'
import { Link } from 'react-router-dom'

export default function Landing() {
  // Nav scroll opacity (from cat_product_landing_page)
  useEffect(() => {
    const nav = document.getElementById('topnav')
    const onScroll = () => {
      if (!nav) return
      if (window.scrollY > 50) {
        nav.style.backgroundColor = '#0A0A0A'
      } else {
        nav.style.backgroundColor = 'rgba(10,10,10,0.8)'
      }
    }
    window.addEventListener('scroll', onScroll)
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  // Hover effect on industrial-border cards
  useEffect(() => {
    const cards = document.querySelectorAll('.hover-card')
    cards.forEach((c) => {
      c.addEventListener('mouseenter', () => {
        c.style.transform   = 'translateY(-4px)'
        c.style.borderColor = '#FFD100'
      })
      c.addEventListener('mouseleave', () => {
        c.style.transform   = 'translateY(0)'
        c.style.borderColor = '#2A2A2A'
      })
    })
  }, [])

  return (
    <div style={{ backgroundColor: '#0A0A0A', color: '#ebe2cf', fontFamily: 'Inter, sans-serif', WebkitFontSmoothing: 'antialiased' }}>

      {/* ── Navigation ──────────────────────────────────────────────────── */}
      <nav
        id="topnav"
        style={{ backgroundColor: 'rgba(10,10,10,0.8)', backdropFilter: 'blur(12px)', transition: 'background-color 0.3s' }}
        className="fixed top-0 w-full z-50 border-b border-outline-variant flex justify-between items-center px-margin-desktop py-4"
      >
        <img src="/logo-full.png" alt="LeakGuard Industrial" className="h-10" />
        <div className="hidden md:flex items-center space-x-8">
          <a className="font-label-caps text-label-caps text-primary-container font-bold border-b-2 border-primary-container pb-1 uppercase" href="#platform">Platform</a>
          <a className="font-label-caps text-label-caps text-on-surface-variant hover:text-on-surface transition-colors uppercase" href="#features">Features</a>
          <a className="font-label-caps text-label-caps text-on-surface-variant hover:text-on-surface transition-colors uppercase" href="#specs">Specs</a>
          <Link className="font-label-caps text-label-caps text-on-surface-variant hover:text-on-surface transition-colors uppercase" to="/dashboard">Dashboard</Link>
        </div>
        <Link
          to="/login"
          style={{ backgroundColor: '#ffd100', color: '#3c2f00', border: 'none' }}
          className="px-6 py-3 font-label-caps text-label-caps font-bold uppercase hover:opacity-90 active:scale-95 transition-all"
        >
          Login
        </Link>
      </nav>

      {/* ── Hero ─────────────────────────────────────────────────────────── */}
      <section className="relative min-h-screen flex items-center pt-20">
        <div className="absolute inset-0 z-0 overflow-hidden">
          <img
            alt="Industrial diesel engine test cell"
            className="w-full h-full object-cover grayscale opacity-60"
            src="https://lh3.googleusercontent.com/aida-public/AB6AXuCcgEAhNpagC-awLCghs9V3SS62bSTHan4frxTTYpk5dOKQn3TTaKe6SquhMDHqnuf-2398-8EI0cHQ6gqAZZNusTmLbgUSSja1AQU3dakEeuEaf91MdVY6ybfH0USNSo1GC2R4ijBvkp2oNVxYc5m-Vu_ryHe1uEju88VeAhr9P7_j38VEhz4Cwi3D68JSc7oLzsNOBJg3wrLoQT6NwYezgU_Fsnq1G8uHcXZA-5AGEnrvykf6dyL3CWaspBqEVpZDPYLlxQ0kqdo"
          />
          <div className="absolute inset-0 hero-gradient" />
        </div>
        <div className="relative z-10 px-margin-desktop max-w-5xl">
          <div className="inline-block px-4 py-1 border border-primary-container/30 bg-primary-container/5 mb-6">
            <span className="font-label-caps text-label-caps text-primary-container tracking-[0.2em] uppercase">
              Caterpillar Hackathon · Real-time ML Detection
            </span>
          </div>
          <h1 className="font-display-lg md:text-[72px] leading-tight font-black text-on-background mb-6 tracking-tighter uppercase" style={{ fontSize: '48px' }}>
            Engine Leak<br />Detection &amp;<br /><span style={{ color: '#ffd100' }}>Isolation.</span>
          </h1>
          <p className="font-body-std text-[24px] text-on-surface-variant max-w-2xl mb-10 leading-relaxed">
            Real-time air and exhaust leak detection for CAT diesel engine test cells — using only your existing 12 sensor channels. No additional hardware required.
          </p>
          <div className="flex flex-col sm:flex-row gap-panel-gap">
            <Link
              to="/login"
              style={{ backgroundColor: '#ffd100', color: '#3c2f00' }}
              className="px-10 py-5 font-headline-md text-[20px] uppercase font-black hover:opacity-90 transition-colors text-center"
            >
              Get Started
            </Link>
            <Link
              to="/dashboard"
              className="border border-primary-container text-primary-container px-10 py-5 font-headline-md text-[20px] uppercase font-black hover:bg-primary-container/10 transition-colors text-center"
            >
              View Dashboard
            </Link>
          </div>
        </div>
      </section>

      {/* ── Feature cards ────────────────────────────────────────────────── */}
      <section id="features" style={{ backgroundColor: '#110e05' }} className="py-24 px-margin-desktop border-y border-outline-variant">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
          {[
            { icon: 'hub',      title: '4-Zone Isolation',   desc: 'Localises leaks to one of four subsystem zones — pre-compressor intake, charge-air circuit, exhaust path, or test cell ducting.', arrow: 'Zone Details' },
            { icon: 'memory',   title: 'Physics + ML Hybrid',desc: 'Fuses 4 autoencoder z-scores, One-Class SVM, and Mahalanobis distance with turbo/boost physics discriminators. F1=1.000 on held-out data.', arrow: 'ML Architecture' },
            { icon: 'summarize',title: 'Go / No-Go Reports', desc: 'Upload a CSV of a completed dynamometer run and receive a structured pass/fail session report with zone-level leak analysis and technician guidance.', arrow: 'API Reference' },
            { icon: 'lock',     title: 'On-Premise Only',    desc: 'Fully self-hosted Django + ASGI stack. All inference happens locally — sensor data never leaves the test cell network. Docker-ready deployment.', arrow: 'Deployment Guide' },
          ].map((card) => (
            <div
              key={card.title}
              className="hover-card industrial-border p-10 group"
              style={{ backgroundColor: '#0A0A0A', transition: 'transform 0.2s, border-color 0.2s', cursor: 'default' }}
            >
              <div className="mb-8" style={{ color: '#ffd100' }}>
                <span className="material-symbols-outlined" style={{ fontSize: '48px', fontVariationSettings: "'FILL' 1" }}>{card.icon}</span>
              </div>
              <h3 className="font-headline-md text-[20px] uppercase mb-4 tracking-tight">{card.title}</h3>
              <p className="font-body-std text-on-surface-variant leading-relaxed" style={{ fontSize: '15px' }}>{card.desc}</p>
              <div className="mt-8 flex items-center gap-2 text-primary-container font-label-caps text-label-caps uppercase tracking-widest opacity-0 group-hover:opacity-100 transition-opacity">
                {card.arrow} <span className="material-symbols-outlined" style={{ fontSize: '14px' }}>arrow_forward</span>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ── Product showcase ──────────────────────────────────────────────── */}
      <section id="platform" className="py-24 px-margin-desktop overflow-hidden">
        <div className="flex flex-col lg:flex-row items-center gap-16">
          <div className="lg:w-1/2 relative">
            <div className="absolute -top-10 -left-10 w-40 h-40 border-t-2 border-l-2 border-primary-container opacity-20" />
            <div className="industrial-border p-1 heavy-shadow" style={{ backgroundColor: '#2e2a1e' }}>
              <img
                alt="LeakGuard Dashboard Interface"
                className="w-full grayscale brightness-90 hover:grayscale-0 transition-all duration-700"
                src="https://lh3.googleusercontent.com/aida-public/AB6AXuARYqYVSIkTjwjRbTM8AjYnw8QvWihpkbUulSA7xNKLE8enEZI204zZmQEmomWOqCpToQKlRV99Sc7xg0ZJAke8ropAFirV4yW18fcdbDCxwFhBkKIhV6jJIqQXnr0lMwH4KUNPuc_U-i07eUn0ieITAnd1LB3LKjmkg0fJydUF6gWvV9CRGh7BQDejtCcAG_gyMPmDXPxiNL_PbAscujqF14RAX0PwtHYGXSiVjPNX5t2vq8fCx5t-U8DaKOWbWyfpsBeJloAzNCQ"
              />
            </div>
            <div className="absolute -bottom-10 -right-10 w-40 h-40 border-b-2 border-r-2 border-primary-container opacity-20" />
          </div>
          <div className="lg:w-1/2">
            <h2 className="font-label-caps text-label-caps text-primary-container uppercase tracking-[0.3em] mb-4">Real-Time Command</h2>
            <h3 className="font-display-lg text-[40px] uppercase font-black mb-8 leading-tight">
              Actionable Diagnostics for Zero-Downtime Test Cells.
            </h3>
            <div className="space-y-6">
              {[
                { title: 'Kalman-Filtered Sensor Pipeline', active: true,  desc: 'All 12 channels pass through a per-channel Kalman filter before ML inference, suppressing transient noise and stabilising z-score output.' },
                { title: 'Cadence-Gated Escalation',        active: false, desc: 'Adaptive alert cadence — PASS reports every 10 windows, WARNING every 3, FAIL on every window. Critical alert fires after 5 consecutive anomalous windows.' },
                { title: 'Steady-State Gate',               active: false, desc: 'CV-based transient detector automatically holds inference until the engine stabilises, eliminating false positives during ramp-up and load changes.' },
              ].map((f) => (
                <div
                  key={f.title}
                  className="flex gap-4 items-start pl-6 py-2"
                  style={{ borderLeft: f.active ? '2px solid #ffd100' : '2px solid #4d4632' }}
                >
                  <div>
                    <h4 className={`font-headline-md text-[20px] uppercase tracking-tight ${f.active ? '' : 'text-on-surface-variant'}`}>{f.title}</h4>
                    <p className="text-on-surface-variant font-body-std mt-2" style={{ fontSize: '15px' }}>{f.desc}</p>
                  </div>
                </div>
              ))}
            </div>
            <Link
              to="/login"
              style={{ backgroundColor: '#ffd100', color: '#3c2f00' }}
              className="mt-12 inline-block px-8 py-4 font-label-caps text-label-caps font-bold uppercase hover:opacity-90"
            >
              Open Monitoring Dashboard
            </Link>
          </div>
        </div>
      </section>

      {/* ── Technical grid ────────────────────────────────────────────────── */}
      <section id="specs" style={{ backgroundColor: '#231f14' }} className="py-24 px-margin-desktop border-t border-outline-variant">
        <div className="mb-16 text-center">
          <h2 className="font-display-lg text-[40px] uppercase font-black tracking-tighter">Detection Pipeline</h2>
          <div style={{ width: '96px', height: '4px', backgroundColor: '#ffd100', margin: '16px auto 0' }} />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-panel-gap">
          {[
            { num: '01', title: 'Steady-State Gate',       desc: 'CV check on RPM, fuel rate, MAF, and boost pressure over a 7-sample stability window before inference begins.' },
            { num: '02', title: 'Kalman Smoothing',         desc: 'Per-channel Kalman filter applied to all 12 sensor signals, tuned from steady-state data to suppress measurement noise without introducing lag.' },
            { num: '03', title: '4-Subsystem Autoencoders', desc: 'Independent autoencoders for boost, DPF, MAF, and exhaust subsystems. Each produces a per-subsystem reconstruction error z-score.' },
            { num: '04', title: 'SVM + Mahalanobis',        desc: 'One-Class SVM and Mahalanobis distance provide multivariate outlier z-scores across all 12 channels for cross-system anomaly capture.' },
            { num: '05', title: 'Weighted Z-Score Fusion',  desc: 'z_cumulative = √(z_boost² + z_dpf² + z_maf² + z_exhaust² + 0.3·z_mahal² + z_svm²). Threshold: 6.3156 (calibrated mean+3σ).' },
            { num: '06', title: 'Window Voting + Zone',     desc: '4/7 anomalous samples → leaky window. 2 consecutive leaky windows → LEAK CONFIRMED. Zone classifier isolates to zone_1–4 via physics discriminators.' },
          ].map((cell) => (
            <div key={cell.num} className="industrial-border p-8 flex flex-col justify-between" style={{ backgroundColor: '#0A0A0A' }}>
              <div>
                <span className="font-metric-lg text-[28px] text-primary-container opacity-30">{cell.num}</span>
                <h4 className="font-label-caps text-label-caps uppercase mt-4 text-on-surface mb-2">{cell.title}</h4>
                <p className="text-on-surface-variant font-body-fixed" style={{ fontSize: '13px' }}>{cell.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ── Final CTA ─────────────────────────────────────────────────────── */}
      <section className="relative py-32 px-margin-desktop text-center overflow-hidden">
        <div className="absolute inset-0 z-0">
          <div className="absolute inset-0" style={{ backgroundColor: 'rgba(255,209,0,0.05)', mixBlendMode: 'overlay' }} />
          <div
            className="absolute inset-0"
            style={{ opacity: 0.03, backgroundImage: 'radial-gradient(#FFD100 0.5px, transparent 0.5px)', backgroundSize: '24px 24px' }}
          />
        </div>
        <div className="relative z-10 max-w-4xl mx-auto">
          <h2 className="font-display-lg text-[40px] uppercase font-black mb-8 leading-none">
            Start Your First<br />Test Session.
          </h2>
          <p className="font-body-std text-[24px] text-on-surface-variant mb-12">
            Log in to the monitoring dashboard and connect your sensor stream via WebSocket.
            Full leak detection begins after the first 7 stable samples.
          </p>
          <div className="flex flex-col sm:flex-row gap-panel-gap justify-center">
            <Link
              to="/login"
              style={{ backgroundColor: '#ffd100', color: '#3c2f00' }}
              className="font-headline-md text-[20px] uppercase font-black py-5 px-16 hover:bg-white transition-colors"
            >
              Get Started
            </Link>
            <Link
              to="/dashboard"
              className="border border-primary-container text-primary-container font-headline-md text-[20px] uppercase font-black py-5 px-16 hover:bg-primary-container/10 transition-colors"
            >
              Live Dashboard
            </Link>
          </div>
          <div className="mt-8 flex justify-center gap-12 font-label-caps text-label-caps text-on-surface-variant">
            <span className="flex items-center gap-2">
              <span className="material-symbols-outlined text-primary-container">verified</span> BINARY F1=1.000 · ZONE MACRO F1=0.884
            </span>
            <span className="flex items-center gap-2">
              <span className="material-symbols-outlined text-primary-container">lock</span> ON-PREMISE ONLY
            </span>
          </div>
        </div>
      </section>

      {/* ── Footer ───────────────────────────────────────────────────────── */}
      <footer style={{ backgroundColor: '#110e05' }} className="border-t border-outline-variant w-full py-12">
        <div className="flex flex-col md:flex-row justify-between items-center px-margin-desktop space-y-4 md:space-y-0">
          <div className="font-headline-md text-[20px] text-primary-container uppercase font-black tracking-tighter">LeakGuard</div>
          <div className="flex gap-8">
            <Link className="font-label-caps text-label-caps text-on-surface-variant hover:text-primary transition-colors uppercase" to="/login">Login</Link>
            <Link className="font-label-caps text-label-caps text-on-surface-variant hover:text-primary transition-colors uppercase" to="/dashboard">Dashboard</Link>
            <a className="font-label-caps text-label-caps text-on-surface-variant hover:text-primary transition-colors uppercase" href="#">API Docs</a>
            <a className="font-label-caps text-label-caps text-on-surface-variant hover:text-primary transition-colors uppercase" href="#">Architecture</a>
          </div>
          <div className="font-label-caps text-label-caps text-on-surface-variant uppercase text-right opacity-50">
            © {new Date().getFullYear()} Caterpillar Hackathon. All Rights Reserved.
          </div>
        </div>
      </footer>
    </div>
  )
}
