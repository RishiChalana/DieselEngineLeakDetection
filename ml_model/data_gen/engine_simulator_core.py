"""
Sequential Engine Simulator with persistent state.
- Gradual RPM updates (no full random redraw each row)
- Persistent load
- Turbo speed first-order lag
- Small sensor noise and drift
- Each row represents next time step
"""
import numpy as np
from typing import Dict, Optional
from . import physics


class EngineSimulator:
    """Time-sequential diesel engine simulator with physics-driven state evolution."""

    TURBO_LAG_ALPHA = 0.15  # First-order lag: turbo_speed = (1-alpha)*prev + alpha*target
    RPM_STEP_SIGMA = 15     # Gradual rpm change per step
    DRIFT_SIGMA = 0.0001    # Small drift increment per step

    def __init__(self, seed: Optional[int] = None):
        if seed is not None:
            np.random.seed(seed)
        self.reset()

    def reset(self) -> None:
        self.mode = "healthy"
        self.time = 0
        self.leak_severity = 0.0
        self.leak_type: Optional[str] = None

        # Persistent state - initialized once
        self.rpm = float(np.clip(np.random.normal(1600, 100), 800, 2200))
        self.load_factor = float(np.random.uniform(0.5, 0.9))
        self.ambient_pressure = float(np.random.normal(1.0, 0.03))
        self.IAT = float(np.random.normal(305, 5))
        self.coolant_temp = 360.0

        # Turbo first-order lag state
        fuelrate = physics.calculate_fuelrate(self.rpm, self.load_factor, noise=1)
        self._turbo_speed = physics.calculate_turbospeed(fuelrate, noise=1)

        # Small sensor drift (persistent)
        self._drift = {"boost": 0.0, "maf": 0.0, "egt": 0.0}

    def set_healthy(self) -> None:
        self.mode = "healthy"
        self.leak_severity = 0.0
        self.leak_type = None

    def introduce_leak(self, leak_type: Optional[str] = None) -> None:
        self.mode = "leak"
        self.leak_severity = 0.02  # Start small
        self.leak_type = leak_type or np.random.choice(["precompressor", "charge_air", "exhaust"])

    def step(self) -> Dict[str, float]:
        # Gradual RPM evolution (no full random redraw)
        self.rpm += float(np.random.normal(0, self.RPM_STEP_SIGMA))
        self.rpm = float(np.clip(self.rpm, 800, 2200))

        # Load is persistent (no per-step random)
        fuelrate = physics.calculate_fuelrate(self.rpm, self.load_factor, noise=1)
        load = fuelrate / 120

        # Turbo first-order lag
        turbo_target = physics.calculate_turbospeed(fuelrate, noise=1)
        self._turbo_speed = (1 - self.TURBO_LAG_ALPHA) * self._turbo_speed + self.TURBO_LAG_ALPHA * turbo_target
        self._turbo_speed = float(np.clip(self._turbo_speed, 55000, 160000))
        turbospeed = self._turbo_speed

        # Small drift update
        for k in self._drift:
            self._drift[k] += float(np.random.normal(0, self.DRIFT_SIGMA))

        # Ambient and IAT: very slow drift, not full random
        self.ambient_pressure += float(np.random.normal(0, 0.001))
        self.ambient_pressure = float(np.clip(self.ambient_pressure, 0.9, 1.1))
        self.IAT += float(np.random.normal(0, 0.5))
        self.IAT = float(np.clip(self.IAT, 290, 320))

        # Compute downstream values with small noise
        boostpressure = physics.calculate_boostpressure(
            turbospeed, fuelrate, load, noise=1, drift=self._drift["boost"]
        )
        MAP = physics.calculate_MAP(self.ambient_pressure, boostpressure, noise=1)
        MAF = physics.calculate_MAF(MAP, self.rpm, self.IAT, noise=1, drift=self._drift["maf"])
        EGT = physics.calculate_EGT(
            MAF, fuelrate, self.coolant_temp, noise=1, drift=self._drift["egt"]
        )
        exhaust_pressure = physics.calculate_exhaustpressure(MAF, fuelrate, self.rpm, noise=1)
        VGT = physics.calculate_VGT(boostpressure, noise=1)
        DPF_delta = physics.calculate_DPFdelta(MAF, fuelrate, noise=1)

        sample = {
            "rpm": self.rpm,
            "fuel_rate": fuelrate,
            "turbo_speed": turbospeed,
            "boost_pressure": boostpressure,
            "MAP": MAP,
            "IAT": self.IAT,
            "MAF": MAF,
            "EGT": EGT,
            "exhaust_pressure": exhaust_pressure,
            "VGT": VGT,
            "DPF_delta": DPF_delta,
            "ambient_pressure": self.ambient_pressure,
        }

        if self.mode == "leak" and self.leak_type:
            sample = self._apply_leak(sample)

        self.time += 1
        return sample

    def _apply_leak(self, sample: Dict[str, float]) -> Dict[str, float]:
        s = self.leak_severity
        load = sample["fuel_rate"] / 120

        if self.leak_type == "exhaust":
            sample["exhaust_pressure"] *= (1 - s)
            sample["exhaust_pressure"] = float(np.clip(sample["exhaust_pressure"], 1.1, 3.5))
            sample["turbo_speed"] *= (1 - 0.6 * s)
            sample["turbo_speed"] = float(np.clip(sample["turbo_speed"], 60000, 140000))
            sample["boost_pressure"] = physics.calculate_boostpressure(
                sample["turbo_speed"], sample["fuel_rate"], load, noise=1, drift=self._drift["boost"]
            )
            sample["MAP"] = physics.calculate_MAP(
                sample["ambient_pressure"], sample["boost_pressure"], noise=1
            )
            sample["MAF"] = physics.calculate_MAF(
                sample["MAP"], sample["rpm"], sample["IAT"], noise=1, drift=self._drift["maf"]
            )
            sample["DPF_delta"] = physics.calculate_DPFdelta(sample["MAF"], sample["fuel_rate"], noise=1)

        elif self.leak_type == "precompressor":
            sample["MAF"] *= (1 - s)
            sample["turbo_speed"] *= (1 + 0.2 * s)
            sample["turbo_speed"] = float(np.clip(sample["turbo_speed"], 60000, 140000))
            sample["boost_pressure"] = physics.calculate_boostpressure(
                sample["turbo_speed"], sample["fuel_rate"], load, noise=1, drift=self._drift["boost"]
            )
            sample["MAP"] = physics.calculate_MAP(
                sample["ambient_pressure"], sample["boost_pressure"], noise=1
            )
            sample["exhaust_pressure"] = physics.calculate_exhaustpressure(
                sample["MAF"], sample["fuel_rate"], sample["rpm"], noise=1
            )
            sample["DPF_delta"] = physics.calculate_DPFdelta(sample["MAF"], sample["fuel_rate"], noise=1)

        elif self.leak_type == "charge_air":
            sample["turbo_speed"] *= (1 + 0.3 * s)
            sample["turbo_speed"] = float(np.clip(sample["turbo_speed"], 60000, 140000))
            sample["boost_pressure"] *= (1 - s)
            sample["boost_pressure"] = float(np.clip(sample["boost_pressure"], 0, 1.8))
            sample["MAP"] = physics.calculate_MAP(
                sample["ambient_pressure"], sample["boost_pressure"], noise=1
            )
            sample["MAF"] = physics.calculate_MAF(
                sample["MAP"], sample["rpm"], sample["IAT"], noise=1, drift=self._drift["maf"]
            )
            sample["exhaust_pressure"] = physics.calculate_exhaustpressure(
                sample["MAF"], sample["fuel_rate"], sample["rpm"], noise=1
            )
            sample["exhaust_pressure"] = float(np.clip(sample["exhaust_pressure"], 1.1, 3.5))
            sample["DPF_delta"] = physics.calculate_DPFdelta(sample["MAF"], sample["fuel_rate"], noise=1)

        # Leak severity grows gradually
        growth = 0.0003 * (1 - self.leak_severity)
        self.leak_severity = min(self.leak_severity + growth, 0.5)

        return sample
