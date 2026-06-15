import numpy as np
import pandas as pd
import joblib
from pathlib import Path
from sklearn.preprocessing import StandardScaler
from ...kalman.kalman_layer import KalmanLayer


def train_mahalanobis():

    # -------- Paths --------
    base_dir = Path(__file__).resolve().parents[2]  # ml_model
    data_path = base_dir / "data_store" / "healthy_dataset.csv"
    save_path = base_dir / "models" / "mahalanobis" / "encoded" / "mahal_model.pkl"
    save_path.parent.mkdir(parents=True, exist_ok=True)

    # -------- Load Data --------
    df = pd.read_csv(data_path)

    kalman = KalmanLayer()
    data = []

    for row in df.to_dict(orient="records"):
        filtered = kalman.filter(row)
        data.append(filtered)

    df_new = pd.DataFrame(data)

    # -------- Scaling --------
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(df_new.values)

    # -------- Statistics --------
    mu = np.mean(X_scaled, axis=0)
    covariance = np.cov(X_scaled, rowvar=False)
    inv_cov = np.linalg.pinv(covariance)

    k = X_scaled.shape[1]

    # -------- Save --------
    joblib.dump({
        "scaler": scaler,
        "mean": mu,
        "inv_cov": inv_cov,
        "k": k
    }, save_path)

    print("Mahalanobis model saved successfully.")
    print("Feature dimension (k):", k)


if __name__ == "__main__":
    train_mahalanobis()