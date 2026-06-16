"""
predict/consumer.py — Django Channels WebSocket consumer for real-time inference.

Protocol (both directions documented in docs/API_REFERENCE.md):
  Client → Server: first message must register the engine (model_no / engine_type).
                   Subsequent messages are sensor dicts (12 channels).
  Server → Client: engine_registered | buffering | unstable | sample_result
                   | window_result | test_complete | error
"""
import json
import logging
import sys
import time
from collections import deque
from pathlib import Path
from typing import Any, Dict

import joblib as jb
import numpy as np
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings
from django.contrib.auth.models import AnonymousUser

# Ensure project root is on sys.path before importing ml_model packages.
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from config.constants import (
    ANOMALY_THRESHOLD,
    CONFIRMATION_WINDOWS_REQUIRED,
    CONSECUTIVE_FAIL_ALERT_THRESHOLD,
    INFERENCE_WINDOW_SIZE,
    SEND_INTERVAL_FAIL,
    SEND_INTERVAL_PASS,
    SEND_INTERVAL_WARNING,
    STABILITY_WINDOW_SIZE,
    WS_SESSION_TIMEOUT_SECONDS,
    WINDOW_ANOMALY_VOTE_THRESHOLD,
    CALIBRATION_FILENAME,
    Z_SCORE_EPSILON,
)
from ml_model.zone_classifier import ZoneClassifier
from ml_model.steady_state import SteadyStateDetector
from .services.pipeline import process_engine_data
from .services.test_service import get_or_create_engine, save_engine_test, update_user_history

_zone_classifier = ZoneClassifier()
_steady_detector = SteadyStateDetector()

logger = logging.getLogger(__name__)

# Load stability limits from calibration bundle once at module load.
_CONFIG_PATH = Path(settings.BASE_DIR) / CALIBRATION_FILENAME
_calibration = jb.load(_CONFIG_PATH)
_STABILITY_LIMITS: Dict[str, float] = _calibration["stability"]


