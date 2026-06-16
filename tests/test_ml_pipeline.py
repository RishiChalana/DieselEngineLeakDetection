"""
test_ml_pipeline.py — Unit tests for the ML inference pipeline.

Tests the 5-section predict() output contract, SteadyStateDetector,
and ZoneClassifier zone mapping.  All synthetic data comes from EngineSimulator.

Run:  pytest tests/test_ml_pipeline.py -v
"""
from typing import Dict, List

import pytest

from ml_model.data_gen.engine_simulator_core import EngineSimulator
from ml_model.models.model_stack import ModelStack
from ml_model.steady_state import SteadyStateDetector


class TestModelStackLoading:
    def test_health_check_reports_all_loaded(self, model_stack: ModelStack) -> None:
        result = model_stack.health_check()
        assert result["all_loaded"] is True
        assert len(result["components"]) == 7

    def test_singleton_returns_same_instance(self) -> None:
        assert ModelStack() is ModelStack()


class TestPredictOutputContract:
    _TOP_KEYS = {"steady_state", "detection", "isolation", "decision", "metadata"}
    _DECISION_KEYS = {"flag", "severity", "recommended_action", "escalate_immediately"}
    _DETECTION_KEYS = {
        "is_leak", "confidence", "z_cumulative", "subsystem_z",
        "svm_z", "mahal_z", "leak_type", "physics_score",
    }

    def test_all_top_level_keys_present(self, model_stack, healthy_sample) -> None:
        result = model_stack.predict(healthy_sample)
        assert self._TOP_KEYS.issubset(result.keys())

    def test_all_detection_keys_present(self, model_stack, healthy_sample) -> None:
        result = model_stack.predict(healthy_sample)
        assert self._DETECTION_KEYS.issubset(result["detection"].keys())

    def test_all_decision_keys_present(self, model_stack, healthy_sample) -> None:
        result = model_stack.predict(healthy_sample)
        assert self._DECISION_KEYS.issubset(result["decision"].keys())

    def test_flag_is_valid_value(self, model_stack, healthy_sample) -> None:
        result = model_stack.predict(healthy_sample)
        assert result["decision"]["flag"] in {"PASS", "WARNING", "FAIL"}

    def test_confidence_in_unit_range(self, model_stack, healthy_sample) -> None:
        c = model_stack.predict(healthy_sample)["detection"]["confidence"]
        assert 0.0 <= c <= 1.0, f"confidence={c} out of [0, 1]"

    def test_z_cumulative_non_negative(self, model_stack, healthy_sample) -> None:
        z = model_stack.predict(healthy_sample)["detection"]["z_cumulative"]
        assert z >= 0.0, f"z_cumulative={z} is negative"

    def test_all_subsystem_z_non_negative(self, model_stack, healthy_sample) -> None:
        sz = model_stack.predict(healthy_sample)["detection"]["subsystem_z"]
        for key, val in sz.items():
            assert val >= 0.0, f"subsystem_z[{key}]={val} is negative"

    def test_svm_z_and_mahal_z_non_negative(self, model_stack, healthy_sample) -> None:
        det = model_stack.predict(healthy_sample)["detection"]
        assert det["svm_z"] >= 0.0
        assert det["mahal_z"] >= 0.0

    def test_metadata_has_timestamp_and_duration(self, model_stack, healthy_sample) -> None:
        meta = model_stack.predict(healthy_sample)["metadata"]
        assert "analysis_timestamp" in meta
        assert meta["analysis_duration_ms"] > 0

    def test_isolation_empty_when_healthy_not_leaking(self, model_stack, healthy_sample) -> None:
        result = model_stack.predict(healthy_sample)
        if not result["detection"]["is_leak"]:
            zone = result["isolation"].get("detected_zone")
            assert zone in {None, "none", "unknown", ""}

    def test_leaky_sample_is_detected(self, model_stack, leaky_sample) -> None:
        det = model_stack.predict(leaky_sample)["detection"]
        assert det["is_leak"] is True, (
            f"charge_air leak at severity 0.40 not detected: "
            f"z_cumulative={det['z_cumulative']:.3f}"
        )

    def test_leaky_sample_isolation_has_zone(self, model_stack, leaky_sample) -> None:
        result = model_stack.predict(leaky_sample)
        if result["detection"]["is_leak"]:
            assert "detected_zone" in result["isolation"]
            assert result["isolation"]["detected_zone"] in {
                "zone_1", "zone_2", "zone_3", "zone_4", "multiple", "unknown",
            }

    def test_escalate_immediately_is_bool(self, model_stack, healthy_sample) -> None:
        assert isinstance(
            model_stack.predict(healthy_sample)["decision"]["escalate_immediately"], bool
        )


class TestSteadyStateDetector:
    def test_output_keys_present(self, stable_window) -> None:
        result = SteadyStateDetector().check(stable_window)
        assert {"is_steady", "confidence", "reason", "unstable_channels", "window_stats"}.issubset(
            result.keys()
        )

    def test_stable_window_is_steady(self, stable_window) -> None:
        result = SteadyStateDetector().check(stable_window)
        assert result["is_steady"] is True
        assert result["confidence"] > 0.7

    def test_transient_window_is_not_steady(self, transient_window) -> None:
        result = SteadyStateDetector().check(transient_window)
        assert result["is_steady"] is False
        assert len(result["unstable_channels"]) > 0

    def test_confidence_in_unit_range(self, stable_window) -> None:
        result = SteadyStateDetector().check(stable_window)
        assert 0.0 <= result["confidence"] <= 1.0

    def test_empty_window_returns_not_steady(self) -> None:
        result = SteadyStateDetector().check([])
        assert result["is_steady"] is False


class TestZoneClassifier:
    """Directional zone tests — charge_air and exhaust hit 100% in the diagnostic."""

    @pytest.mark.parametrize("leak_type,expected_zone", [
        ("charge_air", "zone_2"),
        ("exhaust",    "zone_3"),
    ])
    def test_zone_maps_correctly(
        self, model_stack: ModelStack, leak_type: str, expected_zone: str
    ) -> None:
        sim = EngineSimulator(seed=88)
        for _ in range(60):
            sim.step()
        sim.introduce_leak(leak_type=leak_type)
        sim.leak_severity = 0.40
        for _ in range(50):
            sim.step()

        detected_zones: List[str] = []
        for _ in range(10):
            result = model_stack.predict(sim.step())
            if result["detection"]["is_leak"]:
                detected_zones.append(result["isolation"]["detected_zone"])

        assert detected_zones, f"No leaks detected for {leak_type} at severity 0.40"
        hit_rate = detected_zones.count(expected_zone) / len(detected_zones)
        assert hit_rate >= 0.80, (
            f"{leak_type} → expected {expected_zone} ≥80%, "
            f"got {hit_rate:.0%} over {detected_zones}"
        )

    def test_healthy_produces_empty_isolation(self, model_stack, healthy_sample) -> None:
        result = model_stack.predict(healthy_sample)
        if not result["detection"]["is_leak"]:
            zone = result["isolation"].get("detected_zone")
            assert zone in {None, "none", "unknown", ""}
