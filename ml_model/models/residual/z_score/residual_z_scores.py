import pandas as pd
import joblib
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[4] / "ml_model"
DATA_HEALTHY = BASE_DIR / "data_store" / "healthy_dataset.csv"
DATA_LEAKY = BASE_DIR / "data_store" / "leaky_dataset.csv"
ENCODED_DIR = Path(__file__).resolve().parents[2] / "encoded"

MODELS = {
    "boost_z": ("boost_model.joblib", "boost_pressure", ["turbo_speed", "fuel_rate"]),
    "maf_z": ("maf_model.joblib", "MAF", ["MAP", "rpm", "IAT"]),
    "exhaust_z": ("exhaust_model.joblib", "exhaust_pressure", ["MAF", "fuel_rate"]),
    "dpf_z": ("DPF_delta.joblib", "DPF_delta", ["MAF", "fuel_rate"]),
}


def _load_pkg(filename: str):
    p = ENCODED_DIR / filename
    if not p.exists():
        raise FileNotFoundError(f"Model not found: {p}")
    return joblib.load(p)


def compute_z_scores(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col_name, (fname, target, feats) in MODELS.items():
        pkg = _load_pkg(fname)
        model = pkg["model"]
        mu = pkg["mu"]
        sigma = max(pkg["sigma"], 1e-10)
        X = out[feats]
        y = out[target]
        y_pred = model.predict(X)
        residual = y.values - y_pred
        z = (residual - mu) / sigma
        out[col_name] = abs(z)
    out["physics_score"] = out[["boost_z", "maf_z", "exhaust_z", "dpf_z"]].max(axis=1)
    return out


def main() -> None:
    if not DATA_HEALTHY.exists() or not DATA_LEAKY.exists():
        raise FileNotFoundError("Healthy or leaky dataset not found in data_store/.")

    df_h = pd.read_csv(DATA_HEALTHY)
    df_l = pd.read_csv(DATA_LEAKY)

    df_h = compute_z_scores(df_h)
    df_l = compute_z_scores(df_l)

    print("\n--- Physics Residual Z-Score Comparison (Every 5000th Row) ---\n")

    total_rows = len(df_h)
    step = 2000

    for i in range(0, total_rows, step):

        print(f"Row {i}:")

        print(f"   Healthy:")
        print(f"      boost_z   = {df_h.loc[i, 'boost_z']:.4f}")
        print(f"      maf_z     = {df_h.loc[i, 'maf_z']:.4f}")
        print(f"      exhaust_z = {df_h.loc[i, 'exhaust_z']:.4f}")
        print(f"      dpf_z     = {df_h.loc[i, 'dpf_z']:.4f}")
        print(f"      physics_score = {df_h.loc[i, 'physics_score']:.4f}")

        print(f"\n   Leaky:")
        print(f"      boost_z   = {df_l.loc[i, 'boost_z']:.4f}")
        print(f"      maf_z     = {df_l.loc[i, 'maf_z']:.4f}")
        print(f"      exhaust_z = {df_l.loc[i, 'exhaust_z']:.4f}")
        print(f"      dpf_z     = {df_l.loc[i, 'dpf_z']:.4f}")
        print(f"      physics_score = {df_l.loc[i, 'physics_score']:.4f}")

        if "leak_type" in df_l.columns:
            leak_type = df_l.loc[i, "leak_type"]
            severity = df_l.loc[i, "leak_severity"]
            print(f"      Leak Type: {leak_type}, Severity: {severity:.4f}")

        print("-" * 60)


if __name__ == "__main__":
    main()

