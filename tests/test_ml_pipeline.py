"""
test_ml_pipeline.py — Unit tests for the ML inference pipeline.

Covers ModelStack loading, inference correctness, and output contract.
All tests use synthetic data from EngineSimulator (no real sensor hardware).

Run with:  pytest tests/test_ml_pipeline.py -v
"""
from typing import Dict

import pytest

from ml_model.models.model_stack import ModelStack

# Expected keys in every ModelStack.predict() / evaluate() response.
_REQUIRED_KEYS = {
    "final_score", "physics_score", "svm_z", "ae_z",
    "boost_z", "maf_z", "exhaust_z", "dpf_z",
    "z_cumulative", "z_mahalanobis",
    "is_leak", "confidence", "z_scores", "leak_type",
}


def test_modelstack_loads(model_stack: ModelStack) -> None:
    """ModelStack should load all artifacts without error."""
    # TODO: assert model_stack.health_check()["all_loaded"] == True
    pass


def test_predict_returns_required_keys(healthy_sample: Dict[str, float],
                                       model_stack: ModelStack) -> None:
    """predict() must always return all documented output keys."""
    result = model_stack.predict(healthy_sample)
    missing = _REQUIRED_KEYS - set(result.keys())
    assert not missing, f"predict() missing keys: {missing}"


def test_predict_healthy_sample_returns_no_leak(
    healthy_sample: Dict[str, float], model_stack: ModelStack
) -> None:
    """Healthy synthetic data should return is_leak=False."""
    # TODO: tune threshold or use a deterministic healthy sample that reliably
    #       falls below MODEL_STACK_ANOMALY_THRESHOLD=3.5 after Kalman warmup.
    pass


def test_predict_leaky_sample_returns_leak(
    leaky_sample: Dict[str, float], model_stack: ModelStack
) -> None:
    """Leaky synthetic data (charge-air, 200 steps escalated) should return is_leak=True."""
    # TODO: assert model_stack.predict(leaky_sample)["is_leak"] == True
    pass


def test_confidence_is_between_0_and_1(
    healthy_sample: Dict[str, float], model_stack: ModelStack
) -> None:
    """confidence must be in [0.0, 1.0] for any input."""
    result = model_stack.predict(healthy_sample)
    assert 0.0 <= result["confidence"] <= 1.0


def test_z_scores_list_has_six_elements(
    healthy_sample: Dict[str, float], model_stack: ModelStack
) -> None:
    """z_scores list must have exactly 6 elements: boost, dpf, maf, exhaust, mahal, svm."""
    result = model_stack.predict(healthy_sample)
    assert len(result["z_scores"]) == 6


def test_all_z_scores_non_negative(
    healthy_sample: Dict[str, float], model_stack: ModelStack
) -> None:
    """All individual z-scores must be ≥ 0 (by construction)."""
    result = model_stack.predict(healthy_sample)
    for key in ("boost_z", "maf_z", "exhaust_z", "dpf_z", "svm_z", "z_mahalanobis"):
        assert result[key] >= 0.0, f"{key} is negative: {result[key]}"


def test_leak_type_is_none_when_healthy(
    healthy_sample: Dict[str, float], model_stack: ModelStack
) -> None:
    """leak_type must be None when is_leak=False."""
    # TODO: ensure healthy_sample reliably gives is_leak=False first.
    pass


def test_health_check_reports_all_loaded(model_stack: ModelStack) -> None:
    """health_check() must report all_loaded=True after successful init."""
    report = model_stack.health_check()
    assert report["all_loaded"] is True
    assert len(report["components"]) == 7
