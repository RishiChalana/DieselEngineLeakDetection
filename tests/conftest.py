"""
conftest.py — Shared pytest fixtures for Diesel Engine Air Leak Detection tests.

Fixtures:
  model_stack   — ModelStack instance, loaded once per test session.
  healthy_sample — Synthetic steady-state sensor dict (no leak).
  leaky_sample   — Synthetic sensor dict with charge-air leak injected.

Channel names match the CSV dataset headers exactly:
  rpm, fuel_rate, turbo_speed, boost_pressure, MAP, IAT,
  MAF, EGT, exhaust_pressure, VGT, DPF_delta, ambient_pressure
"""
import sys
from pathlib import Path
from typing import Dict

import pytest

# Ensure project root is importable from the tests/ directory.
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from ml_model.data_gen.engine_simulator_core import EngineSimulator
from ml_model.models.model_stack import ModelStack


@pytest.fixture(scope="session")
def model_stack() -> ModelStack:
    """Return the singleton ModelStack instance, loaded once for the session.

    Returns:
        Loaded ModelStack ready for inference calls.
    """
    return ModelStack()


@pytest.fixture(scope="session")
def healthy_sample() -> Dict[str, float]:
    """Return one synthetic healthy engine sensor reading.

    Uses EngineSimulator in healthy mode, warmed up over 50 steps so that
    the Kalman state inside the simulator is past the transient phase.

    Returns:
        Dict of 12 sensor channels matching the CSV column names.
    """
    engine = EngineSimulator(seed=0)
    for _ in range(50):
        engine.step()
    return engine.step()


@pytest.fixture(scope="session")
def leaky_sample() -> Dict[str, float]:
    """Return one synthetic leaky engine sensor reading (charge-air leak).

    Warms up the simulator, injects a charge-air leak, then runs 200 more
    steps to allow leak severity to escalate before taking the sample.

    Returns:
        Dict of 12 sensor channels with anomalous readings from charge-air leak.
    """
    engine = EngineSimulator(seed=1)
    for _ in range(50):
        engine.step()
    engine.introduce_leak(leak_type="charge_air")
    for _ in range(200):
        engine.step()
    return engine.step()