class EngineConsumer(AsyncWebsocketConsumer):
    """Async WebSocket consumer that streams sensor samples through the ML pipeline.

    State machine:
        INIT  → waiting for engine-registration message (model_no).
        READY → buffering samples until stability gate passes.
        RUNNING → running inference per sample, tracking window votes.
        DONE → test saved, connection closed.
    """

    async def connect(self) -> None:
        """Accept authenticated connections; reject anonymous users."""
        user = self.scope["user"]
        if isinstance(user, AnonymousUser):
            logger.warning("Rejected unauthenticated WebSocket connection")
            await self.close()
            return

        await self.accept()

        self.user = user
        self.engine: Any = None
        self.start_time: float = time.time()
        self.stability_buffer: deque = deque(maxlen=STABILITY_WINDOW_SIZE)
        self.current_window: list = []
        self.confirmed_windows: int = 0
        self.window_count: int = 0
        self.consecutive_fail_count: int = 0

        logger.info("WebSocket connected — user=%s", user.username)

    async def disconnect(self, close_code: int) -> None:
        """Log disconnection."""
        logger.info("WebSocket disconnected — code=%s", close_code)

    async def receive(self, text_data: str) -> None:
        """Dispatch incoming message to the appropriate handler.

        Args:
            text_data: JSON-encoded string from the client.
        """
        data: Dict[str, Any] = json.loads(text_data)

        # --- Phase 1: engine registration ---
        if self.engine is None:
            await self._handle_registration(data)
            return

        # --- Session timeout guard ---
        if time.time() - self.start_time > WS_SESSION_TIMEOUT_SECONDS:
            logger.info("Session timeout — closing with no leak confirmed")
            await self.finish_test(leak_detected=False)
            return

        await self._handle_sensor_sample(data)

    # ------------------------------------------------------------------
    # Private handlers
    # ------------------------------------------------------------------

    async def _handle_registration(self, data: Dict[str, Any]) -> None:
        """Register the engine under test from the first client message.

        Args:
            data: Must contain ``model_no``; optionally ``engine_type``.
        """
        model_no: str | None = data.get("model_no")
        engine_type: str = data.get("engine_type", "diesel")

        if not model_no:
            await self.send(text_data=json.dumps({
                "type": "error",
                "message": "model_no is required as the first message.",
            }))
            await self.close()
            return

        self.engine = await database_sync_to_async(get_or_create_engine)(
            model_no, engine_type
        )
        logger.info("Engine registered — model_no=%s  type=%s", model_no, engine_type)

        await self.send(text_data=json.dumps({
            "type": "engine_registered",
            "model_no": model_no,
            "engine_type": engine_type,
        }))

    async def _handle_sensor_sample(self, data: Dict[str, Any]) -> None:
        """Buffer, gate, infer, and window-vote on one sensor sample.

        Args:
            data: Dict with 12 sensor channel values.
        """
        # Stability buffering
        self.stability_buffer.append(data)
        if len(self.stability_buffer) < STABILITY_WINDOW_SIZE:
            await self.send(text_data=json.dumps({
                "type": "buffering",
                "buffered": len(self.stability_buffer),
                "required": STABILITY_WINDOW_SIZE,
            }))
            return

        if not self._is_engine_stable():
            await self.send(text_data=json.dumps({
                "type": "unstable",
                "message": "Engine not yet at steady state — waiting.",
            }))
            return

        # ML inference
        result = process_engine_data(data)
        z_cumulative: float = result["z_cumulative"]
        self._last_z_cumulative: float = z_cumulative
        is_leak_sample: bool = z_cumulative >= ANOMALY_THRESHOLD
        confidence: float = round(
            min(z_cumulative / max(ANOMALY_THRESHOLD * 2, Z_SCORE_EPSILON), 1.0),
            4,
        )

        self.current_window.append({
            "rpm": data["rpm"],
            "fuel_rate": data["fuel_rate"],
            "boost_pressure": data["boost_pressure"],
            "z_cumulative": z_cumulative,
            # Store subsystem z-scores for zone classification at window boundary.
            "_subsystem_z": {
                "boost":   result["z_autoencoder_boost"],
                "dpf":     result["z_autoencoder_dpf"],
                "maf":     result["z_autoencoder_maf"],
                "exhaust": result["z_autoencoder_exhaust"],
            },
        })
        self._last_raw_sample: Dict[str, Any] = data

        await self.send(text_data=json.dumps({
            "type": "sample_result",
            "status": "leak" if is_leak_sample else "normal",
            "confidence": confidence,
            "z_scores": {
                "boost":       round(result["z_autoencoder_boost"], 4),
                "dpf":         round(result["z_autoencoder_dpf"], 4),
                "maf":         round(result["z_autoencoder_maf"], 4),
                "exhaust":     round(result["z_autoencoder_exhaust"], 4),
                "mahalanobis": round(result["z_mahalanobis"], 4),
                "svm":         round(result["z_svm"], 4),
                "cumulative":  round(z_cumulative, 4),
            },
            "window_index": self.window_count,
        }))

        # Window evaluation
        if len(self.current_window) == INFERENCE_WINDOW_SIZE:
            await self._evaluate_window()

    async def _evaluate_window(self) -> None:
        """Vote on the completed window, classify zone, and check for leak confirmation."""
        anomaly_count: int = sum(
            s["z_cumulative"] >= ANOMALY_THRESHOLD
            for s in self.current_window
        )
        window_leak: bool = anomaly_count >= WINDOW_ANOMALY_VOTE_THRESHOLD

        if window_leak:
            self.confirmed_windows += 1
        else:
            self.confirmed_windows = 0

        # Zone isolation: average subsystem z-scores across the anomalous samples.
        isolation_payload: Dict[str, Any] = {}
        is_steady = _steady_detector.check(
            [s for s in self.current_window]
        )["is_steady"]

        if window_leak:
            anomalous = [s for s in self.current_window if s["z_cumulative"] >= ANOMALY_THRESHOLD]
            avg_subsystem_z = {
                sub: float(np.mean([s["_subsystem_z"][sub] for s in anomalous]))
                for sub in ("boost", "dpf", "maf", "exhaust")
            }
            raw_ref = getattr(self, "_last_raw_sample", {})
            iso = _zone_classifier.analyze(avg_subsystem_z, {}, raw_ref)
            isolation_payload = {
                "zone":             iso["detected_zone"],
                "zone_label":       iso["zone_label"],
                "top_evidence":     iso["supporting_evidence"][:2],
                "zone_scores":      iso["zone_scores"],
            }

        # Confidence from average z of anomalous window samples
        avg_z = float(np.mean([s["z_cumulative"] for s in self.current_window]))
        window_confidence = round(
            min(avg_z / max(ANOMALY_THRESHOLD * 2, Z_SCORE_EPSILON), 1.0), 4
        )
        flag = "FAIL" if (window_leak and window_confidence >= 0.6) else (
            "WARNING" if window_leak else "PASS"
        )
        severity = "severe" if window_confidence >= 0.75 and window_leak else (
            "moderate" if window_leak else "none"
        )

        # Track consecutive FAIL windows for escalation cadence.
        if flag == "FAIL":
            self.consecutive_fail_count += 1
        else:
            self.consecutive_fail_count = 0

        logger.debug(
            "Window %d evaluated — anomalous=%d/%d  confirmed_windows=%d  flag=%s  "
            "consecutive_fail=%d",
            self.window_count,
            anomaly_count,
            INFERENCE_WINDOW_SIZE,
            self.confirmed_windows,
            flag,
            self.consecutive_fail_count,
        )

        # Cadence gating: suppress window_result messages at PASS/WARNING rates.
        send_interval = (
            SEND_INTERVAL_FAIL    if flag == "FAIL"    else
            SEND_INTERVAL_WARNING if flag == "WARNING" else
            SEND_INTERVAL_PASS
        )
        should_send = (self.window_count % send_interval) == 0

        if should_send:
            leaky_samples = [
                {k: v for k, v in s.items() if not k.startswith("_")}
                for s in self.current_window
                if s["z_cumulative"] >= ANOMALY_THRESHOLD
            ]
            await self.send(text_data=json.dumps({
                "type": "window_result",
                "window_index": self.window_count,
                "window_leak": window_leak,
                "anomaly_count": anomaly_count,
                "confirmed_windows": self.confirmed_windows,
                "leaky_samples_last_window": leaky_samples,
                "flag":           flag,
                "severity":       severity,
                "is_steady_state": is_steady,
                "escalate":       flag == "FAIL",
                **isolation_payload,
            }))

        if self.consecutive_fail_count >= CONSECUTIVE_FAIL_ALERT_THRESHOLD:
            logger.warning(
                "Critical alert: %d consecutive FAIL windows — user=%s engine=%s",
                self.consecutive_fail_count,
                self.user.username,
                getattr(self.engine, "model_no", "unknown"),
            )
            await self.send(text_data=json.dumps({
                "type": "critical_alert",
                "consecutive_fail_windows": self.consecutive_fail_count,
                "window_index": self.window_count,
                "severity": severity,
                "zone": isolation_payload.get("zone", "unknown"),
                "message": (
                    f"CRITICAL: {self.consecutive_fail_count} consecutive anomalous windows. "
                    "Halt test and inspect immediately."
                ),
            }))

        self.window_count += 1

        if self.confirmed_windows >= CONFIRMATION_WINDOWS_REQUIRED:
            await self.finish_test(leak_detected=True)
            return

        self.current_window = []

    # ------------------------------------------------------------------
    # Test completion
    # ------------------------------------------------------------------

    async def finish_test(self, leak_detected: bool) -> None:
        """Persist the test result, update user history, and close the connection.

        Args:
            leak_detected: True if the leak confirmation threshold was met.
        """
        final_confidence: float = round(
            min(
                self._last_z_cumulative / max(ANOMALY_THRESHOLD * 2, Z_SCORE_EPSILON),
                1.0,
            ),
            4,
        ) if hasattr(self, "_last_z_cumulative") else 0.0

        await database_sync_to_async(save_engine_test)(
            engine=self.engine,
            user=self.user,
            window_samples=self.current_window,
            leak_detected=leak_detected,
        )
        await database_sync_to_async(update_user_history)(
            user=self.user,
            engine_model_no=self.engine.model_no,
            leak_detected=leak_detected,
            confidence=final_confidence,
        )
        logger.info(
            "Test complete — leak_detected=%s  windows=%d  user=%s",
            leak_detected,
            self.window_count,
            self.user.username,
        )

        await self.send(text_data=json.dumps({
            "type": "test_complete",
            "leak_detected": leak_detected,
            "windows_evaluated": self.window_count,
            "confirmed_anomaly_windows": self.confirmed_windows,
        }))

        await self.close()

    # ------------------------------------------------------------------
    # Stability gate
    # ------------------------------------------------------------------

    def _is_engine_stable(self) -> bool:
        """Return True if RPM, fuel-rate, and boost-pressure are steady.

        Compares the std-dev of each signal over the stability buffer against
        the limits loaded from engine_calibration.pkl.
        """
        rpm_values    = [x["rpm"]            for x in self.stability_buffer]
        fuel_values   = [x["fuel_rate"]      for x in self.stability_buffer]
        boost_values  = [x["boost_pressure"] for x in self.stability_buffer]

        return (
            float(np.std(rpm_values))   < _STABILITY_LIMITS["rpm_limit"]   and
            float(np.std(fuel_values))  < _STABILITY_LIMITS["fuel_limit"]  and
            float(np.std(boost_values)) < _STABILITY_LIMITS["boost_limit"]
        )
