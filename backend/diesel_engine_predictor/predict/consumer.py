import json
import time
import numpy as np
from collections import deque

from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser

from .services.pipeline import process_engine_data
from .services.test_service import get_or_create_engine, save_engine_test
import joblib as jb
import os
from django.conf import settings

CONFIG_PATH = os.path.join(settings.BASE_DIR, "engine_calibration.pkl")
config = jb.load(CONFIG_PATH)

ANOMALY_THRESHOLD = config["cumulative"]["threshold"]
STABILITY_LIMITS = config["stability"]

WINDOW_SIZE = 7
STABILITY_WINDOW = 7
CONFIRMATION_WINDOWS_REQUIRED = 2
TIMEOUT_SECONDS = 30


class EngineConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        user = self.scope["user"]
        if isinstance(user, AnonymousUser):
            await self.close()
            return

        await self.accept()

        self.user = user
        self.engine = None
        self.start_time = time.time()
        self.stability_buffer = deque(maxlen=STABILITY_WINDOW)
        self.current_window = []
        self.confirmed_windows = 0
        self.window_count = 0

        print("WebSocket connected")

    async def disconnect(self, close_code):
        print("WebSocket disconnected")

    async def receive(self, text_data):
        data = json.loads(text_data)

        # --- First message: register the engine ---
        if self.engine is None:
            model_no = data.get("model_no")
            engine_type = data.get("engine_type", "diesel")
            if not model_no:
                await self.send(text_data=json.dumps({
                    "type": "error",
                    "message": "model_no is required as the first message",
                }))
                await self.close()
                return

            self.engine = await database_sync_to_async(get_or_create_engine)(
                model_no, engine_type
            )
            await self.send(text_data=json.dumps({
                "type": "engine_registered",
                "model_no": model_no,
                "engine_type": engine_type,
            }))
            return

        # --- Timeout guard ---
        if time.time() - self.start_time > TIMEOUT_SECONDS:
            await self.finish_test(leak_detected=False)
            return

        # --- Stability buffering ---
        self.stability_buffer.append(data)
        if len(self.stability_buffer) < STABILITY_WINDOW:
            await self.send(text_data=json.dumps({
                "type": "buffering",
                "buffered": len(self.stability_buffer),
                "required": STABILITY_WINDOW,
            }))
            return

        if not self.is_engine_stable():
            await self.send(text_data=json.dumps({
                "type": "unstable",
                "message": "Engine not yet stable — waiting for steady state",
            }))
            return

        # --- ML inference ---
        result = process_engine_data(data)
        z_cumulative = result["z_cumulative"]
        is_leak_sample = z_cumulative > ANOMALY_THRESHOLD
        confidence = round(min(z_cumulative / (ANOMALY_THRESHOLD * 2), 1.0), 4)

        self.current_window.append({
            "rpm": data["rpm"],
            "fuel_rate": data["fuel_rate"],
            "boost_pressure": data["boost_pressure"],
            "z_cumulative": z_cumulative,
        })

        # Send per-sample inference result to client
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

        # --- Window evaluation ---
        if len(self.current_window) == WINDOW_SIZE:
            anomaly_count = sum(
                s["z_cumulative"] > ANOMALY_THRESHOLD for s in self.current_window
            )
            window_leak = anomaly_count >= 4

            if window_leak:
                self.confirmed_windows += 1
            else:
                self.confirmed_windows = 0

            await self.send(text_data=json.dumps({
                "type": "window_result",
                "window_index": self.window_count,
                "window_leak": window_leak,
                "anomaly_count": anomaly_count,
                "confirmed_windows": self.confirmed_windows,
                "leaky_samples_last_window": [
                    s for s in self.current_window
                    if s["z_cumulative"] > ANOMALY_THRESHOLD
                ],
            }))

            self.window_count += 1

            if self.confirmed_windows >= CONFIRMATION_WINDOWS_REQUIRED:
                await self.finish_test(leak_detected=True)
                return

            # Reset window only when NOT triggering a finish
            self.current_window = []

    async def finish_test(self, leak_detected: bool):
        await database_sync_to_async(save_engine_test)(
            engine=self.engine,
            user=self.user,
            window_samples=self.current_window,
            leak_detected=leak_detected,
        )

        await self.send(text_data=json.dumps({
            "type": "test_complete",
            "leak_detected": leak_detected,
            "windows_evaluated": self.window_count,
            "confirmed_anomaly_windows": self.confirmed_windows,
        }))

        await self.close()

    def is_engine_stable(self):
        rpm_values   = [x["rpm"]            for x in self.stability_buffer]
        fuel_values  = [x["fuel_rate"]      for x in self.stability_buffer]
        boost_values = [x["boost_pressure"] for x in self.stability_buffer]

        return (
            np.std(rpm_values)   < STABILITY_LIMITS["rpm_limit"]  and
            np.std(fuel_values)  < STABILITY_LIMITS["fuel_limit"] and
            np.std(boost_values) < STABILITY_LIMITS["boost_limit"]
        )
