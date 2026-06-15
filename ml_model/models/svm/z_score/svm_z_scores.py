import pandas as pd
import numpy as np
import joblib
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[4] / "ml_model"
DATA_HEALTHY = BASE_DIR / "data_store" / "healthy_dataset.csv"
DATA_LEAKY = BASE_DIR / "data_store" / "leaky_dataset.csv"
ENCODED_PATH = Path(__file__).resolve().parents[2] / "encoded" / "svm_model.joblib"


def load_svm():
    if not ENCODED_PATH.exists():
        raise FileNotFoundError(f"SVM model not found at {ENCODED_PATH}")
    return joblib.load(ENCODED_PATH)


def compute_svm_z(df: pd.DataFrame, pkg: dict) -> pd.Series:
    cols = pkg["columns"]
    scaler = pkg["scaler"]
    svm = pkg["svm_model"]
    mean = pkg["healthy_mean"]
    std = max(pkg["healthy_std"], 1e-10)

    X = df[[c for c in cols if c in df.columns]].values
    X_scaled = scaler.transform(X)
    raw = -svm.decision_function(X_scaled)
    z = (raw - mean) / std
    return pd.Series(np.maximum(z, 0.0), index=df.index)


def main() -> None:
    if not DATA_HEALTHY.exists() or not DATA_LEAKY.exists():
        raise FileNotFoundError("Healthy or leaky dataset not found in data_store/.")

    pkg = load_svm()
    df_h = pd.read_csv(DATA_HEALTHY)
    df_l = pd.read_csv(DATA_LEAKY)

    df_h["svm_z"] = compute_svm_z(df_h, pkg)
    df_l["svm_z"] = compute_svm_z(df_l, pkg)

    print("\n--- SVM Z-Score Comparison (Every 5000th Row) ---\n")

    total_rows = len(df_h)
    step = 2000

    for i in range(0, total_rows, step):

        print(f"Row {i}:")

        print(f"   Healthy  svm_z = {df_h.loc[i, 'svm_z']:.4f}")
        print(f"   Leaky    svm_z = {df_l.loc[i, 'svm_z']:.4f}")

        if "leak_type" in df_l.columns:
            leak_type = df_l.loc[i, "leak_type"]
            severity = df_l.loc[i, "leak_severity"]
            print(f"   Leak Type: {leak_type}, Severity: {severity:.4f}")

        print("-" * 50)


if __name__ == "__main__":
    main()

