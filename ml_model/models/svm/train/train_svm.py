import os
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.svm import OneClassSVM

from ml_model.kalman.kalman_layer import KalmanLayer


BASE_DIR = Path(__file__).resolve().parents[4] / "ml_model"
DATA_PATH = BASE_DIR / "data_store" / "healthy_dataset.csv"
ENCODED_DIR = BASE_DIR / "models" / "svm" / "encoded"

os.makedirs(ENCODED_DIR, exist_ok=True)


SENSOR_COLS = [
    "rpm",
    "fuel_rate",
    "turbo_speed",
    "boost_pressure",
    "MAP",
    "IAT",
    "MAF",
    "EGT",
    "exhaust_pressure",
    "VGT",
    "DPF_delta",
    "ambient_pressure",
]

def train_svm() -> None:

    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Healthy dataset not found at {DATA_PATH}")

    print("Loading healthy dataset...")
    df = pd.read_csv(DATA_PATH)

    # Keep only available sensor columns
    df = df[[c for c in SENSOR_COLS if c in df.columns]]

    print(f"Using {len(df.columns)} sensor features")

    print("Applying Kalman filtering...")
    kalman = KalmanLayer()

    filtered_rows = []

    for _, row in df.iterrows():
        filtered_row = kalman.filter(row.to_dict())
        filtered_rows.append(filtered_row)

    df_filt = pd.DataFrame(filtered_rows)

    # Ensure same column order
    df_filt = df_filt[df.columns]

    print("Scaling features...")
    X = df_filt.values

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)


    print("Training One-Class SVM...")
    ocsvm = OneClassSVM(
        kernel="rbf",
        nu=0.05,       
        gamma="scale"
    )

    ocsvm.fit(X_scaled)

    raw_scores = -ocsvm.decision_function(X_scaled)

    healthy_mean = float(np.mean(raw_scores))
    healthy_std = float(np.std(raw_scores))
    healthy_std = max(healthy_std, 1e-10)  

    print(f"Healthy mean score: {healthy_mean:.6f}")
    print(f"Healthy std score : {healthy_std:.6f}")


    pkg = {
        "scaler": scaler,
        "svm_model": ocsvm,
        "healthy_mean": healthy_mean,
        "healthy_std": healthy_std,
        "columns": list(df.columns),
    }

    out_path = ENCODED_DIR / "svm_model.joblib"
    joblib.dump(pkg, out_path)

    print(f"\n✅ SVM model saved to: {out_path}")
    print("Training complete.")


if __name__ == "__main__":
    train_svm()