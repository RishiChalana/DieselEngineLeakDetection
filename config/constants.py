"""
constants.py — All project-wide constants for Diesel Engine Air Leak Detection.

Edit this file to tune thresholds or adapt to a new engine configuration.
Every value here corresponds to a source in the codebase; see the inline comments
for which file originally defined each magic number.

Phase 3: ANOMALY_THRESHOLD is the single source of truth for all is_leak decisions.
It is loaded at import time from engine_calibration.pkl (mean+3σ of leaky z-scores).
DISPLAY_COLOR_SCALE_MAX is a separate visual-only constant (not a decision threshold).
"""

import logging
from pathlib import Path
from typing import Dict, List

import joblib as _jb

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Calibration bundle — loaded once at import to supply ANOMALY_THRESHOLD
# ---------------------------------------------------------------------------

_CALIBRATION_PKL = (
    Path(__file__).resolve().parents[1]
    / "backend"
    / "diesel_engine_predictor"
    / "engine_calibration.pkl"
)

try:
    _calibration_bundle = _jb.load(_CALIBRATION_PKL)
    #: Single source of truth for all is_leak decisions (REST + WebSocket + ModelStack).
    #: Value: mean+3σ of leaky cumulative z-scores from engine_calibration.pkl.
    ANOMALY_THRESHOLD: float = float(_calibration_bundle["cumulative"]["threshold"])
    _logger.debug("Loaded ANOMALY_THRESHOLD=%.6f from calibration pkl", ANOMALY_THRESHOLD)
except Exception as _e:  # pragma: no cover
    _logger.warning("Could not load engine_calibration.pkl (%s); using fallback 6.3156", _e)
    ANOMALY_THRESHOLD: float = 6.315587152674103

# ---------------------------------------------------------------------------
# Sensor channels
# ---------------------------------------------------------------------------

#: All 12 sensor channels in the exact order used across the pipeline.
#: Changing order here requires retraining all models.
SENSOR_COLS: List[str] = [
    "rpm",
    "fuel_rate",
    "turbo_speed",
    "boost_pressure",
    "MAP",
    "IAT",
    "MAF",
    "EGT",
    "exhaust_pressure",
    "VGT",
    "DPF_delta",
    "ambient_pressure",
]

# ---------------------------------------------------------------------------
# Autoencoder feature groups  (must match the .pkl scalers — do not reorder)
# ---------------------------------------------------------------------------

AE_FEATURES: Dict[str, List[str]] = {
    "boost": ["rpm", "fuel_rate", "turbo_speed", "exhaust_pressure", "boost_pressure"],
    "dpf":   ["fuel_rate", "rpm", "MAF", "boost_pressure", "turbo_speed",
               "exhaust_pressure", "DPF_delta"],
    # Bug fix (Phase 3): training used [rpm, fuel_rate, MAP, MAF, turbo_speed];
    # Phase 2 had IAT at position 4 and MAF at 5, mismatching the scaler.
    "maf":   ["rpm", "fuel_rate", "MAP", "MAF", "turbo_speed"],
    "exhaust": ["rpm", "fuel_rate", "MAF", "turbo_speed", "DPF_delta", "exhaust_pressure"],
}

# ---------------------------------------------------------------------------
# WebSocket rolling-window detection  (consumer.py)
# ---------------------------------------------------------------------------

#: Number of inference samples that form one evaluation window.
INFERENCE_WINDOW_SIZE: int = 7

#: Samples buffered to verify engine stability before inference starts.
STABILITY_WINDOW_SIZE: int = 7

#: Consecutive anomalous windows required to confirm a leak.
CONFIRMATION_WINDOWS_REQUIRED: int = 2

#: Seconds before a WebSocket test session times out with no leak confirmed.
WS_SESSION_TIMEOUT_SECONDS: int = 30

#: Minimum anomalous samples within a window to declare that window as leaky.
WINDOW_ANOMALY_VOTE_THRESHOLD: int = 4

# ---------------------------------------------------------------------------
# Stability-gate thresholds  (loaded from engine_calibration.pkl at runtime)
# These are the std-dev limits for RPM, fuel-rate, and boost pressure over
# the last STABILITY_WINDOW_SIZE samples.  Values below come from the pkl.
# ---------------------------------------------------------------------------

#: Maximum std-dev of RPM over stability window.
STABILITY_RPM_LIMIT: float = 30.532084719403016

#: Maximum std-dev of fuel_rate over stability window.
STABILITY_FUEL_LIMIT: float = 3.3650725218042306

#: Maximum std-dev of boost_pressure over stability window.
STABILITY_BOOST_LIMIT: float = 0.03571613589568773

# ---------------------------------------------------------------------------
# Anomaly detection thresholds
# ---------------------------------------------------------------------------

# ANOMALY_THRESHOLD is defined above (loaded from engine_calibration.pkl).

