"""
test_websocket.py — Integration tests for the WebSocket consumer.

Uses Django Channels' WebsocketCommunicator to exercise the EngineConsumer
without a real network connection.

Run with:  pytest tests/test_websocket.py -v --ds=diesel_engine_predictor.settings
"""
import sys
from pathlib import Path
from typing import Dict

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

_REGISTRATION_MSG = {"model_no": "TEST-ENGINE-001", "engine_type": "diesel"}

_SENSOR_SAMPLE: Dict[str, float] = {
    "rpm": 1600.0,
    "fuel_rate": 75.0,
    "turbo_speed": 90000.0,
    "boost_pressure": 1.2,
    "MAP": 2.2,
    "IAT": 305.0,
    "MAF": 500.0,
    "EGT": 650.0,
    "exhaust_pressure": 2.5,
    "VGT": 50.0,
    "DPF_delta": 20000.0,
    "ambient_pressure": 1.0,
}


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_anonymous_connection_is_rejected() -> None:
    """Anonymous WebSocket connections must be closed immediately."""
    # TODO: use WebsocketCommunicator with AnonymousUser scope
    # TODO: assert not connected
    pass


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_engine_registration_returns_engine_registered_message() -> None:
    """First message with model_no should return type='engine_registered'."""
    pass


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_missing_model_no_closes_connection() -> None:
    """First message without model_no should return type='error' and close."""
    pass


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_sensor_sample_before_stability_returns_buffering() -> None:
    """Sensor samples before stability window fills should return type='buffering'."""
    pass


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_sample_result_message_has_all_z_score_keys() -> None:
    """sample_result message must contain all 7 z_score keys."""
    # TODO: assert all of boost/dpf/maf/exhaust/mahalanobis/svm/cumulative present
    pass


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_window_result_sent_after_window_size_samples() -> None:
    """After INFERENCE_WINDOW_SIZE samples, a window_result message should arrive."""
    pass


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_test_complete_sent_on_leak_confirmation() -> None:
    """After CONFIRMATION_WINDOWS_REQUIRED anomalous windows, test_complete is sent."""
    pass
