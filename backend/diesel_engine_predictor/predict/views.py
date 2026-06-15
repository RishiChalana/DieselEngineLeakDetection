"""
predict/views.py — REST endpoint for single-shot engine leak inference.

Exposes POST /api/predict which accepts one sensor reading (12 channels),
runs the full ML pipeline through ModelStack, and returns the result.
"""
import logging
import sys
from pathlib import Path

from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status

# Ensure project root is resolvable before importing ml_model packages.
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from config.constants import SENSOR_COLS
from ml_model.models.model_stack import ModelStack

logger = logging.getLogger(__name__)


class Predict(APIView):
    """Single-shot leak inference over one sensor sample.

    Requires token authentication. Validates that all 12 required sensor
    channels are present before invoking the ML pipeline.
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request: Request, *args, **kwargs) -> Response:
        """Run full inference pipeline on one sensor reading.

        Args:
            request: DRF request whose ``data`` dict must contain all sensor
                channels listed in ``config.constants.SENSOR_COLS``.

        Returns:
            200 with ModelStack output dict on success.
            400 if required channels are missing or values are non-numeric.
            500 if model inference raises an unexpected exception.
        """
        logger.debug("POST /api/predict — payload keys: %s", list(request.data.keys()))

        # --- Validate presence of all required channels ---
        missing = [col for col in SENSOR_COLS if col not in request.data]
        if missing:
            logger.warning("Predict request missing channels: %s", missing)
            return Response(
                {
                    "error": "Missing required sensor channels.",
                    "missing_channels": missing,
                    "required_channels": SENSOR_COLS,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # --- Parse and type-validate sensor values ---
        sensor_data: dict = {}
        malformed: list = []
        for col in SENSOR_COLS:
            try:
                sensor_data[col] = float(request.data[col])
            except (TypeError, ValueError):
                malformed.append(col)

        if malformed:
            logger.warning("Predict request has non-numeric channels: %s", malformed)
            return Response(
                {
                    "error": "Non-numeric values for sensor channels.",
                    "malformed_channels": malformed,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        logger.debug("Predict: running ModelStack.predict() on validated sensor data")

        # --- Run inference ---
        try:
            result = ModelStack().predict(sensor_data)
        except Exception as exc:  # noqa: BLE001
            logger.exception("ModelStack inference failed: %s", exc)
            return Response(
                {"error": "Model inference failed. Check server logs."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        logger.debug(
            "Predict result — is_leak=%s  z_cumulative=%.4f  confidence=%.4f",
            result["is_leak"],
            result["z_cumulative"],
            result["confidence"],
        )

        return Response(result, status=status.HTTP_200_OK)
