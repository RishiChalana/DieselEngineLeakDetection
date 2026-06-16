"""
model_stack.py — Singleton wrapper around all trained ML model artifacts.

Used by engine_simulator/app.py (Streamlit dashboard) and by the REST
/api/predict view as an alternative entry point.

Three public methods:
  evaluate(filtered_data)  — takes already Kalman-filtered sensor dict;
                              returns the flat 14-key detection dict.
  predict(sensor_data)     — applies Kalman, evaluates, then builds the full
                              five-section structured verdict including
                              steady-state gate, detection, isolation, decision,
                              and metadata.
  health_check()           — returns component loading status.

Loading happens once on first instantiation (singleton pattern via __new__).
"""
import datetime
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import joblib as jb
import numpy as np
from tensorflow.keras.models import load_model

# Ensure project root is on sys.path so config and ml_model sub-packages resolve.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from config.constants import (
    AE_FEATURES,
    ANOMALY_THRESHOLD,
    AUTOENCODER_MODEL_FILES,
    AUTOENCODER_PREPROCESSING_FILES,
    AUTOENCODER_SUBPATH,
    MAHAL_SUBPATH,
    RECOMMENDED_ACTIONS,
    SENSOR_COLS,
    SEVERITY_MINOR_MAX,
    SEVERITY_MODERATE_MAX,
    SVM_SUBPATH,
    Z_SCORE_EPSILON,
)
from ml_model.kalman.kalman_layer import KalmanLayer
from ml_model.models.mahalanobis.distance import MahalanobisDistance
from ml_model.steady_state import SteadyStateDetector
from ml_model.zone_classifier import ZoneClassifier

logger = logging.getLogger(__name__)

_MODELS_DIR = Path(__file__).resolve().parent
_AE_PATH = _MODELS_DIR / AUTOENCODER_SUBPATH
_SVM_PATH = _MODELS_DIR / SVM_SUBPATH
_MAHAL_PATH = _MODELS_DIR / MAHAL_SUBPATH


def _autoencoder_z(
    model: Any,
    scaler: Any,
    threshold: float,
    values: List[float],
) -> float:
    """Compute a non-negative z-score from autoencoder reconstruction error.

    Args:
        model: Loaded Keras autoencoder model.
        scaler: Fitted StandardScaler for the model's feature subset.
        threshold: 99th-percentile reconstruction error on healthy training data.
        values: Raw feature values in the order the model was trained on.

    Returns:
        Non-negative float; 0.0 for healthy, higher for more anomalous.
    """
    X = scaler.transform(np.array(values).reshape(1, -1))
    recon = model.predict(X, verbose=0)
    score = float(np.mean((recon - X) ** 2))
    return max(float(np.log1p(score / max(threshold, Z_SCORE_EPSILON))), 0.0)


