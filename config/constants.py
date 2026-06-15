"""
constants.py — All project-wide constants for Diesel Engine Air Leak Detection.

Edit this file to tune thresholds or adapt to a new engine configuration.
Every value here corresponds to a source in the codebase; see the inline comments
for which file originally defined each magic number.

Two threshold systems exist (see ANOMALY_THRESHOLD_* notes below):
  - CONSUMER_ANOMALY_THRESHOLD: used by the WebSocket consumer for per-sample
    window-voting. Calibrated from the leaky-data z-score distribution (mean + 3σ).
  - MODEL_STACK_ANOMALY_THRESHOLD: used by ModelStack.evaluate() for immediate
    per-sample flag. More sensitive, tuned for the Streamlit live display.
"""

from typing import Dict, List

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
    "maf":   ["rpm", "fuel_rate", "MAP", "IAT", "MAF"],
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

#: Calibrated cumulative z-score threshold used by the WebSocket consumer.
#: Source: engine_calibration.pkl["cumulative"]["threshold"]
#: Derived as mean + 3σ of leaky-data cumulative z-scores (≈ 5.86 + 3×0.152).
CONSUMER_ANOMALY_THRESHOLD: float = 6.315587152674103

#: Cumulative z-score threshold used by ModelStack.evaluate() for the
#: per-sample is_leak flag and the Streamlit dashboard display.
#: More sensitive than CONSUMER_ANOMALY_THRESHOLD; not calibration-derived.
MODEL_STACK_ANOMALY_THRESHOLD: float = 3.5

#: Score threshold used in the Streamlit app for live display status.
STREAMLIT_DISPLAY_THRESHOLD: float = 3.0

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
# Steady-state detection  (Phase 1 prep — not yet wired)
# ---------------------------------------------------------------------------

#: Maximum coefficient of variation for RPM to consider engine steady-state.
STEADY_STATE_RPM_CV_MAX: float = 0.01

#: Maximum coefficient of variation for MAF to consider engine steady-state.
STEADY_STATE_MAF_CV_MAX: float = 0.015

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
