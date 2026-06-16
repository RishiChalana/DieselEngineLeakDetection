"""
steady_state.py — Engine steady-state gate for the leak detection pipeline.

Steady-state detection is a prerequisite for reliable anomaly scoring.
During transients (load steps, RPM sweeps, startup/shutdown), sensor signatures
overlap heavily with leak signatures; scoring those samples produces false positives.

The detector computes per-channel coefficient of variation (CV = std/mean) over a
rolling window and reports whether the engine has settled to a stable operating point.

Usage::

    detector = SteadyStateDetector()
    result = detector.check(window_of_samples)
    if result["is_steady"]:
        # proceed to ML scoring
"""
import logging
import sys
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional

import numpy as np

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from config.constants import (
    STEADY_STATE_BOOST_CV_MAX,
    STEADY_STATE_FUEL_CV_MAX,
    STEADY_STATE_MAF_CV_MAX,
    STEADY_STATE_RPM_CV_MAX,
    STEADY_STATE_WINDOW_SIZE,
)

logger = logging.getLogger(__name__)

# Channels used as stability indicators; others are not checked by default.
_DEFAULT_CHANNELS: List[str] = ["rpm", "fuel_rate", "MAF", "boost_pressure"]

# CV thresholds per channel (pulled from constants, indexed by channel name).
_DEFAULT_CV_LIMITS: Dict[str, float] = {
    "rpm":            STEADY_STATE_RPM_CV_MAX,
    "fuel_rate":      STEADY_STATE_FUEL_CV_MAX,
    "MAF":            STEADY_STATE_MAF_CV_MAX,
    "boost_pressure": STEADY_STATE_BOOST_CV_MAX,
}


def _cv(values: List[float]) -> float:
    """Return coefficient of variation (std/mean), guarded against zero mean.

    Args:
        values: Non-empty list of floats.

    Returns:
        CV as a float; 0.0 when the mean is effectively zero.
    """
    arr = np.asarray(values, dtype=float)
    mean = float(np.mean(arr))
    if abs(mean) < 1e-9:
        return 0.0
    return float(np.std(arr)) / abs(mean)


class SteadyStateDetector:
    """Determines whether the engine is at steady state using CV per channel.

    All CV thresholds and the evaluation window size come from
    ``config.constants``. Override via ``from_config()`` for per-engine tuning.

    Attributes:
        cv_limits: Dict mapping channel name → maximum acceptable CV.
        window_size: Number of consecutive samples evaluated per check.
    """

    _DEFAULT_CV_LIMITS: ClassVar[Dict[str, float]] = _DEFAULT_CV_LIMITS

    def __init__(
        self,
        cv_limits: Optional[Dict[str, float]] = None,
        window_size: int = STEADY_STATE_WINDOW_SIZE,
    ) -> None:
        """Initialise with threshold overrides and optional window size.

        Args:
            cv_limits: Per-channel CV thresholds; defaults to ``_DEFAULT_CV_LIMITS``.
            window_size: Number of samples per evaluation window.
        """
        self.cv_limits: Dict[str, float] = cv_limits or dict(_DEFAULT_CV_LIMITS)
        self.window_size: int = window_size

    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> "SteadyStateDetector":
        """Construct from a per-engine config dict for run-time tuning.

        Args:
            config: Dict with optional keys ``cv_limits`` and ``window_size``.

        Returns:
            A configured SteadyStateDetector instance.

        Example::

            detector = SteadyStateDetector.from_config({
                "cv_limits": {"rpm": 0.005, "fuel_rate": 0.02},
                "window_size": 15,
            })
        """
        return cls(
            cv_limits=config.get("cv_limits"),
            window_size=config.get("window_size", STEADY_STATE_WINDOW_SIZE),
        )

    def check(self, window: List[Dict[str, float]]) -> Dict[str, Any]:
        """Evaluate whether the engine is at steady state.

        Args:
            window: List of sensor dicts (must have ≥ 1 entry). If fewer than
                ``window_size`` samples are provided the check uses what is available.

        Returns:
            Dict with keys:

            * ``is_steady`` (bool): True when all monitored channels are within
              their CV thresholds.
            * ``confidence`` (float [0, 1]): Fraction of channels within threshold;
              1.0 = perfectly stable.
            * ``reason`` (str): Human-readable summary for logging/UI.
            * ``unstable_channels`` (list[str]): Channels exceeding their limits.
            * ``window_stats`` (dict): Per-channel mean, std, cv.
        """
        if not window:
            return self._result(False, [], {}, "Empty window — cannot assess stability")

        stats: Dict[str, Dict[str, float]] = {}
        unstable: List[str] = []

        for channel, limit in self.cv_limits.items():
            values = [s[channel] for s in window if channel in s]
            if not values:
                continue
            mean_val = float(np.mean(values))
            std_val = float(np.std(values))
            cv_val = _cv(values)
            stats[channel] = {"mean": round(mean_val, 4), "std": round(std_val, 4), "cv": round(cv_val, 6)}
            if cv_val > limit:
                unstable.append(channel)

        total = len(self.cv_limits)
        stable_count = total - len(unstable)
        confidence = round(stable_count / max(total, 1), 4)
        is_steady = len(unstable) == 0

        if is_steady:
            reason = (
                f"All {total} channels within CV thresholds over {len(window)}-sample window"
            )
        else:
            parts = []
            for ch in unstable:
                s = stats.get(ch, {})
                parts.append(f"{ch} CV={s.get('cv', 0):.3f} > limit {self.cv_limits[ch]:.3f}")
            reason = "Unstable: " + "; ".join(parts)

        logger.debug("SteadyStateDetector: is_steady=%s  %s", is_steady, reason)
        return self._result(is_steady, unstable, stats, reason, confidence)

    @staticmethod
    def _result(
        is_steady: bool,
        unstable_channels: List[str],
        window_stats: Dict[str, Any],
        reason: str,
        confidence: float = 0.0,
    ) -> Dict[str, Any]:
        """Pack the result dict.

        Args:
            is_steady: Stability verdict.
            unstable_channels: Channels that failed the CV check.
            window_stats: Per-channel statistics dict.
            reason: Human-readable explanation.
            confidence: Fraction of channels within threshold.

        Returns:
            Standardised result dict.
        """
        return {
            "is_steady": is_steady,
            "confidence": confidence,
            "reason": reason,
            "unstable_channels": unstable_channels,
            "window_stats": window_stats,
        }
