import pandas as pd
import numpy as np


df = pd.read_csv("ml_model/data_store/healthy_dataset.csv")

sensors = [
    "rpm",
    "MAF",
    "boost_pressure",
    "exhaust_pressure",
    "MAP",
    "fuel_rate",
    "EGT",
    "VGT",
    "DPF_delta",
    "turbo_speed",
    "ambient_pressure",
    "IAT"
]

print("=" * 60)
print("KALMAN PARAMETER ESTIMATION FROM HEALTHY DATA")
print("=" * 60)

results = {}

for sensor in sensors:

    if sensor not in df.columns:
        continue

    signal = df[sensor].dropna()

    # First difference (velocity approx)
    first_diff = signal.diff().dropna()

    # Second difference (acceleration approx)
    second_diff = first_diff.diff().dropna()

    # Measurement Noise Variance (R)
    R = np.var(first_diff)

    # Process Noise Variance (Q)
    Q = np.var(second_diff)

    results[sensor] = {
        "Recommended_Process_Variance_Q": Q,
        "Recommended_Measurement_Variance_R": R
    }

    print(f"\nSensor: {sensor}")
    print(f"  Measurement Variance (R): {R:.6f}")
    print(f"  Process Variance (Q):     {Q:.6f}")

print("\n" + "=" * 60)
print("Use these values inside KalmanLayer.")
print("=" * 60)
