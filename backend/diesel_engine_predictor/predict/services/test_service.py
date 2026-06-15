from user_auth.models import Engine, Sensor_Leaky_Data, Engine_Test
import numpy as np


def get_or_create_engine(model_no: str, engine_type: str | None = None):

    engine, created = Engine.objects.get_or_create(
        model_no=model_no,
        defaults={"type": engine_type or "diesel"}
    )
    return engine


def generate_next_steps(leak_detected: bool, window_samples: list):

    if not window_samples:
        return "No sufficient data collected."

    if not leak_detected:
        return "Engine operating normally. No leak detected."

    # Extract values
    boost_vals = [s.get("boost_pressure", 0) for s in window_samples]
    rpm_vals = [s.get("rpm", 0) for s in window_samples]
    fuel_vals = [s.get("fuel_rate", 0) for s in window_samples]
    z_vals = [s.get("z_cumulative", 0) for s in window_samples]

    avg_boost = np.mean(boost_vals)
    avg_rpm = np.mean(rpm_vals)
    avg_fuel = np.mean(fuel_vals)
    avg_z = np.mean(z_vals)

    # Rule-based decision tree

    if avg_boost > 1.6:
        return "Possible turbocharger leak. Inspect turbo hoses and intercooler connections."

    if avg_boost < 1.0:
        return "Boost pressure too low. Check for air intake leakage or damaged turbo."

    if avg_z > 8:
        return "Severe anomaly detected. Immediate inspection of exhaust and fuel system recommended."

    if avg_fuel > 110:
        return "Abnormal fuel consumption detected. Inspect injectors and fuel pump."

    if np.std(rpm_vals) > 100:
        return "RPM instability detected. Possible combustion or sensor irregularity."

    return "Leak pattern detected. Inspect exhaust manifold, turbo system and DPF assembly."

def save_engine_test(engine, user, window_samples, leak_detected):


    sensor_obj = Sensor_Leaky_Data.objects.create(
        rolling_window_data={"samples": window_samples},
        next_steps=generate_next_steps(leak_detected, window_samples)
    )

    Engine_Test.objects.create(
        engine=engine,
        user=user,
        sensor=sensor_obj,
        test_check="Fail" if leak_detected else "Pass"
    )