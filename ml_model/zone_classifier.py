"""
zone_classifier.py — Subsystem zone isolation for detected leaks.

Localises a confirmed leak to one of four engine subsystem zones using:
  1. Weighted voting from per-subsystem autoencoder z-scores (primary signal).
  2. Physics-based consistency checks (mass balance, pressure ratio) that
     raise or lower confidence in the ML-suggested zone.

Zones:
  zone_1 — Pre-compressor intake (Airflow meter → Compressor inlet)
  zone_2 — Charge-air system (Compressor outlet → CAC → Intake ports)
  zone_3 — Exhaust path (Manifold → Turbine → Aftertreatment)
  zone_4 — Test cell ducting interfaces

Only call this after a leak is already confirmed (z_cumulative ≥ ANOMALY_THRESHOLD).
"""
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from config.constants import (
    BOOST_BELOW_EXPECTED_FACTOR,
    RECOMMENDED_ACTIONS,
    TURBO_ABOVE_EXPECTED_FACTOR,
    ZONE_AE_WEIGHTS,
    ZONE_FLOOR,
    ZONE_LABELS,
    ZONE_MULTIPLE_DELTA,
)

logger = logging.getLogger(__name__)

_ZONES = ["zone_1", "zone_2", "zone_3", "zone_4"]

# Expected MAP/boost_pressure ratio for healthy charge-air path (dimensionless).
# MAP (absolute) should be somewhat above ambient; boost adds ~0.3–1.5 bar gauge.
_PRESSURE_RATIO_MIN: float = 1.1
_PRESSURE_RATIO_MAX: float = 2.5

# Expected MAF per unit fuel_rate during healthy stoichiometric/lean diesel combustion.
# Approximate air-to-fuel mass ratio window for diesel: 18–80 (highly load-dependent).
_AFR_MIN: float = 15.0
_AFR_MAX: float = 90.0


