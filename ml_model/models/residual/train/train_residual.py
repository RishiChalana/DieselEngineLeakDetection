import os
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.metrics import r2_score
from sklearn.model_selection import GridSearchCV, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import PolynomialFeatures, StandardScaler


BASE_DIR = Path(__file__).resolve().parents[4] / "ml_model"
DATA_PATH = BASE_DIR / "data_store" / "healthy_dataset.csv"
ENCODED_DIR = Path(__file__).resolve().parents[2] / "encoded"
os.makedirs(ENCODED_DIR, exist_ok=True)

R2_MIN = 0.85

MODELS = [
    {
        "name": "boost",
        "filename": "boost_model.joblib",
        "target": "boost_pressure",
        "features": ["turbo_speed", "fuel_rate"],
    },
    {
        "name": "maf",
        "filename": "maf_model.joblib",
        "target": "MAF",
        "features": ["MAP", "rpm", "IAT"],
    },
    {
        "name": "exhaust",
        "filename": "exhaust_model.joblib",
        "target": "exhaust_pressure",
        "features": ["MAF", "fuel_rate"],
    },
    {
        "name": "dpf",
        "filename": "DPF_delta.joblib",
        "target": "DPF_delta",
        "features": ["MAF", "fuel_rate"],
    },
]


def _mad_sigma(residuals: np.ndarray) -> float:
    mu = np.median(residuals)
    mad = np.median(np.abs(residuals - mu))
    return max(1.4826 * mad, 1e-8)


def train_single(model_cfg: dict, df: pd.DataFrame) -> None:
    target = model_cfg["target"]
    feats = model_cfg["features"]

    X = df[feats]
    y = df[target]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    pipe = Pipeline(
        [
            ("scaler", StandardScaler()),
            ("poly", PolynomialFeatures(degree=2, include_bias=False)),
            ("ridge", Ridge()),
        ]
    )
    param_grid = {"ridge__alpha": [0.01, 0.1, 1.0, 10.0, 50.0, 100.0]}
    grid = GridSearchCV(pipe, param_grid, cv=5, scoring="r2")
    grid.fit(X_train, y_train)
    best_alpha = grid.best_params_["ridge__alpha"]

    model = Pipeline(
        [
            ("scaler", StandardScaler()),
            ("poly", PolynomialFeatures(degree=2, include_bias=False)),
            ("ridge", Ridge(alpha=best_alpha)),
        ]
    )
    model.fit(X_train, y_train)

    y_pred_train = model.predict(X_train)
    y_pred_test = model.predict(X_test)

    r2_tr = r2_score(y_train, y_pred_train)
    r2_te = r2_score(y_test, y_pred_test)

    if r2_te < R2_MIN:
        raise RuntimeError(
            f"{model_cfg['name']} R2={r2_te:.4f} < {R2_MIN}. Check data or model."
        )

    residuals = np.asarray(y_train, dtype=float) - y_pred_train
    mu = float(np.median(residuals))
    sigma = _mad_sigma(residuals)

    pkg = {
        "model": model,
        "mu": mu,
        "sigma": sigma,
        "feature_names": feats,
        "target_name": target,
        "r2_train": r2_tr,
        "r2_test": r2_te,
    }

    out_path = ENCODED_DIR / model_cfg["filename"]
    joblib.dump(pkg, out_path)
    print(
        f"[{model_cfg['name']}] saved to {out_path.name} "
        f"(R2 train={r2_tr:.4f}, test={r2_te:.4f}, mu={mu:.6f}, sigma={sigma:.6f})"
    )


def train_all() -> None:
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Healthy dataset not found at {DATA_PATH}")
    df = pd.read_csv(DATA_PATH)
    for cfg in MODELS:
        train_single(cfg, df)


if __name__ == "__main__":
    train_all()

