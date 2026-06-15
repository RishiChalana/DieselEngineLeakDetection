"""
Physics equations for diesel engine simulation.
No global state - all functions are pure with explicit noise/drift parameters.
Used by EngineSimulator for sequential data generation.
"""
import numpy as np


def calculate_fuelrate(rpm: float, load_factor: float, noise: float = 0) -> float:
    fuelrate_noise = np.random.normal(0, 2) if noise else 0
    healthy_fuelrate = 0.045 * rpm + 20 * load_factor + fuelrate_noise
    return float(np.clip(healthy_fuelrate, 5, 140))


def calculate_turbospeed(fuelrate: float, noise: float = 0) -> float:
    turbo_noise = np.random.normal(0, 500) if noise else 0
    healthy_turbospeed = 28000 + 400 * fuelrate + 0.00008 * fuelrate**2 + turbo_noise
    return float(np.clip(healthy_turbospeed, 55000, 160000))


def calculate_boostpressure(turbospeed: float, fuelrate: float, load: float, noise: float = 0, drift: float = 0) -> float:
    boost_noise = np.random.normal(0, 0.02) if noise else 0
    healthy_boostpressure = (
        0.000016 * turbospeed + 0.003 * fuelrate + 0.25 * load + boost_noise + drift
    )
    return float(np.clip(healthy_boostpressure, 0.7, 2.5))


def calculate_MAP(ambient_pressure: float, boostpressure: float, noise: float = 0) -> float:
    return float(ambient_pressure + boostpressure + (np.random.normal(0, 0.01) if noise else 0))


def calculate_MAF(MAP: float, rpm: float, IAT: float, noise: float = 0, drift: float = 0) -> float:
    maf_noise = np.random.normal(0, 8) if noise else 0
    healthy_MAF = 21 * ((MAP * rpm) / IAT) + 0.0003 * (rpm**2) + maf_noise + drift
    return float(np.clip(healthy_MAF, 80, 1000))


def calculate_coolant_temp(noise: float = 0) -> float:
    return float(np.random.normal(360, 3) if noise else 360)


def calculate_EGT(MAF: float, fuelrate: float, coolant_temp: float, noise: float = 0, drift: float = 0) -> float:
    AFR = MAF / max(fuelrate, 1e-6)
    EGT_noise = np.random.normal(0, 5) if noise else 0
    healthy_EGT = 460 + 3.8 * fuelrate + 0.35 * (coolant_temp - 360) + (20 / AFR) + EGT_noise + drift
    return float(np.clip(healthy_EGT, 470, 950))


def calculate_exhaustpressure(MAF: float, fuelrate: float, rpm: float, noise: float = 0) -> float:
    exhaust_noise = np.random.normal(0, 0.02) if noise else 0
    healthy_exhaust = 0.8 + 0.004 * MAF + 0.007 * fuelrate + 0.000003 * rpm + exhaust_noise
    return float(np.clip(healthy_exhaust, 1.0, 4.5))


def calculate_VGT(boostpressure: float, noise: float = 0) -> float:
    vgt_noise = np.random.normal(0, 2) if noise else 0
    healthy_VGT = 78 - (25 * boostpressure) + vgt_noise
    return float(np.clip(healthy_VGT, 5, 100))


def calculate_DPFdelta(MAF: float, fuelrate: float, noise: float = 0) -> float:
    dpf_noise = np.random.normal(0, 200) if noise else 0
    healthy_DPF = 3500 + 45 * MAF + 20 * fuelrate + 0.00012 * (fuelrate**2) + dpf_noise
    return float(np.clip(healthy_DPF, 4000, 70000))
