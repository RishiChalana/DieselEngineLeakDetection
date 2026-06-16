"""
validate_zone_isolation.py — Zone isolation diagnostic script.

Generates 20 windows per leak type using EngineSimulator, runs the full
ModelStack.predict() pipeline on each, and prints a discrimination table
showing whether each leak type consistently maps to the expected zone.

Expected mappings (physics):
  no_leak       → is_leak=False, no zone
  precompressor → Zone 1 (MAF drops, boost stays normal)
  charge_air    → Zone 2 (boost drops, MAF follows MAP)
  exhaust       → Zone 3 (exhaust_pressure drops, turbo slows)

Usage::
    python scripts/validate_zone_isolation.py
"""
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from ml_model.data_gen.engine_simulator_core import EngineSimulator
from ml_model.models.model_stack import ModelStack

# Leak types supported by EngineSimulator.introduce_leak()
_LEAK_TYPES = ["precompressor", "charge_air", "exhaust"]
_WINDOWS_PER_TYPE = 20
_WARMUP_STEPS = 60
# After introduce_leak() the severity is set directly to _LEAK_SEVERITY_TARGET so
# the diagnostic tests at a realistic operational severity without waiting ~2 000
# steps for the gradual escalation (0.0003 growth rate) to reach it.
_LEAK_SEVERITY_TARGET: float = 0.40
_LEAK_STABILISE_STEPS: int = 50

# Expected zone for each leak type (for PASS/FAIL evaluation)
_EXPECTED_ZONE = {
    "no_leak":       None,
    "precompressor": "zone_1",
    "charge_air":    "zone_2",
    "exhaust":       "zone_3",
}


def _run_window(
    simulator: EngineSimulator,
    ms: ModelStack,
    n_steps: int = 1,
) -> Dict[str, Any]:
    """Step the simulator n_steps times and return the last predict() result.

    Args:
        simulator: Primed EngineSimulator instance.
        ms: Loaded ModelStack singleton.
        n_steps: How many steps to advance before sampling.

    Returns:
        Full predict() dict from the final step.
    """
    for _ in range(n_steps - 1):
        simulator.step()
    sample = simulator.step()
    return ms.predict(sample)


def _collect_windows(
    leak_type: Optional[str],
    n_windows: int,
    seed_base: int,
) -> List[Dict[str, Any]]:
    """Collect n_windows predict() results for a given leak type.

    Args:
        leak_type: One of the EngineSimulator leak type strings, or None for healthy.
        n_windows: Number of windows to generate.
        seed_base: Base seed; each window uses seed_base + window_index.

    Returns:
        List of predict() result dicts.
    """
    ms = ModelStack()
    results: List[Dict[str, Any]] = []

    for i in range(n_windows):
        sim = EngineSimulator(seed=seed_base + i * 7)
        for _ in range(_WARMUP_STEPS):
            sim.step()
        if leak_type is not None:
            sim.introduce_leak(leak_type=leak_type)
            # Jump to target severity immediately; the gradual growth rate (0.0003/step)
            # would require ~2 000 steps to reach 0.40 naturally.
            sim.leak_severity = _LEAK_SEVERITY_TARGET
            for _ in range(_LEAK_STABILISE_STEPS):
                sim.step()
        result = _run_window(sim, ms)
        results.append(result)

    return results