class ModelStack:
    """Singleton inference stack: Kalman → 4 AEs → SVM → Mahalanobis → fusion.

    Attributes:
        _singleton: Class-level reference to the single instance.
        _loaded: Guards against re-loading on repeated ``__init__`` calls.
    """

    _singleton: Optional["ModelStack"] = None

    def __new__(cls) -> "ModelStack":
        """Return the existing instance or create and store a new one."""
        if cls._singleton is None:
            instance = super().__new__(cls)
            instance._loaded = False
            cls._singleton = instance
        return cls._singleton

    def __init__(self) -> None:
        """Load all model artifacts (runs once; subsequent calls are no-ops)."""
        if self._loaded:
            return
        self._load_models()
        self._loaded = True

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def _load_models(self) -> None:
        """Load all .keras, .joblib, and .pkl artifacts from disk."""
        logger.info("ModelStack: loading all model artifacts…")

        self._ae: Dict[str, Any] = {}
        self._scaler_ae: Dict[str, Any] = {}
        self._threshold_ae: Dict[str, float] = {}

        for name in ("boost", "dpf", "maf", "exhaust"):
            self._ae[name] = load_model(_AE_PATH / AUTOENCODER_MODEL_FILES[name])
            bundle = jb.load(_AE_PATH / AUTOENCODER_PREPROCESSING_FILES[name])
            self._scaler_ae[name] = bundle["scaler"]
            self._threshold_ae[name] = float(bundle["threshold"])

        self._svm_bundle: Dict[str, Any] = jb.load(_SVM_PATH)
        self._mahal = MahalanobisDistance()
        self._kalman = KalmanLayer()

        logger.info("ModelStack: all artifacts loaded successfully.")

    # ------------------------------------------------------------------
    # Inference helpers
    # ------------------------------------------------------------------

    def _z_svm(self, fd: Dict[str, float]) -> float:
        """Compute SVM z-score from calibrated decision function.

        Args:
            fd: Kalman-filtered sensor dict.

        Returns:
            Non-negative z-score; 0.0 for healthy.
        """
        cols: List[str] = self._svm_bundle["columns"]
        scaler = self._svm_bundle["scaler"]
        svm = self._svm_bundle["svm_model"]
        mean: float = self._svm_bundle["healthy_mean"]
        std: float = max(float(self._svm_bundle["healthy_std"]), Z_SCORE_EPSILON)

        X = np.array([fd[c] for c in cols]).reshape(1, -1)
        raw: float = -svm.decision_function(scaler.transform(X))[0]
        return max(float((raw - mean) / std), 0.0)

    def _z_mahal(self, fd: Dict[str, float]) -> float:
        """Compute Mahalanobis z-score.

        Args:
            fd: Kalman-filtered sensor dict.

        Returns:
            Non-negative float; 0.0 for in-distribution.
        """
        x = np.array([fd[c] for c in SENSOR_COLS])
        return max(float(self._mahal.calculate_z_score(x)), 0.0)

    def _infer_leak_type(
        self,
        z_boost: float,
        z_maf: float,
        z_exhaust: float,
        z_dpf: float,
    ) -> str:
        """Map the dominant autoencoder score to a leak-type label.

        Args:
            z_boost: Boost-subsystem autoencoder z-score.
            z_maf: MAF-subsystem autoencoder z-score.
            z_exhaust: Exhaust-subsystem autoencoder z-score.
            z_dpf: DPF-subsystem autoencoder z-score.

        Returns:
            One of ``"charge_air"``, ``"precompressor"``, ``"exhaust"``.
        """
        scores = {
            "charge_air":    z_boost,
            "precompressor": z_maf,
            "exhaust":       z_exhaust,
        }
        return max(scores, key=scores.get)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate(self, filtered_data: Dict[str, float]) -> Dict[str, Any]:
        """Run full inference on already Kalman-filtered sensor data.

        Args:
            filtered_data: Sensor dict after Kalman smoothing (12 channels).

        Returns:
            Dict with keys: ``final_score``, ``physics_score``, ``svm_z``,
            ``ae_z``, ``boost_z``, ``maf_z``, ``exhaust_z``, ``dpf_z``,
            ``z_cumulative``, ``z_mahalanobis``, ``is_leak``, ``confidence``,
            ``z_scores``, ``leak_type``.
        """
        fd = filtered_data

        z_boost   = _autoencoder_z(self._ae["boost"],   self._scaler_ae["boost"],
                                   self._threshold_ae["boost"],
                                   [fd[c] for c in AE_FEATURES["boost"]])
        z_dpf     = _autoencoder_z(self._ae["dpf"],     self._scaler_ae["dpf"],
                                   self._threshold_ae["dpf"],
                                   [fd[c] for c in AE_FEATURES["dpf"]])
        z_maf     = _autoencoder_z(self._ae["maf"],     self._scaler_ae["maf"],
                                   self._threshold_ae["maf"],
                                   [fd[c] for c in AE_FEATURES["maf"]])
        z_exhaust = _autoencoder_z(self._ae["exhaust"], self._scaler_ae["exhaust"],
                                   self._threshold_ae["exhaust"],
                                   [fd[c] for c in AE_FEATURES["exhaust"]])

        z_mahal   = self._z_mahal(fd)
        z_svm     = self._z_svm(fd)

        from config.constants import MAHAL_FUSION_WEIGHT
        z_cumulative = float(np.sqrt(
            z_boost**2   + z_dpf**2 + z_maf**2 + z_exhaust**2
            + MAHAL_FUSION_WEIGHT * z_mahal**2
            + z_svm**2
        ))

        physics_score: float = max(z_boost, z_maf, z_exhaust, z_dpf)
        ae_z: float          = float(np.mean([z_boost, z_dpf, z_maf, z_exhaust]))
        is_leak: bool        = z_cumulative >= ANOMALY_THRESHOLD
        confidence: float    = round(
            min(z_cumulative / max(ANOMALY_THRESHOLD * 2, Z_SCORE_EPSILON), 1.0),
            4,
        )
        leak_type: Optional[str] = (
            self._infer_leak_type(z_boost, z_maf, z_exhaust, z_dpf) if is_leak else None
        )

        return {
            # Keys expected by engine_simulator/app.py
            "final_score":   z_cumulative,
            "physics_score": physics_score,
            "svm_z":         z_svm,
            "ae_z":          ae_z,
            "boost_z":       z_boost,
            "maf_z":         z_maf,
            "exhaust_z":     z_exhaust,
            "dpf_z":         z_dpf,
            # Extended keys for REST / WebSocket consumers
            "z_cumulative":   z_cumulative,
            "z_mahalanobis":  z_mahal,
            "is_leak":        is_leak,
            "confidence":     confidence,
            "z_scores":       [z_boost, z_dpf, z_maf, z_exhaust, z_mahal, z_svm],
            "leak_type":      leak_type,
        }

    def predict(self, sensor_data: Dict[str, float]) -> Dict[str, Any]:
        """Run full pipeline: Kalman → detection → steady-state → isolation → verdict.

        Args:
            sensor_data: Raw 12-channel sensor dict (pre-Kalman).

        Returns:
            Structured dict with five top-level keys: ``steady_state``,
            ``detection``, ``isolation``, ``decision``, ``metadata``.
            ``isolation`` is populated only when ``detection.is_leak`` is True.
        """
        t_start = time.perf_counter()
        filtered = self._kalman.filter(sensor_data)
        detection = self.evaluate(filtered)
        steady = self._steady_detector.check([sensor_data])
        isolation: Dict[str, Any] = {}

        if detection["is_leak"]:
            subsystem_z = {
                "boost":   detection["boost_z"],
                "dpf":     detection["dpf_z"],
                "maf":     detection["maf_z"],
                "exhaust": detection["exhaust_z"],
            }
            isolation = self._zone_classifier.analyze(subsystem_z, {}, filtered)

        decision = self._build_decision(detection, steady, isolation)

        duration_ms = round((time.perf_counter() - t_start) * 1000, 2)
        return {
            "steady_state": {
                "is_steady":         steady["is_steady"],
                "confidence":        steady["confidence"],
                "reason":            steady["reason"],
                "unstable_channels": steady["unstable_channels"],
            },
            "detection": {
                "is_leak":     detection["is_leak"],
                "confidence":  detection["confidence"],
                "z_cumulative": detection["z_cumulative"],
                "subsystem_z": {
                    "boost":   detection["boost_z"],
                    "dpf":     detection["dpf_z"],
                    "maf":     detection["maf_z"],
                    "exhaust": detection["exhaust_z"],
                },
                "svm_z":        detection["svm_z"],
                "mahal_z":      detection["z_mahalanobis"],
                "leak_type":    detection["leak_type"],
                "physics_score": detection["physics_score"],
            },
            "isolation": isolation,
            "decision":  decision,
            "metadata": {
                "analysis_timestamp":  datetime.datetime.now(tz=datetime.timezone.utc).isoformat(),
                "model_version":       "phase3",
                "analysis_duration_ms": duration_ms,
            },
        }

    # ------------------------------------------------------------------
    # Lazy-loaded helpers (avoid import-time overhead for callers that
    # use only evaluate())
    # ------------------------------------------------------------------

    @property
    def _steady_detector(self) -> SteadyStateDetector:
        if not hasattr(self, "__steady_detector"):
            object.__setattr__(self, "__steady_detector", SteadyStateDetector())
        return object.__getattribute__(self, "__steady_detector")

    @property
    def _zone_classifier(self) -> ZoneClassifier:
        if not hasattr(self, "__zone_classifier"):
            object.__setattr__(self, "__zone_classifier", ZoneClassifier())
        return object.__getattribute__(self, "__zone_classifier")

    @staticmethod
    def _build_decision(
        detection: Dict[str, Any],
        steady: Dict[str, Any],
        isolation: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Build the flag/severity/action decision block.

        Args:
            detection: Output of evaluate().
            steady: Output of SteadyStateDetector.check().
            isolation: Output of ZoneClassifier.analyze() or empty dict.

        Returns:
            Dict with keys ``flag``, ``severity``, ``recommended_action``,
            ``escalate_immediately``.
        """
        is_leak: bool = detection["is_leak"]
        confidence: float = detection["confidence"]
        is_steady: bool = steady["is_steady"]
        zone: str = isolation.get("detected_zone", "unknown") if isolation else "unknown"

        if not is_leak:
            flag = "PASS"
        elif not is_steady or confidence < 0.6:
            flag = "WARNING"
        else:
            flag = "FAIL"

        if not is_leak:
            severity = "none"
        elif confidence < SEVERITY_MINOR_MAX:
            severity = "minor"
        elif confidence < SEVERITY_MODERATE_MAX or zone in ("unknown", "multiple"):
            severity = "moderate"
        else:
            severity = "severe"

        action = RECOMMENDED_ACTIONS.get(zone, RECOMMENDED_ACTIONS["unknown"])
        return {
            "flag":                flag,
            "severity":            severity,
            "recommended_action":  action,
            "escalate_immediately": flag == "FAIL",
        }

    def health_check(self) -> Dict[str, Any]:
        """Return a dict confirming all sub-models are loaded.

        Returns:
            Dict with keys ``all_loaded`` (bool) and ``components`` (list).
        """
        components = ["ae_boost", "ae_dpf", "ae_maf", "ae_exhaust",
                      "svm", "mahalanobis", "kalman"]
        all_loaded = (
            self._loaded
            and all(k in self._ae for k in ("boost", "dpf", "maf", "exhaust"))
            and self._svm_bundle is not None
            and self._mahal is not None
            and self._kalman is not None
        )
        return {"all_loaded": all_loaded, "components": components}
