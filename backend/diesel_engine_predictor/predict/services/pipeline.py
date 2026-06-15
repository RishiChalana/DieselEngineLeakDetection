import os
import sys

# -------------------------------------------------
# Resolve Project Root — must happen before ml_model imports
# -------------------------------------------------

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(CURRENT_DIR)))
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import joblib as jb
import numpy as np
from tensorflow.keras.models import load_model

from .kalman_service import apply_kalman
from ml_model.models.mahalanobis.distance import MahalanobisDistance

ML_MODEL_PATH = os.path.join(PROJECT_ROOT, "ml_model")

AUTOENCODER_PATH = os.path.join(
    ML_MODEL_PATH,
    "models",
    "autoencoders",
    "residual_score",
    "encoded_model",
)

SVM_PATH = os.path.join(
    ML_MODEL_PATH,
    "models",
    "svm",
    "encoded",
    "svm_model.joblib",
)

# -------------------------------------------------
# Globals
# -------------------------------------------------

MAHAL_MODEL = MahalanobisDistance()

AUTOENCODER_BOOST = None
AUTOENCODER_DPF = None
AUTOENCODER_MAF = None
AUTOENCODER_EXHAUST = None

SCALAR_BOOST = None
MU_BOOST = None
STD_BOOST = None
THRESHOLD_BOOST = None

SCALAR_DPF = None
MU_DPF = None
STD_DPF = None
THRESHOLD_DPF = None

SCALAR_MAF = None
MU_MAF = None
STD_MAF = None
THRESHOLD_MAF = None

SCALAR_EXHAUST = None
MU_EXHAUST = None
STD_EXHAUST = None
THRESHOLD_EXHAUST = None

SVM_MODEL = None


# -------------------------------------------------
# Load Models
# -------------------------------------------------

def load_trained_models():
    global AUTOENCODER_BOOST, AUTOENCODER_DPF
    global AUTOENCODER_MAF, AUTOENCODER_EXHAUST
    global SCALAR_BOOST, MU_BOOST, STD_BOOST
    global SCALAR_DPF, MU_DPF, STD_DPF
    global SCALAR_MAF, MU_MAF, STD_MAF
    global SCALAR_EXHAUST, MU_EXHAUST, STD_EXHAUST
    global THRESHOLD_BOOST, THRESHOLD_DPF, THRESHOLD_MAF, THRESHOLD_EXHAUST
    global SVM_MODEL

    # -------- BOOST --------
    AUTOENCODER_BOOST = load_model(
        os.path.join(AUTOENCODER_PATH, "nn_model_boost.keras")
    )
    bundle = jb.load(os.path.join(AUTOENCODER_PATH, "nn_model_preprocessing_boost.pkl"))
    SCALAR_BOOST = bundle["scaler"]
    MU_BOOST = bundle["mean"]
    STD_BOOST = bundle["std"]
    THRESHOLD_BOOST = bundle["threshold"]

    # -------- DPF --------
    AUTOENCODER_DPF = load_model(
        os.path.join(AUTOENCODER_PATH, "nn_model_dpf.keras")
    )
    bundle = jb.load(os.path.join(AUTOENCODER_PATH, "nn_model_preprocessing_dpf.pkl"))
    SCALAR_DPF = bundle["scaler"]
    MU_DPF = bundle["mean"]
    STD_DPF = bundle["std"]
    THRESHOLD_DPF = bundle["threshold"]

    # -------- MAF --------
    AUTOENCODER_MAF = load_model(
        os.path.join(AUTOENCODER_PATH, "nn_model_maf.keras")
    )
    bundle = jb.load(os.path.join(AUTOENCODER_PATH, "nn_model_preprocessing_maf.pkl"))
    SCALAR_MAF = bundle["scaler"]
    MU_MAF = bundle["mean"]
    STD_MAF = bundle["std"]
    THRESHOLD_MAF = bundle["threshold"]

    # -------- EXHAUST --------
    AUTOENCODER_EXHAUST = load_model(
        os.path.join(AUTOENCODER_PATH, "nn_model_exhaust.keras")
    )
    bundle = jb.load(os.path.join(AUTOENCODER_PATH, "nn_model_preprocessing_exhaust.pkl"))
    SCALAR_EXHAUST = bundle["scaler"]
    MU_EXHAUST = bundle["mean"]
    STD_EXHAUST = bundle["std"]
    THRESHOLD_EXHAUST = bundle["threshold"]

    # -------- SVM --------
    SVM_MODEL = jb.load(SVM_PATH)

    print("All trained models loaded successfully.")