def _aggregate(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute mean z-scores, zone frequency, and detection rate.

    Args:
        results: List of predict() dicts.

    Returns:
        Aggregated statistics dict.
    """
    det = [r["detection"] for r in results]
    iso = [r["isolation"] for r in results if r["isolation"]]

    def mean(vals: List[float]) -> float:
        return float(np.mean(vals)) if vals else 0.0

    zone_counts: Dict[str, int] = {}
    for r in results:
        z = r["isolation"].get("detected_zone", "none") if r["isolation"] else "none"
        zone_counts[z] = zone_counts.get(z, 0) + 1

    top_zone = max(zone_counts, key=zone_counts.get) if zone_counts else "none"
    top_zone_freq = zone_counts.get(top_zone, 0) / len(results)

    return {
        "n":          len(results),
        "leak_rate":  mean([float(d["is_leak"]) for d in det]),
        "maf_z":      mean([d["subsystem_z"]["maf"] for d in det]),
        "boost_z":    mean([d["subsystem_z"]["boost"] for d in det]),
        "exhaust_z":  mean([d["subsystem_z"]["exhaust"] for d in det]),
        "dpf_z":      mean([d["subsystem_z"]["dpf"] for d in det]),
        "svm_z":      mean([d["svm_z"] for d in det]),
        "mahal_z":    mean([d["mahal_z"] for d in det]),
        "top_zone":   top_zone,
        "top_zone_pct": top_zone_freq * 100,
        "zone_counts": zone_counts,
        "mean_confidence": mean([d["confidence"] for d in det]),
    }


def _evaluate_discrimination(
    leak_type: Optional[str],
    agg: Dict[str, Any],
) -> str:
    """Return OK / WEAK / FAIL based on whether the zone matches expectation.

    Args:
        leak_type: The simulated leak type (None for healthy).
        agg: Aggregated statistics from _aggregate().

    Returns:
        "OK", "WEAK", or "FAIL" string.
    """
    expected = _EXPECTED_ZONE.get(str(leak_type) if leak_type else "no_leak")

    if leak_type is None:
        return "OK" if agg["leak_rate"] < 0.2 else "FAIL (healthy flagged as leak)"

    if agg["leak_rate"] < 0.5:
        return "WEAK (leak detection rate < 50%)"

    if agg["top_zone"] == expected and agg["top_zone_pct"] >= 50:
        return "OK"
    elif agg["top_zone"] == expected:
        return f"WEAK ({agg['top_zone_pct']:.0f}% → {expected}, expected ≥50%)"
    else:
        return f"FAIL (got {agg['top_zone']}, expected {expected})"


def main() -> None:
    """Run the zone isolation diagnostic and print the discrimination table."""
    print("=" * 90)
    print("ZONE ISOLATION DIAGNOSTIC — ModelStack.predict() zone discrimination")
    print("=" * 90)
    print(f"Leak types: {_LEAK_TYPES}  |  Windows per type: {_WINDOWS_PER_TYPE}")
    print(
        f"Warmup: {_WARMUP_STEPS} steps  |  "
        f"Leak severity: {_LEAK_SEVERITY_TARGET} (direct)  |  "
        f"Stabilise: {_LEAK_STABILISE_STEPS} steps"
    )
    print()

    all_types = [None] + _LEAK_TYPES  # None = healthy baseline
    aggregated: Dict[str, Dict[str, Any]] = {}

    for i, lt in enumerate(all_types):
        label = lt or "no_leak"
        print(f"  Collecting: {label} ...", end="", flush=True)
        results = _collect_windows(lt, _WINDOWS_PER_TYPE, seed_base=i * 100)
        agg = _aggregate(results)
        aggregated[label] = agg
        print(f" done (leak_rate={agg['leak_rate']:.0%})")

    print()
    print("-" * 90)
    print(
        f"{'Leak Type':<16} {'maf_z':>7} {'boost_z':>7} {'exhaust_z':>9} {'dpf_z':>7}"
        f" {'svm_z':>6} {'mahal_z':>7} {'top_zone':>10} {'zone%':>6} {'eval':>6}"
    )
    print("-" * 90)

    for label, agg in aggregated.items():
        ev = _evaluate_discrimination(
            None if label == "no_leak" else label, agg
        )
        print(
            f"{label:<16}"
            f" {agg['maf_z']:>7.3f}"
            f" {agg['boost_z']:>7.3f}"
            f" {agg['exhaust_z']:>9.3f}"
            f" {agg['dpf_z']:>7.3f}"
            f" {agg['svm_z']:>6.3f}"
            f" {agg['mahal_z']:>7.3f}"
            f" {agg['top_zone']:>10}"
            f" {agg['top_zone_pct']:>5.0f}%"
            f"  {ev}"
        )

    print("-" * 90)
    print()
    print("Zone distribution detail:")
    for label, agg in aggregated.items():
        counts_str = "  ".join(
            f"{z}:{c}" for z, c in sorted(agg["zone_counts"].items())
        )
        print(f"  {label:<16} {counts_str}")

    print()
    print("Expected mappings:")
    for lt, zone in _EXPECTED_ZONE.items():
        print(f"  {lt:<16} → {zone or 'no zone (healthy)'}")

    # Exit code: 0 if all FAIL-free, 1 otherwise
    any_fail = any(
        "FAIL" in _evaluate_discrimination(
            None if lbl == "no_leak" else lbl, agg
        )
        for lbl, agg in aggregated.items()
    )
    print()
    if any_fail:
        print("RESULT: FAIL — one or more leak types did not map to expected zone")
        sys.exit(1)
    else:
        print("RESULT: PASS — all leak types discriminated correctly")
        sys.exit(0)


if __name__ == "__main__":
    main()
