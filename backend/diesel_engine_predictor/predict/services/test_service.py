"""
test_service.py — ORM helpers for persisting engine test results and user history.

All functions are synchronous Django ORM calls; wrap them with
``database_sync_to_async`` before awaiting inside the WebSocket consumer.
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import numpy as np

from user_auth.models import Engine, Engine_Test, Sensor_Leaky_Data

logger = logging.getLogger(__name__)

_MAX_HISTORY_ENTRIES: int = 50


def get_or_create_engine(model_no: str, engine_type: Optional[str] = None) -> Engine:
    """Fetch or create an Engine record by model_no.

    Args:
        model_no: Unique engine model identifier (e.g. "CAT-3412-001").
        engine_type: Engine fuel type; defaults to "diesel".

    Returns:
        The Engine ORM instance.
    """
    engine, created = Engine.objects.get_or_create(
        model_no=model_no,
        defaults={"type": engine_type or "diesel"},
    )
    if created:
        logger.info("Created new engine record — model_no=%s", model_no)
    return engine


def generate_next_steps(leak_detected: bool, window_samples: list):

    if not window_samples:
        return "No sufficient data collected."

    if not leak_detected:
        return "Engine operating normally. No leak detected."

    # Extract values
    boost_vals = [s.get("boost_pressure", 0) for s in window_samples]
    rpm_vals = [s.get("rpm", 0) for s in window_samples]
    fuel_vals = [s.get("fuel_rate", 0) for s in window_samples]
    z_vals = [s.get("z_cumulative", 0) for s in window_samples]

    avg_boost = np.mean(boost_vals)
    avg_rpm = np.mean(rpm_vals)
    avg_fuel = np.mean(fuel_vals)
    avg_z = np.mean(z_vals)

    # Rule-based decision tree

    if avg_boost > 1.6:
        return "Possible turbocharger leak. Inspect turbo hoses and intercooler connections."

    if avg_boost < 1.0:
        return "Boost pressure too low. Check for air intake leakage or damaged turbo."

    if avg_z > 8:
        return "Severe anomaly detected. Immediate inspection of exhaust and fuel system recommended."

    if avg_fuel > 110:
        return "Abnormal fuel consumption detected. Inspect injectors and fuel pump."

    if np.std(rpm_vals) > 100:
        return "RPM instability detected. Possible combustion or sensor irregularity."

    return "Leak pattern detected. Inspect exhaust manifold, turbo system and DPF assembly."

def save_engine_test(engine: Engine, user: Any, window_samples: List[Dict], leak_detected: bool) -> Engine_Test:
    """Persist a completed test run and return the Engine_Test record.

    Args:
        engine: Engine ORM instance under test.
        user: User ORM instance who ran the test.
        window_samples: List of per-sample dicts captured during the test.
        leak_detected: True when LEAK_CONFIRMED verdict was reached.

    Returns:
        The newly created Engine_Test ORM instance.
    """
    sensor_obj = Sensor_Leaky_Data.objects.create(
        rolling_window_data={"samples": window_samples},
        next_steps=generate_next_steps(leak_detected, window_samples),
    )
    test = Engine_Test.objects.create(
        engine=engine,
        user=user,
        sensor=sensor_obj,
        test_check="Fail" if leak_detected else "Pass",
    )
    logger.info(
        "Saved Engine_Test id=%s — engine=%s  result=%s",
        test.id,
        engine.model_no,
        test.test_check,
    )
    return test


def update_user_history(
    user: Any,
    engine_model_no: str,
    leak_detected: bool,
    confidence: float,
) -> None:
    """Append a summary entry to user.history (bounded to 50 entries).

    Args:
        user: User ORM instance whose history to update.
        engine_model_no: The engine model_no string for this test.
        leak_detected: Final verdict of the test.
        confidence: Confidence score (0–1) at test completion.
    """
    from user_auth.models import User as UserModel

    entry: Dict[str, Any] = {
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "engine_model_no": engine_model_no,
        "leak_detected": leak_detected,
        "confidence": round(confidence, 4),
    }

    # history is a JSONField(default=dict); normalise to list on first write.
    existing: Any = user.history
    if not isinstance(existing, list):
        existing = []

    existing.append(entry)
    if len(existing) > _MAX_HISTORY_ENTRIES:
        existing = existing[-_MAX_HISTORY_ENTRIES:]

    UserModel.objects.filter(pk=user.pk).update(history=existing)
    logger.debug("Updated history for user=%s (entries=%d)", user.username, len(existing))