load_trained_models()


# -------------------------------------------------
# Autoencoder Z Score
# -------------------------------------------------

def compute_autoencoder_z(model, scaler, mu, std, threshold,values):
    X_scaled = scaler.transform(np.array(values).reshape(1, -1))
    recon = model.predict(X_scaled, verbose=0)
    residual = (recon - X_scaled) ** 2
    score = float(np.mean(residual))
    z = np.log1p(score / max(threshold, 1e-10))
    return max(z, 0.0)


# -------------------------------------------------
# SVM
# -------------------------------------------------

def apply_svm(filtered_data: dict):
    cols = SVM_MODEL["columns"]
    scaler = SVM_MODEL["scaler"]
    svm = SVM_MODEL["svm_model"]
    mean = SVM_MODEL["healthy_mean"]
    std = max(SVM_MODEL["healthy_std"], 1e-10)

    X = np.array([filtered_data[c] for c in cols]).reshape(1, -1)
    X_scaled = scaler.transform(X)
    raw = -svm.decision_function(X_scaled)[0]
    z = (raw - mean) / std

    return max(float(z), 0.0)


# -------------------------------------------------
# Mahalanobis
# -------------------------------------------------

SENSOR_COLS = [
    "rpm", "fuel_rate", "turbo_speed", "boost_pressure",
    "MAP", "IAT", "MAF", "EGT",
    "exhaust_pressure", "VGT", "DPF_delta", "ambient_pressure"
]


def apply_mahalanobis(filtered_data: dict):
    x = np.array([filtered_data[c] for c in SENSOR_COLS])
    z = MAHAL_MODEL.calculate_z_score(x)
    return max(float(z), 0.0)


# -------------------------------------------------
# Main Pipeline
# -------------------------------------------------

def process_engine_data(sensor_data: dict):

    # Step 1: Kalman
    filtered_data = apply_kalman(sensor_data)

    # Step 2: Autoencoders
    z_boost = compute_autoencoder_z(
        AUTOENCODER_BOOST,
        SCALAR_BOOST,
        MU_BOOST,
        STD_BOOST,
        THRESHOLD_BOOST,
        [filtered_data[c] for c in
         ["rpm", "fuel_rate", "turbo_speed", "exhaust_pressure", "boost_pressure"]]
    )

    z_dpf = compute_autoencoder_z(
        AUTOENCODER_DPF,
        SCALAR_DPF,
        MU_DPF,
        STD_DPF,
        THRESHOLD_DPF,
        [filtered_data[c] for c in
         ["fuel_rate", "rpm", "MAF", "boost_pressure",
          "turbo_speed", "exhaust_pressure", "DPF_delta"]]
    )

    z_maf = compute_autoencoder_z(
        AUTOENCODER_MAF,
        SCALAR_MAF,
        MU_MAF,
        STD_MAF,
        THRESHOLD_MAF,
        [filtered_data[c] for c in
         ["rpm", "fuel_rate", "MAP", "IAT", "MAF"]]
    )

    z_exhaust = compute_autoencoder_z(
        AUTOENCODER_EXHAUST,
        SCALAR_EXHAUST,
        MU_EXHAUST,
        STD_EXHAUST,
        THRESHOLD_EXHAUST,
        [filtered_data[c] for c in
         ["rpm", "fuel_rate", "MAF", "turbo_speed",
          "DPF_delta", "exhaust_pressure"]]
    )

    # Step 3: Mahalanobis
    z_mahal = apply_mahalanobis(filtered_data)

    # Step 4: SVM
    z_svm = apply_svm(filtered_data)

    # Step 5: Cumulative
    z_cumulative = np.sqrt(
        z_boost**2 +
        z_dpf**2 +
        z_maf**2 +
        z_exhaust**2 +
        0.3*z_mahal**2 +
        z_svm**2
    )
    

    return {
        "z_autoencoder_boost": z_boost,
        "z_autoencoder_dpf": z_dpf,
        "z_autoencoder_maf": z_maf,
        "z_autoencoder_exhaust": z_exhaust,
        "z_mahalanobis": z_mahal,
        "z_svm": z_svm,
        "z_cumulative": float(z_cumulative),
    }