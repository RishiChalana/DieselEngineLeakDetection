export const ANOMALY_THRESHOLD = 6.3156

export const SENSOR_COLS = [
  'rpm', 'fuel_rate', 'turbo_speed', 'boost_pressure',
  'MAP', 'IAT', 'MAF', 'EGT',
  'exhaust_pressure', 'VGT', 'DPF_delta', 'ambient_pressure',
]

export const ZONE_LABELS = {
  zone_1:   'Pre-compressor intake',
  zone_2:   'Charge-air system',
  zone_3:   'Exhaust path',
  zone_4:   'Test cell ducting',
  multiple: 'Multiple zones suspect',
  unknown:  'Zone undetermined',
}

export const ZONE_LABELS_LONG = {
  zone_1:   'Pre-compressor intake (Airflow meter → Compressor inlet)',
  zone_2:   'Charge-air system (Compressor outlet → CAC → Intake ports)',
  zone_3:   'Exhaust path (Manifold → Turbine → Aftertreatment)',
  zone_4:   'Test cell ducting interfaces',
  multiple: 'Multiple zones',
  unknown:  'Zone undetermined',
}

export const RECOMMENDED_ACTIONS = {
  zone_1:   'Inspect airflow meter connections and hose clamps between MAF sensor and turbocharger compressor inlet. Check for cracked intake ducting or loose fittings.',
  zone_2:   'Pressure-test charge-air circuit. Inspect compressor outlet piping, boost hose clamps, charge-air cooler end tanks, and intake manifold gaskets.',
  zone_3:   'Inspect exhaust manifold gaskets and turbocharger outlet flange. Check aftertreatment inlet connection for soot trails indicating a hot-side leak.',
  zone_4:   'Check test cell ducting connections and measurement tap seals. Verify cell-to-engine interface flanges are properly sealed.',
  multiple: 'Multiple zones suspect. Perform systematic pressure-decay test. Begin with Zone 2 (charge-air) — most common failure location.',
  unknown:  'Leak detected but zone unclear. Perform visual inspection of all circuit interfaces. Consult steady-state test data records.',
}
