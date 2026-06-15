"""
pipeline.py — Core ML inference pipeline for the Django backend.

Loads all model artifacts once at module import time (module-level globals).
Single public entry-point: process_engine_data(sensor_data) → dict of z-scores.

Path setup MUST stay before any ml_model imports; manage.py injects the project
root into sys.path at startup, but Daphne loads this module without running
manage.py, so we do the injection here.
"""
import logging
import os
import sys
from typing import Dict

# -------------------------------------------------
# Project-root path injection (must precede ml_model imports)
# -------------------------------------------------

_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(_CURRENT_DIR)))
_PROJECT_ROOT = os.path.dirname(_BACKEND_DIR)

if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import joblib as jb
import numpy as np
from tensorflow.keras.models import load_model

from .kalman_service import apply_kalman
from config.constants import (
    AE_FEATURES,
    AUTOENCODER_MODEL_FILES,
    AUTOENCODER_PREPROCESSING_FILES,
    AUTOENCODER_SUBPATH,
    MAHAL_FUSION_WEIGHT,
    SENSOR_COLS,
    SVM_SUBPATH,
    Z_SCORE_EPSILON,
)
from ml_model.models.mahalanobis.distance import MahalanobisDistance

logger = logging.getLogger(__name__)

_ML_MODEL_PATH = os.path.join(_PROJECT_ROOT, "ml_model")
_AUTOENCODER_PATH = os.path.join(_ML_MODEL_PATH, "models", AUTOENCODER_SUBPATH)
_SVM_PATH = os.path.join(_ML_MODEL_PATH, "models", SVM_SUBPATH)

# -------------------------------------------------
# Module-level globals (populated by load_trained_models)
# -------------------------------------------------

_MAHAL_MODEL = MahalanobisDistance()

_AUTOENCODER_BOOST    = None
_AUTOENCODER_DPF      = None
_AUTOENCODER_MAF      = None
_AUTOENCODER_EXHAUST  = None

_SCALAR_BOOST    = None
_THRESHOLD_BOOST = None
_SCALAR_DPF      = None
_THRESHOLD_DPF   = None
_SCALAR_MAF      = None
_THRESHOLD_MAF   = None
_SCALAR_EXHAUST  = None
_THRESHOLD_EXHAUST = None

_SVM_MODEL = None


# -------------------------------------------------
# Model loading
# -------------------------------------------------

def load_trained_models() -> None:
    """Load all model artifacts into module-level globals.

    Called once at import time. Safe to call again; models will be reloaded.
    """
    global _AUTOENCODER_BOOST, _AUTOENCODER_DPF, _AUTOENCODER_MAF, _AUTOENCODER_EXHAUST
    global _SCALAR_BOOST, _THRESHOLD_BOOST
    global _SCALAR_DPF,   _THRESHOLD_DPF
    global _SCALAR_MAF,   _THRESHOLD_MAF
    global _SCALAR_EXHAUST, _THRESHOLD_EXHAUST
    global _SVM_MODEL

    for name, global_ae, global_scalar, global_thresh in [
        ("boost",   "_AUTOENCODER_BOOST",   "_SCALAR_BOOST",   "_THRESHOLD_BOOST"),
        ("dpf",     "_AUTOENCODER_DPF",     "_SCALAR_DPF",     "_THRESHOLD_DPF"),
        ("maf",     "_AUTOENCODER_MAF",     "_SCALAR_MAF",     "_THRESHOLD_MAF"),
        ("exhaust", "_AUTOENCODER_EXHAUST", "_SCALAR_EXHAUST", "_THRESHOLD_EXHAUST"),
    ]:
        model = load_model(os.path.join(_AUTOENCODER_PATH, AUTOENCODER_MODEL_FILES[name]))
        bundle = jb.load(os.path.join(_AUTOENCODER_PATH, AUTOENCODER_PREPROCESSING_FILES[name]))
        globals()[global_ae]      = model
        globals()[global_scalar]  = bundle["scaler"]
        globals()[global_thresh]  = bundle["threshold"]

    _SVM_MODEL = jb.load(_SVM_PATH)
    logger.info("All trained models loaded successfully.")


load_trained_models()


# -------------------------------------------------
# Inference helpers
# -------------------------------------------------

