"""
conftest.py — Shared pytest fixtures for Diesel Engine Air Leak Detection tests.

All fixtures use EngineSimulator for real sensor distributions.
Fixtures that need the DB are defined per-test to avoid scope conflicts.
"""
import sys
from pathlib import Path
from typing import Dict, List

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_BACKEND_ROOT = _PROJECT_ROOT / "backend" / "diesel_engine_predictor"
for _p in (_PROJECT_ROOT, _BACKEND_ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from config.constants import SENSOR_COLS, STEADY_STATE_WINDOW_SIZE
from ml_model.data_gen.engine_simulator_core import EngineSimulator
from ml_model.models.model_stack import ModelStack


@pytest.fixture(scope="session")
def model_stack() -> ModelStack:
    """Loaded once for the entire test session (singleton)."""
    return ModelStack()


@pytest.fixture(scope="session")
def healthy_sample() -> Dict[str, float]:
    """Single healthy sensor reading after 60-step warmup."""
    sim = EngineSimulator(seed=0)
    for _ in range(60):
        sim.step()
    return sim.step()


@pytest.fixture(scope="session")
def leaky_sample() -> Dict[str, float]:
    """Charge-air leak at severity 0.40 — reliably above ANOMALY_THRESHOLD."""
    sim = EngineSimulator(seed=1)
    for _ in range(60):
        sim.step()
    sim.introduce_leak(leak_type="charge_air")
    sim.leak_severity = 0.40
    for _ in range(50):
        sim.step()
    return sim.step()


@pytest.fixture(scope="session")
def stable_window() -> List[Dict[str, float]]:
    """30 samples at steady operating point — all CV values near zero."""
    sim = EngineSimulator(seed=2)
    for _ in range(100):
        sim.step()
    base = sim.step()
    # Duplicate the same sample: CV = 0 on all channels → definitely steady
    return [dict(base) for _ in range(STEADY_STATE_WINDOW_SIZE)]


@pytest.fixture(scope="session")
def transient_window() -> List[Dict[str, float]]:
    """30 samples with a large RPM step change — RPM CV >> 0.01 → not steady."""
    sim = EngineSimulator(seed=3)
    for _ in range(60):
        sim.step()
    window = []
    for i in range(STEADY_STATE_WINDOW_SIZE):
        sample = dict(sim.step())
        sample["rpm"] = 1000.0 if i < STEADY_STATE_WINDOW_SIZE // 2 else 2500.0
        window.append(sample)
    return window
