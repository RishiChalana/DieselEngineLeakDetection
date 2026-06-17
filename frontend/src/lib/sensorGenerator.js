// Box-Muller Gaussian — avoids log(0)
function randn(mean = 0, std = 1) {
  let u, v
  do { u = Math.random() } while (u === 0)
  do { v = Math.random() } while (v === 0)
  return mean + std * Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v)
}

// Baselines from test_api.py _VALID_PAYLOAD — produce healthy PASS responses
export const BASELINES = {
  rpm:              1600,
  fuel_rate:        75,
  turbo_speed:      90000,
  boost_pressure:   1.4,
  MAP:              2.3,
  IAT:              305,
  MAF:              520,
  EGT:              680,
  exhaust_pressure: 2.6,
  VGT:              48,
  DPF_delta:        22000,
  ambient_pressure: 1.01,
}

// σ values kept well below stability gate limits
// rpm_limit=30.5, fuel_limit=3.37, boost_limit=0.036
const NOISE = {
  rpm:              15,
  fuel_rate:        2,
  turbo_speed:      800,
  boost_pressure:   0.008,
  MAP:              0.015,
  IAT:              1,
  MAF:              4,
  EGT:              5,
  exhaust_pressure: 0.015,
  VGT:              0.4,
  DPF_delta:        200,
  ambient_pressure: 0.001,
}

export function generateSample(leakMode = 'healthy', leakType = 'charge_air') {
  const s = {}
  for (const [key, base] of Object.entries(BASELINES)) {
    s[key] = randn(base, NOISE[key])
  }

  if (leakMode === 'leak') {
    const sev = 0.40
    if (leakType === 'charge_air') {
      // Leak multipliers match engine_simulator_core.py _apply_leak()
      s.boost_pressure *= (1 - sev)
      s.MAP            *= (1 - 0.5 * sev)
      s.turbo_speed    *= (1 + 0.3 * sev)
      s.MAF            *= (1 - 0.2 * sev)
    } else if (leakType === 'exhaust') {
      s.exhaust_pressure *= (1 + sev * 0.3)
      s.EGT              *= (1 + sev * 0.15)
      s.DPF_delta        *= (1 + sev * 0.4)
    } else if (leakType === 'precompressor') {
      s.MAF             *= (1 - sev * 0.4)
      s.turbo_speed     *= (1 + sev * 0.2)
      s.boost_pressure  *= (1 - sev * 0.1)
    }
  }
  return s
}