def _compute_autoencoder_z(
    model,
    scaler,
    threshold: float,
    values: list,
) -> float:
    """Return non-negative z-score from autoencoder reconstruction error.

    Args:
        model: Loaded Keras autoencoder.
        scaler: Fitted StandardScaler for this model's feature subset.
        threshold: 99th-percentile healthy reconstruction error.
        values: Feature values in training-time order.

    Returns:
        Non-negative float; 0.0 means within healthy distribution.
    """
    X_scaled = scaler.transform(np.array(values).reshape(1, -1))
    recon = model.predict(X_scaled, verbose=0)
    score = float(np.mean((recon - X_scaled) ** 2))
    z = np.log1p(score / max(threshold, Z_SCORE_EPSILON))
    return max(float(z), 0.0)


def _apply_svm(filtered_data: Dict[str, float]) -> float:
    """Return non-negative SVM anomaly z-score.

    Args:
        filtered_data: Kalman-filtered 12-channel sensor dict.

    Returns:
        Non-negative float; 0.0 means inside the healthy support.
    """
    cols   = _SVM_MODEL["columns"]
    scaler = _SVM_MODEL["scaler"]
    svm    = _SVM_MODEL["svm_model"]
    mean   = _SVM_MODEL["healthy_mean"]
    std    = max(float(_SVM_MODEL["healthy_std"]), Z_SCORE_EPSILON)

    X = np.array([filtered_data[c] for c in cols]).reshape(1, -1)
    raw = -svm.decision_function(scaler.transform(X))[0]
    return max(float((raw - mean) / std), 0.0)


def _apply_mahalanobis(filtered_data: Dict[str, float]) -> float:
    """Return non-negative Mahalanobis z-score.

    Args:
        filtered_data: Kalman-filtered 12-channel sensor dict.

    Returns:
        Non-negative float; 0.0 means at the healthy distribution mean.
    """
    x = np.array([filtered_data[c] for c in SENSOR_COLS])
    return max(float(_MAHAL_MODEL.calculate_z_score(x)), 0.0)


# -------------------------------------------------
# Public entry point
# -------------------------------------------------

def process_engine_data(sensor_data: Dict[str, float]) -> Dict[str, float]:
    """Run the full inference pipeline on one raw sensor reading.

    Steps: Kalman → 4 autoencoders → Mahalanobis → SVM → weighted L2 fusion.

    Args:
        sensor_data: Raw 12-channel sensor dict.

    Returns:
        Dict with keys: z_autoencoder_boost, z_autoencoder_dpf,
        z_autoencoder_maf, z_autoencoder_exhaust, z_mahalanobis,
        z_svm, z_cumulative.
    """
    filtered_data = apply_kalman(sensor_data)

    z_boost   = _compute_autoencoder_z(_AUTOENCODER_BOOST,   _SCALAR_BOOST,
                                       _THRESHOLD_BOOST,
                                       [filtered_data[c] for c in AE_FEATURES["boost"]])
    z_dpf     = _compute_autoencoder_z(_AUTOENCODER_DPF,     _SCALAR_DPF,
                                       _THRESHOLD_DPF,
                                       [filtered_data[c] for c in AE_FEATURES["dpf"]])
    z_maf     = _compute_autoencoder_z(_AUTOENCODER_MAF,     _SCALAR_MAF,
                                       _THRESHOLD_MAF,
                                       [filtered_data[c] for c in AE_FEATURES["maf"]])
    z_exhaust = _compute_autoencoder_z(_AUTOENCODER_EXHAUST, _SCALAR_EXHAUST,
                                       _THRESHOLD_EXHAUST,
                                       [filtered_data[c] for c in AE_FEATURES["exhaust"]])

    z_mahal = _apply_mahalanobis(filtered_data)
    z_svm   = _apply_svm(filtered_data)

    z_cumulative = float(np.sqrt(
        z_boost**2   + z_dpf**2    + z_maf**2 + z_exhaust**2
        + MAHAL_FUSION_WEIGHT * z_mahal**2
        + z_svm**2
    ))

    return {
        "z_autoencoder_boost":   z_boost,
        "z_autoencoder_dpf":     z_dpf,
        "z_autoencoder_maf":     z_maf,
        "z_autoencoder_exhaust": z_exhaust,
        "z_mahalanobis":         z_mahal,
        "z_svm":                 z_svm,
        "z_cumulative":          z_cumulative,
    }