class ZoneClassifier:
    """Localises a detected leak to one of four engine subsystem zones.

    Uses weighted voting across per-subsystem autoencoder z-scores plus physics
    checks. Physics checks act as validators: they boost confidence when they
    agree with the ML zone and reduce it when they contradict.

    All weights and zone definitions come from ``config.constants``.
    """

    def analyze(
        self,
        subsystem_z: Dict[str, float],
        channel_z: Dict[str, float],
        raw_sample: Dict[str, float],
    ) -> Dict[str, Any]:
        """Localise the leak to a zone.

        Args:
            subsystem_z: Dict with keys ``boost``, ``dpf``, ``maf``, ``exhaust``
                — the per-autoencoder z-scores from ModelStack.evaluate().
            channel_z: Optional per-channel z-scores (unused in current implementation;
                reserved for future per-channel anomaly model). Pass an empty dict
                if not available.
            raw_sample: Raw (or Kalman-filtered) sensor dict for physics checks.

        Returns:
            Dict with keys:

            * ``detected_zone`` (str): Primary zone or "multiple"/"unknown".
            * ``zone_scores`` (dict): Normalised zone scores [0, 1].
            * ``zone_label`` (str): Human-readable zone description.
            * ``supporting_evidence`` (list[str]): Explanation strings.
            * ``physics_check`` (dict): mass_balance_ok, pressure_ratio_ok, notes.
        """
        raw_scores = self._compute_raw_zone_scores(subsystem_z)
        norm_scores = self._normalise(raw_scores)
        detected_zone, evidence = self._vote(norm_scores, subsystem_z)
        physics = self._run_physics_checks(raw_sample, detected_zone)
        detected_zone = self._apply_physics_adjustment(
            detected_zone, norm_scores, physics, raw_sample
        )

        return {
            "detected_zone": detected_zone,
            "zone_scores": {z: round(norm_scores.get(z, 0.0), 4) for z in _ZONES},
            "zone_label": ZONE_LABELS.get(detected_zone, ZONE_LABELS["unknown"]),
            "supporting_evidence": evidence,
            "physics_check": physics,
        }

    # ------------------------------------------------------------------
    # Zone scoring
    # ------------------------------------------------------------------

    def _compute_raw_zone_scores(
        self, subsystem_z: Dict[str, float]
    ) -> Dict[str, float]:
        """Compute weighted sum of AE z-scores for each zone.

        Args:
            subsystem_z: AE z-scores keyed by subsystem name.

        Returns:
            Dict of unnormalised zone scores.
        """
        scores: Dict[str, float] = {}
        for zone, weights in ZONE_AE_WEIGHTS.items():
            scores[zone] = sum(
                weight * subsystem_z.get(sub, 0.0)
                for sub, weight in weights.items()
            )
        return scores

    @staticmethod
    def _normalise(raw: Dict[str, float]) -> Dict[str, float]:
        """Normalise raw zone scores to sum to 1.0.

        Args:
            raw: Unnormalised zone score dict.

        Returns:
            Normalised dict; all zeros if total is zero.
        """
        total = sum(raw.values())
        if total < 1e-10:
            return {z: 0.0 for z in raw}
        return {z: v / total for z, v in raw.items()}

    def _vote(
        self,
        norm: Dict[str, float],
        subsystem_z: Dict[str, float],
    ) -> Tuple[str, List[str]]:
        """Determine detected zone from normalised scores.

        Args:
            norm: Normalised zone scores.
            subsystem_z: Raw AE z-scores for evidence text generation.

        Returns:
            Tuple of (zone_name, list_of_evidence_strings).
        """
        if not norm:
            return "unknown", ["No subsystem z-scores provided"]

        sorted_zones = sorted(norm.items(), key=lambda x: x[1], reverse=True)
        top_zone, top_score = sorted_zones[0]
        second_zone, second_score = sorted_zones[1] if len(sorted_zones) > 1 else ("none", 0.0)

        evidence = self._build_evidence(top_zone, subsystem_z, norm)

        if top_score < ZONE_FLOOR:
            return "unknown", ["All zone scores below floor — pattern unclear"]

        if (
            second_score >= ZONE_FLOOR
            and abs(top_score - second_score) / max(top_score, 1e-10) <= ZONE_MULTIPLE_DELTA
        ):
            evidence.append(
                f"{top_zone} ({top_score:.2f}) and {second_zone} ({second_score:.2f}) "
                f"within {ZONE_MULTIPLE_DELTA*100:.0f}% → ambiguous isolation"
            )
            return "multiple", evidence

        return top_zone, evidence

    @staticmethod
    def _build_evidence(
        zone: str,
        subsystem_z: Dict[str, float],
        norm: Dict[str, float],
    ) -> List[str]:
        """Build human-readable evidence strings for the top zone.

        Args:
            zone: The winning zone identifier.
            subsystem_z: AE z-scores for context.
            norm: Normalised zone scores.

        Returns:
            List of evidence strings.
        """
        evidence: List[str] = []
        z_maf     = subsystem_z.get("maf",     0.0)
        z_boost   = subsystem_z.get("boost",   0.0)
        z_exhaust = subsystem_z.get("exhaust", 0.0)
        z_dpf     = subsystem_z.get("dpf",     0.0)

        if zone == "zone_1":
            evidence.append(
                f"maf_z {z_maf:.2f}σ elevated while boost_z {z_boost:.2f}σ near normal "
                f"→ air loss before compressor (pre-compressor intake)"
            )
        elif zone == "zone_2":
            evidence.append(
                f"boost_z {z_boost:.2f}σ high while maf_z {z_maf:.2f}σ near normal "
                f"→ leak downstream of MAF sensor (charge-air circuit)"
            )
        elif zone == "zone_3":
            evidence.append(
                f"exhaust_z {z_exhaust:.2f}σ / dpf_z {z_dpf:.2f}σ elevated "
                f"→ anomaly in exhaust path or aftertreatment"
            )
        elif zone == "zone_4":
            evidence.append(
                f"Diffuse anomaly across zones (maf={z_maf:.2f}, boost={z_boost:.2f}, "
                f"exhaust={z_exhaust:.2f}) → possible test-cell ducting interface issue"
            )

        evidence.append(
            f"Zone scores: " + ", ".join(f"{z}={norm[z]:.2f}" for z in _ZONES)
        )
        return evidence

    # ------------------------------------------------------------------
    # Physics checks
    # ------------------------------------------------------------------

    def _run_physics_checks(
        self,
        raw_sample: Dict[str, float],
        candidate_zone: str,
    ) -> Dict[str, Any]:
        """Run mass balance and pressure ratio checks.

        Args:
            raw_sample: Sensor dict (Kalman-filtered or raw).
            candidate_zone: ML-suggested zone for context in the notes field.

        Returns:
            Dict with ``mass_balance_ok`` (bool), ``pressure_ratio_ok`` (bool),
            ``notes`` (str).
        """
        mass_ok, mass_note = self._mass_balance_check(raw_sample)
        pressure_ok, pressure_note = self._pressure_ratio_check(raw_sample)

        notes = "; ".join(filter(None, [mass_note, pressure_note]))
        return {
            "mass_balance_ok":    mass_ok,
            "pressure_ratio_ok":  pressure_ok,
            "notes": notes or "Physics checks passed",
        }

    @staticmethod
    def _mass_balance_check(
        sample: Dict[str, float],
    ) -> Tuple[bool, str]:
        """Check air/fuel mass balance via approximate AFR.

        Air-to-fuel ratio (AFR) outside the healthy diesel range [15, 90]
        suggests either a pre-compressor air leak (MAF low for the fuel rate)
        or a fuel system fault.

        Args:
            sample: Sensor dict.

        Returns:
            (ok, note_string) — ok is False when AFR is outside expected range.
        """
        maf = sample.get("MAF", 0.0)
        fuel = sample.get("fuel_rate", 0.0)
        if fuel < 1e-3:
            return True, ""
        afr = maf / fuel
        ok = _AFR_MIN <= afr <= _AFR_MAX
        note = "" if ok else f"AFR={afr:.1f} outside [{_AFR_MIN},{_AFR_MAX}] — air/fuel imbalance"
        return ok, note

    @staticmethod
    def _pressure_ratio_check(
        sample: Dict[str, float],
    ) -> Tuple[bool, str]:
        """Check MAP/ambient_pressure ratio is consistent with boost.

        A MAP/ambient ratio far below expected indicates charge-air path loss
        (Zone 2 signature). Ratio near 1.0 while boost is commanded suggests
        a downstream leak between the compressor and intake manifold.

        Args:
            sample: Sensor dict.

        Returns:
            (ok, note_string) — ok is False when the ratio is out of range.
        """
        map_val = sample.get("MAP", 0.0)
        ambient = sample.get("ambient_pressure", 1.0)
        if ambient < 1e-3:
            return True, ""
        ratio = map_val / ambient
        ok = _PRESSURE_RATIO_MIN <= ratio <= _PRESSURE_RATIO_MAX
        note = (
            "" if ok
            else f"MAP/ambient={ratio:.2f} outside [{_PRESSURE_RATIO_MIN},{_PRESSURE_RATIO_MAX}] "
                 f"→ charge-air pressure anomaly"
        )
        return ok, note

    # ------------------------------------------------------------------
    # Physics adjustment
    # ------------------------------------------------------------------

    def _apply_physics_adjustment(
        self,
        zone: str,
        norm: Dict[str, float],
        physics: Dict[str, Any],
        raw_sample: Optional[Dict[str, float]] = None,
    ) -> str:
        """Optionally override zone if physics checks strongly contradict ML.

        Rules applied in order:
        1. zone_1 + MAP/ambient anomaly → zone_2 (charge-air pressure loss).
        2. zone_3 + boost-below-expected-for-turbo → zone_2 (charge_air vs exhaust
           discrimination: charge_air explicitly reduces boost while turbo rises;
           exhaust recalculates boost from the reduced turbo, keeping ratio ~1.0).

        Args:
            zone: ML-suggested zone.
            norm: Normalised zone scores.
            physics: Physics check result dict.
            raw_sample: Raw sensor dict for turbo-boost check.

        Returns:
            Possibly adjusted zone string.
        """
        # Rule 1: zone_1 + MAP/ambient anomaly → zone_2 (charge-air pressure loss).
        if zone == "zone_1" and not physics["pressure_ratio_ok"]:
            z2_score = norm.get("zone_2", 0.0)
            if z2_score > ZONE_FLOOR:
                logger.debug(
                    "Physics override: MAP/ambient anomaly contradicts zone_1; upgrading to zone_2"
                )
                return "zone_2"

        if raw_sample:
            boost_deficit = self._boost_below_expected(raw_sample)

            # Rule 2: boost too low for current turbo → charge_air (zone_2).
            # Applies when ML voted zone_3 or was ambiguous (multiple).
            # Reason: charge_air reduces boost explicitly while raising turbo;
            # exhaust and precompressor recalculate boost from the new turbo, so
            # their ratio stays near 1.0.
            if zone in ("zone_3", "multiple") and boost_deficit:
                z2_score = norm.get("zone_2", 0.0)
                if z2_score > ZONE_FLOOR:
                    logger.debug(
                        "Physics override: boost/turbo ratio below expected; "
                        "%s → zone_2 (charge-air pattern)",
                        zone,
                    )
                    return "zone_2"

            # Rule 3: turbo elevated without boost deficit → precompressor (zone_1).
            # Applies only when ML was ambiguous (multiple), not zone_3, because
            # exhaust produces depressed turbo, not elevated, so it won't trigger here.
            if zone == "multiple" and not boost_deficit:
                if self._turbo_above_expected(raw_sample):
                    z1_score = norm.get("zone_1", 0.0)
                    if z1_score > ZONE_FLOOR:
                        logger.debug(
                            "Physics override: turbo elevated without boost deficit; "
                            "multiple → zone_1 (precompressor pattern)"
                        )
                        return "zone_1"

        return zone

    @staticmethod
    def _boost_below_expected(sample: Dict[str, float]) -> bool:
        """Return True when boost pressure is too low for the current turbo speed.

        For a charge_air leak the simulator explicitly reduces boost while raising
        turbo_speed, so actual_boost / expected_boost << 1.  For an exhaust leak,
        boost is recalculated from the already-reduced turbo_speed, keeping the
        ratio near 1.0.  The threshold ``BOOST_BELOW_EXPECTED_FACTOR`` (0.82) sits
        safely between the two patterns for severity ≥ 0.15.

        The expected-boost formula mirrors ``physics.calculate_boostpressure``:
            expected = 0.000016 * turbo + 0.003 * fuel + 0.25 * (fuel / 120)

        Args:
            sample: Kalman-filtered sensor dict.

        Returns:
            True when boost is anomalously low relative to turbo.
        """
        turbo = sample.get("turbo_speed", 0.0)
        boost = sample.get("boost_pressure", 0.0)
        fuel = sample.get("fuel_rate", 0.0)
        if turbo < 1e3:
            return False
        load = fuel / 120.0
        expected = 0.000016 * turbo + 0.003 * fuel + 0.25 * load
        if expected < 1e-6:
            return False
        return (boost / expected) < BOOST_BELOW_EXPECTED_FACTOR

    @staticmethod
    def _turbo_above_expected(sample: Dict[str, float]) -> bool:
        """Return True when turbo speed is elevated above what the fuel rate predicts.

        For a precompressor leak the simulator raises turbo by ``(1+0.2*s)`` while
        exhaust leaks depress it by ``(1-0.6*s)``.  Comparing against the fuel-rate
        prediction distinguishes the two patterns when the ML vote is ambiguous.

        The expected-turbo formula mirrors ``physics.calculate_turbospeed``:
            expected = 28 000 + 400 * fuel + 0.00008 * fuel²  (clipped to 55 000)

        Args:
            sample: Kalman-filtered sensor dict.

        Returns:
            True when actual turbo exceeds ``TURBO_ABOVE_EXPECTED_FACTOR`` × expected.
        """
        turbo = sample.get("turbo_speed", 0.0)
        fuel = sample.get("fuel_rate", 0.0)
        if turbo < 1e3:
            return False
        expected = max(28000.0 + 400.0 * fuel + 0.00008 * fuel ** 2, 55000.0)
        return (turbo / expected) > TURBO_ABOVE_EXPECTED_FACTOR