#: Maximum z-score shown at full red on the Streamlit live-trend chart.
#: This is a DISPLAY constant only — it does NOT gate any is_leak decision.
DISPLAY_COLOR_SCALE_MAX: float = 3.0

#: Weight applied to the Mahalanobis z-score inside the weighted L2 fusion.
#: The other five z-scores (4 AE + SVM) carry weight 1.0.
MAHAL_FUSION_WEIGHT: float = 0.3

#: Small epsilon to prevent division by zero in z-score calculations.
Z_SCORE_EPSILON: float = 1e-10

# ---------------------------------------------------------------------------
# WebSocket escalation intervals  (Phase 1 prep — not yet wired)
# ---------------------------------------------------------------------------

#: Send a status message every N evaluation windows when result is PASS.
SEND_INTERVAL_PASS: int = 10

#: Send a status message every N evaluation windows when result is WARNING.
SEND_INTERVAL_WARNING: int = 3

#: Send a status message on every evaluation window when result is FAIL.
SEND_INTERVAL_FAIL: int = 1

#: Number of consecutive FAIL windows before triggering an escalation alert.
CONSECUTIVE_FAIL_ALERT_THRESHOLD: int = 5

# ---------------------------------------------------------------------------
# Steady-state detection  (SteadyStateDetector — ml_model/steady_state.py)
# ---------------------------------------------------------------------------

#: Maximum coefficient of variation for RPM to consider engine steady-state.
STEADY_STATE_RPM_CV_MAX: float = 0.01

#: Maximum coefficient of variation for MAF to consider engine steady-state.
STEADY_STATE_MAF_CV_MAX: float = 0.015

#: Maximum coefficient of variation for fuel_rate to consider engine steady-state.
STEADY_STATE_FUEL_CV_MAX: float = 0.02

#: Maximum coefficient of variation for boost_pressure to consider engine steady-state.
STEADY_STATE_BOOST_CV_MAX: float = 0.03

#: Maximum coefficient of variation for torque/load to consider steady-state.
STEADY_STATE_TORQUE_CV_MAX: float = 0.02

#: Number of samples used to evaluate the steady-state condition.
STEADY_STATE_WINDOW_SIZE: int = 30

# ---------------------------------------------------------------------------
# ML training hyperparameters  (training scripts only)
# ---------------------------------------------------------------------------

#: Number of samples in each generated dataset (healthy or leaky).
DATASET_NUM_SAMPLES: int = 20_000

#: Number of training epochs for all autoencoder models.
AE_EPOCHS: int = 50

#: Mini-batch size for autoencoder training.
AE_BATCH_SIZE: int = 128

#: Fraction of training data reserved for validation.
AE_VALIDATION_SPLIT: float = 0.1

#: Percentile of healthy reconstruction error used as the anomaly threshold.
AE_THRESHOLD_PERCENTILE: int = 99

#: Adam learning rate used for all autoencoder models.
AE_LEARNING_RATE: float = 0.001

#: One-Class SVM contamination assumption (fraction of outliers in training).
SVM_NU: float = 0.05

#: One-Class SVM kernel.
SVM_KERNEL: str = "rbf"

# ---------------------------------------------------------------------------
# Engine simulator parameters  (engine_simulator_core.py)
# ---------------------------------------------------------------------------

#: First-order lag coefficient for turbocharger speed dynamics.
TURBO_LAG_ALPHA: float = 0.15

#: Standard deviation of per-step RPM random walk (rev/min per step).
RPM_STEP_SIGMA: float = 15.0

#: Standard deviation of per-step sensor drift increment.
DRIFT_SIGMA: float = 0.0001

# ---------------------------------------------------------------------------
# Zone isolation labels and recommended actions  (Phase 1 prep)
# ---------------------------------------------------------------------------

#: Human-readable labels for each isolation zone.
ZONE_LABELS: Dict[str, str] = {
    "zone_1":   "Pre-compressor intake (Airflow meter → Compressor inlet)",
    "zone_2":   "Charge-air system (Compressor outlet → CAC → Intake ports)",
    "zone_3":   "Exhaust path (Manifold → Turbine → Aftertreatment)",
    "zone_4":   "Test cell ducting interfaces",
    "multiple": "Multiple zones",
    "unknown":  "Zone undetermined",
}

