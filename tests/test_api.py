"""
test_api.py — Integration tests for the REST API endpoints.

Tests /user_auth/ and /api/predict using Django's test client.
Requires a migrated test database (handled automatically by pytest-django).

Run with:  pytest tests/test_api.py -v --ds=diesel_engine_predictor.settings
"""
import sys
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# Minimal healthy sensor payload matching all 12 required channels.
_HEALTHY_PAYLOAD = {
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


@pytest.mark.django_db
def test_signup_creates_user_and_returns_token(client) -> None:
    """POST /user_auth/signup/ should return 201 with a token."""
    # TODO: assert response.status_code == 201
    # TODO: assert "token" in response.json()
    pass


@pytest.mark.django_db
def test_login_with_valid_credentials_returns_token(client) -> None:
    """POST /user_auth/login/ should return 200 with token for valid user."""
    pass


@pytest.mark.django_db
def test_login_with_invalid_credentials_returns_401(client) -> None:
    """POST /user_auth/login/ should return 401 for wrong password."""
    pass


@pytest.mark.django_db
def test_predict_without_auth_returns_401(client) -> None:
    """POST /api/predict without token should return 401."""
    # TODO: assert client.post("/api/predict", ...).status_code == 401
    pass


@pytest.mark.django_db
def test_predict_with_missing_channels_returns_400(client) -> None:
    """POST /api/predict missing required channels should return 400."""
    pass


@pytest.mark.django_db
def test_predict_with_valid_payload_returns_200(client) -> None:
    """POST /api/predict with all 12 channels should return 200 with is_leak key."""
    # TODO: assert "is_leak" in response.json()
    pass


@pytest.mark.django_db
def test_predict_response_has_all_required_keys(client) -> None:
    """POST /api/predict response must include all documented output fields."""
    pass


@pytest.mark.django_db
def test_logout_invalidates_token(client) -> None:
    """POST /user_auth/logout/ should return 200 and invalidate the token."""
    pass
