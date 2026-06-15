"""
ModelStack: singleton wrapper around all trained ML artifacts.
Used by engine_simulator/app.py (Streamlit dashboard).
evaluate(filtered_data) takes already Kalman-filtered sensor dict.
predict(sensor_data) applies internal Kalman first.
"""
import sys
from pathlib import Path

import joblib as jb
import numpy as np
from tensorflow.keras.models import load_model

# Ensure project root is on sys.path so sibling ml_model imports resolve
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from ml_model.kalman.kalman_layer import KalmanLayer
from ml_model.models.mahalanobis.distance import MahalanobisDistance

_MODELS_DIR = Path(__file__).resolve().parent
_AE_PATH = _MODELS_DIR / "autoencoders" / "residual_score" / "encoded_model"
_SVM_PATH = _MODELS_DIR / "svm" / "encoded" / "svm_model.joblib"

_SENSOR_COLS = [
    "rpm", "fuel_rate", "turbo_speed", "boost_pressure",
    "MAP", "IAT", "MAF", "EGT",
    "exhaust_pressure", "VGT", "DPF_delta", "ambient_pressure",
]

_AE_FEATURES = {
    "boost":   ["rpm", "fuel_rate", "turbo_speed", "exhaust_pressure", "boost_pressure"],
    "dpf":     ["fuel_rate", "rpm", "MAF", "boost_pressure", "turbo_speed", "exhaust_pressure", "DPF_delta"],
    "maf":     ["rpm", "fuel_rate", "MAP", "IAT", "MAF"],
    "exhaust": ["rpm", "fuel_rate", "MAF", "turbo_speed", "DPF_delta", "exhaust_pressure"],
}

ANOMALY_THRESHOLD = 3.5


def _autoencoder_z(model, scaler, threshold, values):
    X = scaler.transform(np.array(values).reshape(1, -1))
    recon = model.predict(X, verbose=0)
    score = float(np.mean((recon - X) ** 2))
    return max(float(np.log1p(score / max(threshold, 1e-10))), 0.0)


class ModelStack:
    """Singleton — models are loaded once and reused across all calls."""

    _singleton = None

    def __new__(cls):
        if cls._singleton is None:
            instance = super().__new__(cls)
            instance._loaded = False
            cls._singleton = instance
        return cls._singleton

    def __init__(self):
        if self._loaded:
            return
        self._load()
        self._loaded = True

    # ------------------------------------------------------------------
    # Model loading
    # ------------------------------------------------------------------

    def _load(self):
        self._ae = {}
        self._scaler_ae = {}
        self._threshold_ae = {}

        for name in ("boost", "dpf", "maf", "exhaust"):
            self._ae[name] = load_model(_AE_PATH / f"nn_model_{name}.keras")
            bundle = jb.load(_AE_PATH / f"nn_model_preprocessing_{name}.pkl")
            self._scaler_ae[name] = bundle["scaler"]
            self._threshold_ae[name] = bundle["threshold"]

        self._svm_bundle = jb.load(_SVM_PATH)
        self._mahal = MahalanobisDistance()
        self._kalman = KalmanLayer()

        print("[ModelStack] All models loaded.")

    # ------------------------------------------------------------------
    # Inference helpers
    # ------------------------------------------------------------------

    def _z_svm(self, fd: dict) -> float:
        cols = self._svm_bundle["columns"]
        scaler = self._svm_bundle["scaler"]
        svm = self._svm_bundle["svm_model"]
        mean = self._svm_bundle["healthy_mean"]
        std = max(self._svm_bundle["healthy_std"], 1e-10)

        X = np.array([fd[c] for c in cols]).reshape(1, -1)
        raw = -svm.decision_function(scaler.transform(X))[0]
        return max(float((raw - mean) / std), 0.0)

    def _z_mahal(self, fd: dict) -> float:
        x = np.array([fd[c] for c in _SENSOR_COLS])
        return max(float(self._mahal.calculate_z_score(x)), 0.0)

    def _infer_leak_type(self, z_boost, z_maf, z_exhaust, z_dpf) -> str:
        scores = {
            "charge_air": z_boost,
            "precompressor": z_maf,
            "exhaust": z_exhaust,
        }
        return max(scores, key=scores.get)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate(self, filtered_data: dict) -> dict:
        """Run full inference on already Kalman-filtered sensor data."""
        fd = filtered_data

        z_boost = _autoencoder_z(
            self._ae["boost"], self._scaler_ae["boost"], self._threshold_ae["boost"],
            [fd[c] for c in _AE_FEATURES["boost"]],
        )
        z_dpf = _autoencoder_z(
            self._ae["dpf"], self._scaler_ae["dpf"], self._threshold_ae["dpf"],
            [fd[c] for c in _AE_FEATURES["dpf"]],
        )
        z_maf = _autoencoder_z(
            self._ae["maf"], self._scaler_ae["maf"], self._threshold_ae["maf"],
            [fd[c] for c in _AE_FEATURES["maf"]],
        )
        z_exhaust = _autoencoder_z(
            self._ae["exhaust"], self._scaler_ae["exhaust"], self._threshold_ae["exhaust"],
            [fd[c] for c in _AE_FEATURES["exhaust"]],
        )

        z_mahal = self._z_mahal(fd)
        z_svm = self._z_svm(fd)

        z_cumulative = float(np.sqrt(
            z_boost**2 + z_dpf**2 + z_maf**2 + z_exhaust**2
            + 0.3 * z_mahal**2 + z_svm**2
        ))

        physics_score = max(z_boost, z_maf, z_exhaust, z_dpf)
        ae_z = float(np.mean([z_boost, z_dpf, z_maf, z_exhaust]))
        is_leak = z_cumulative > ANOMALY_THRESHOLD
        confidence = round(min(z_cumulative / (ANOMALY_THRESHOLD * 2), 1.0), 4)
        leak_type = self._infer_leak_type(z_boost, z_maf, z_exhaust, z_dpf) if is_leak else None

        return {
            # app.py expected keys
            "final_score": z_cumulative,
            "physics_score": physics_score,
            "svm_z": z_svm,
            "ae_z": ae_z,
            "boost_z": z_boost,
            "maf_z": z_maf,
            "exhaust_z": z_exhaust,
            "dpf_z": z_dpf,
            # consumer / API extended keys
            "z_cumulative": z_cumulative,
            "z_mahalanobis": z_mahal,
            "is_leak": is_leak,
            "confidence": confidence,
            "z_scores": [z_boost, z_dpf, z_maf, z_exhaust, z_mahal, z_svm],
            "leak_type": leak_type,
        }

    def predict(self, sensor_data: dict) -> dict:
        """Run full pipeline: internal Kalman filter → evaluate."""
        filtered = self._kalman.filter(sensor_data)
        return self.evaluate(filtered)