#: Technician-facing action guidance for each zone.
RECOMMENDED_ACTIONS: Dict[str, str] = {
    "zone_1": (
        "Inspect airflow meter connections and hose clamps between MAF sensor "
        "and turbocharger compressor inlet. Check for cracked intake ducting "
        "or loose fittings."
    ),
    "zone_2": (
        "Pressure-test charge-air circuit. Inspect compressor outlet piping, "
        "boost hose clamps, charge-air cooler end tanks, and intake manifold "
        "gaskets."
    ),
    "zone_3": (
        "Inspect exhaust manifold gaskets and turbocharger outlet flange. "
        "Check aftertreatment inlet connection for soot trails indicating "
        "a hot-side leak."
    ),
    "zone_4": (
        "Check test cell ducting connections and measurement tap seals. "
        "Verify cell-to-engine interface flanges are properly sealed."
    ),
    "multiple": (
        "Multiple zones suspect. Perform systematic pressure-decay test. "
        "Begin with Zone 2 (charge-air) — most common failure location."
    ),
    "unknown": (
        "Leak detected but zone unclear. Perform visual inspection of all "
        "circuit interfaces. Consult steady-state test data records."
    ),
}

# ---------------------------------------------------------------------------
# Zone classifier constants  (ml_model/zone_classifier.py)
# ---------------------------------------------------------------------------

#: Maps each sensor channel to its primary zone(s).
#: Used by ZoneClassifier to weight per-zone evidence.
CHANNEL_ZONE_MAP: Dict[str, List[str]] = {
    "rpm":              ["zone_1", "zone_2", "zone_3", "zone_4"],
    "fuel_rate":        ["zone_2", "zone_3"],
    "turbo_speed":      ["zone_1", "zone_2", "zone_3"],
    "boost_pressure":   ["zone_2"],
    "MAP":              ["zone_2"],
    "IAT":              ["zone_1", "zone_2"],
    "MAF":              ["zone_1"],
    "EGT":              ["zone_3"],
    "exhaust_pressure": ["zone_3"],
    "VGT":              ["zone_3"],
    "DPF_delta":        ["zone_3"],
    "ambient_pressure": ["zone_4"],
}

#: Weighted contributions of subsystem autoencoders to each zone score.
#: zone_score[zone] = sum(weight * z_score for subsystem in zone)
ZONE_AE_WEIGHTS: Dict[str, Dict[str, float]] = {
    "zone_1": {"maf": 1.0,     "boost": 0.1,  "dpf": 0.0,  "exhaust": 0.0},
    "zone_2": {"boost": 1.5,   "maf": 0.2,    "dpf": 0.0,  "exhaust": 0.0},
    "zone_3": {"exhaust": 1.0, "dpf": 0.8,    "maf": 0.0,  "boost": 0.0},
    "zone_4": {"maf": 0.25,    "boost": 0.25, "dpf": 0.25, "exhaust": 0.25},
}

#: charge_air vs exhaust/precompressor discriminator.
#: actual_boost / expected_boost(turbo, fuelrate) below this → charge_air (zone_2).
#: For charge_air: boost *= (1-s) while turbo *= (1+0.3s) → ratio << 1.
#: For exhaust: boost recalculated from reduced turbo → ratio ≈ 1.0.
#: For precompressor: boost recalculated from slightly elevated turbo → ratio ≈ 1.0.
BOOST_BELOW_EXPECTED_FACTOR: float = 0.60

#: precompressor vs exhaust discriminator.
#: actual_turbo / expected_turbo(fuelrate) above this → turbo is elevated → zone_1 pattern.
#: For precompressor: turbo *= (1+0.2s) → ratio > 1.
#: For exhaust: turbo *= (1-0.6s) and is often clipped → ratio < 1.
TURBO_ABOVE_EXPECTED_FACTOR: float = 1.04

#: Minimum normalised zone score to consider a zone active.
ZONE_FLOOR: float = 0.05

#: If the top two zone scores are within this fraction of each other → "multiple".
ZONE_MULTIPLE_DELTA: float = 0.15

# Severity thresholds (confidence-based)
SEVERITY_MINOR_MAX: float = 0.50
SEVERITY_MODERATE_MAX: float = 0.75

# ---------------------------------------------------------------------------
# Model artifact paths  (relative to ml_model/models/)
# ---------------------------------------------------------------------------

AUTOENCODER_SUBPATH: str = "autoencoders/residual_score/encoded_model"

AUTOENCODER_MODEL_FILES: Dict[str, str] = {
    "boost":   "nn_model_boost.keras",
    "dpf":     "nn_model_dpf.keras",
    "maf":     "nn_model_maf.keras",
    "exhaust": "nn_model_exhaust.keras",
}

AUTOENCODER_PREPROCESSING_FILES: Dict[str, str] = {
    "boost":   "nn_model_preprocessing_boost.pkl",
    "dpf":     "nn_model_preprocessing_dpf.pkl",
    "maf":     "nn_model_preprocessing_maf.pkl",
    "exhaust": "nn_model_preprocessing_exhaust.pkl",
}

SVM_SUBPATH: str = "svm/encoded/svm_model.joblib"
MAHAL_SUBPATH: str = "mahalanobis/encoded/mahal_model.pkl"

#: Path to the calibration bundle relative to the Django backend root.
CALIBRATION_FILENAME: str = "engine_calibration.pkl"
