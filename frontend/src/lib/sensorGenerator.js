// Box-Muller Gaussian — avoids log(0)
function randn(mean = 0, std = 1) {
  let u, v
  do { u = Math.random() } while (u === 0)
  do { v = Math.random() } while (v === 0)
  return mean + std * Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v)
}

// Mirrors zone_classifier.py _boost_below_expected() expected-boost formula:
//   expected = 0.000016 * turbo + 0.003 * fuel + 0.25 * (fuel / 120)
function approxBoost(turbo, fuel) {
  return 0.000016 * turbo + 0.003 * fuel + 0.25 * (fuel / 120)
}

// Baselines from Python simulator healthy steady-state (fuel_rate≈88, turbo≈63k).
// These match the ML model training distribution and produce healthy PASS responses.
// Previous baselines used _VALID_PAYLOAD values (turbo=90k) which are outside
// the training distribution (z_cumulative≈505 for healthy) and broke zone isolation.
export const BASELINES = {
  rpm:              1650,
  fuel_rate:        88,
  turbo_speed:      63000,
  boost_pressure:   1.46,
  MAP:              2.47,
  IAT:              307,
  MAF:              946,
  EGT:              797,
  exhaust_pressure: 4.47,
  VGT:              42,
  DPF_delta:        47865,
  ambient_pressure: 1.005,
}

// σ values kept below absolute stability limits (rpm≤30.5, fuel≤3.37, boost≤0.036)
// so the SteadyStateDetector always classifies the simulated signal as stable.
const NOISE = {
  rpm:              15,
  fuel_rate:        2,
  turbo_speed:      500,
  boost_pressure:   0.008,
  MAP:              0.015,
  IAT:              1,
  MAF:              7,
  EGT:              6,
  exhaust_pressure: 0.025,
  VGT:              0.4,
  DPF_delta:        400,
  ambient_pressure: 0.001,
}

// Pre-computed expected boost at healthy baseline — used to scale boost proportionally
// when turbo changes (mirrors engine_simulator_core.py physics.calculate_boostpressure).
const BASE_BOOST_EXPECTED = approxBoost(BASELINES.turbo_speed, BASELINES.fuel_rate)

export function generateSample(leakMode = 'healthy', leakType = 'charge_air') {
  const s = {}
  for (const [key, base] of Object.entries(BASELINES)) {
    s[key] = randn(base, NOISE[key])
  }

  if (leakMode === 'leak') {
    const sev = 0.40

    if (leakType === 'charge_air') {
      // Charge-air leak: turbo spins faster (less load), boost drops explicitly
      // (leak downstream of compressor vents compressed air to atmosphere).
      // Matches engine_simulator_core.py: turbo*(1+0.3s), boost*(1-s), cascade MAP/MAF.
      s.turbo_speed      *= (1 + 0.3 * sev)
      s.boost_pressure   *= (1 - sev)
      s.MAP              *= (1 - 0.5 * sev)
      s.MAF              *= (1 - 0.2 * sev)
      s.exhaust_pressure *= (1 - 0.1 * sev)
      s.DPF_delta        *= (1 - 0.1 * sev)

    } else if (leakType === 'exhaust') {
      // Exhaust leak: back-pressure drops → turbine drive reduced → turbo slows →
      // boost/MAP/MAF/DPF recalculate down.  exhaust_pressure drops as primary event.
      // Matches engine_simulator_core.py: exhaust*(1-s), turbo*(1-0.6s), cascade rest.
      s.exhaust_pressure *= (1 - sev)
      s.turbo_speed      *= (1 - 0.6 * sev)
      const newBoostExp   = approxBoost(s.turbo_speed, s.fuel_rate)
      const boostScale    = newBoostExp / BASE_BOOST_EXPECTED
      s.boost_pressure    = BASELINES.boost_pressure * boostScale
      s.MAP               = BASELINES.MAP            * boostScale
      s.MAF               = BASELINES.MAF            * boostScale
      s.DPF_delta         = BASELINES.DPF_delta      * boostScale
      s.EGT              *= (1 + 0.15 * sev)

    } else if (leakType === 'precompressor') {
      // Pre-compressor leak: intake air mass drops, turbo runs free (less compressor
      // load) → spins faster → boost recalculates UP.  exhaust/DPF follow MAF down.
      // Matches engine_simulator_core.py: MAF*(1-s), turbo*(1+0.2s), boost recalculated.
      s.MAF              *= (1 - sev)
      s.turbo_speed      *= (1 + 0.2 * sev)
      const newBoostExp   = approxBoost(s.turbo_speed, s.fuel_rate)
      const boostScale    = newBoostExp / BASE_BOOST_EXPECTED
      s.boost_pressure    = BASELINES.boost_pressure * boostScale
      s.MAP               = BASELINES.MAP            * boostScale
      const mafRatio      = s.MAF / BASELINES.MAF
      s.exhaust_pressure  = BASELINES.exhaust_pressure * mafRatio
      s.DPF_delta         = BASELINES.DPF_delta        * mafRatio
    }
  }
  return s
}
