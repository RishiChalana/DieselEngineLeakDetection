"""
session_analysis/views.py — Batch CSV inference endpoint.

POST /api/session/ accepts a multipart CSV upload or a raw CSV body,
runs ModelStack.predict() on each row, and returns a structured Go/No-Go
report via SessionReportGenerator.
"""
import io
import logging
import sys
from pathlib import Path

import pandas as pd
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from config.constants import SENSOR_COLS
from ml_model.models.model_stack import ModelStack
from .report_generator import SessionReportGenerator

logger = logging.getLogger(__name__)

_MAX_ROWS: int = 10_000


class AnalyzeSessionView(APIView):
    """Batch inference over a CSV session file.

    Accepts multipart/form-data with a ``file`` field (CSV) or a raw CSV
    body (Content-Type: text/csv).  Each row must contain all 12 SENSOR_COLS
    channels.  Returns a Go/No-Go session report with per-sample statistics.

    Request (multipart):
        file — CSV file with header row; columns must include all SENSOR_COLS.

    Request (raw body):
        Content-Type: text/csv — raw CSV text body.

    Response (200):
        Structured session report dict from SessionReportGenerator.generate().

    Response (400):
        error, missing_columns / required_columns when CSV is invalid.

    Response (500):
        error when model inference raises an unexpected exception.
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request: Request, *args, **kwargs) -> Response:
        """Run batch inference and return a session report.

        Args:
            request: Multipart or raw-body CSV request.

        Returns:
            DRF Response with report dict or error payload.
        """
        logger.debug("POST /api/session/ — content_type=%s", request.content_type)

        csv_bytes = self._extract_csv_bytes(request)
        if csv_bytes is None:
            return Response(
                {
                    "error": (
                        "No CSV data found. Send a 'file' field "
                        "or set Content-Type: text/csv."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        df, parse_error = self._parse_csv(csv_bytes)
        if parse_error:
            return Response(
                {"error": f"CSV parse error: {parse_error}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        missing_cols = [c for c in SENSOR_COLS if c not in df.columns]
        if missing_cols:
            return Response(
                {
                    "error": "CSV missing required sensor columns.",
                    "missing_columns": missing_cols,
                    "required_columns": SENSOR_COLS,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if len(df) > _MAX_ROWS:
            logger.info("Session CSV truncated from %d to %d rows", len(df), _MAX_ROWS)
            df = df.head(_MAX_ROWS)

        per_sample, infer_error = self._run_inference(df)
        if infer_error:
            return Response(
                {"error": "Model inference failed. Check server logs."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        report = SessionReportGenerator().generate(per_sample)
        logger.info(
            "Session analysis complete — samples=%d  go_nogo=%s  leak_rate=%.1f%%",
            len(per_sample),
            report["header"]["go_nogo"],
            report["session_summary"]["leak_rate_pct"],
        )
        return Response(report, status=status.HTTP_200_OK)

    @staticmethod
    def _extract_csv_bytes(request: Request) -> bytes | None:
        if "file" in request.FILES:
            return request.FILES["file"].read()
        ct = request.content_type or ""
        if "text/csv" in ct or "application/octet-stream" in ct:
            return request.body
        return None

    @staticmethod
    def _parse_csv(data: bytes):
        try:
            return pd.read_csv(io.BytesIO(data)), None
        except Exception as exc:  # noqa: BLE001
            return None, str(exc)

    @staticmethod
    def _run_inference(df: pd.DataFrame):
        ms = ModelStack()
        results = []
        try:
            for _, row in df[SENSOR_COLS].iterrows():
                sensor_dict = {col: float(row[col]) for col in SENSOR_COLS}
                results.append(ms.predict(sensor_dict))
        except Exception as exc:  # noqa: BLE001
            logger.exception("Batch inference error at row %d: %s", len(results), exc)
            return None, str(exc)
        return results, None
