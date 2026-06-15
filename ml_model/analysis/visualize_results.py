import sys
from pathlib import Path

# --------------------------------------------------
# Add project root to path
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(PROJECT_ROOT))

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

from ml_model.kalman.kalman_layer import KalmanLayer
from backend.diesel_engine_predictor.predict.services.pipeline import process_engine_data

# --------------------------------------------------
# Plot Style
# --------------------------------------------------

plt.style.use("seaborn-v0_8")

# --------------------------------------------------
# Load datasets
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parents[1]

healthy_path = BASE_DIR / "data_store" / "healthy_dataset.csv"
leaky_path = BASE_DIR / "data_store" / "leaky_dataset.csv"

healthy_df = pd.read_csv(healthy_path)
leaky_df = pd.read_csv(leaky_path)

print("Healthy dataset:", healthy_df.shape)
print("Leaky dataset:", leaky_df.shape)

kalman = KalmanLayer()

# ==================================================
# 1️⃣ Raw vs Kalman Filtered Signal
# ==================================================

raw_maf = []
filtered_maf = []

for _, row in healthy_df.head(1000).iterrows():

    raw_maf.append(row["MAF"])

    filtered = kalman.filter(row.to_dict())
    filtered_maf.append(filtered["MAF"])

plt.figure(figsize=(10,5))

plt.plot(raw_maf, label="Raw MAF")
plt.plot(filtered_maf, label="Kalman Filtered MAF")

plt.title("Raw vs Kalman Filtered Signal")
plt.xlabel("Time Step")
plt.ylabel("MAF")
plt.legend()

plt.savefig("kalman_filter_plot.png", dpi=300)
plt.close()

# ==================================================
# 2️⃣ Subsystem Model Scores (AE + SVM)
# ==================================================

z_boost=[]
z_dpf=[]
z_maf=[]
z_exhaust=[]
z_svm=[]

for _, row in leaky_df.head(1500).iterrows():

    result = process_engine_data(row.to_dict())

    z_boost.append(result["z_autoencoder_boost"])
    z_dpf.append(result["z_autoencoder_dpf"])
    z_maf.append(result["z_autoencoder_maf"])
    z_exhaust.append(result["z_autoencoder_exhaust"])
    z_svm.append(result["z_svm"])

plt.figure(figsize=(10,5))

plt.plot(z_boost,label="Boost AE")
plt.plot(z_maf,label="MAF AE")
plt.plot(z_dpf,label="DPF AE")
plt.plot(z_exhaust,label="Exhaust AE")
plt.plot(z_svm,label="SVM")

plt.title("Subsystem Anomaly Scores")
plt.xlabel("Time Step")
plt.ylabel("Z Score")
plt.legend()

all_values = z_boost + z_maf + z_dpf + z_exhaust + z_svm
plt.ylim(0, max(all_values)*1.2)

plt.savefig("subsystem_scores.png", dpi=300)
plt.close()

# ==================================================
# 3️⃣ Fusion Score
# ==================================================

fusion_scores=[]

for _, row in leaky_df.head(1500).iterrows():

    result = process_engine_data(row.to_dict())

    fusion_scores.append(result["z_cumulative"])

plt.figure(figsize=(10,5))

plt.plot(fusion_scores,label="Fusion Score")

plt.title("Fusion Anomaly Score Over Time")
plt.xlabel("Time Step")
plt.ylabel("Fusion Score")
plt.legend()

plt.ylim(0, max(fusion_scores)*1.2)

plt.savefig("fusion_score.png", dpi=300)
plt.close()

# ==================================================
# 4️⃣ Raw → Kalman → Residual → Detection
# ==================================================

raw_maf=[]
filtered_maf=[]
residual=[]
fusion=[]

for _,row in leaky_df.head(1000).iterrows():

    raw=row["MAF"]

    filtered=kalman.filter(row.to_dict())

    result=process_engine_data(row.to_dict())

    raw_maf.append(raw)
    filtered_maf.append(filtered["MAF"])
    residual.append(abs(raw-filtered["MAF"]))
    fusion.append(result["z_cumulative"])

fig,axs=plt.subplots(4,1,figsize=(10,8),sharex=True)

axs[0].plot(raw_maf)
axs[0].set_title("Raw Sensor Signal")

axs[1].plot(filtered_maf)
axs[1].set_title("Kalman Filtered Signal")

axs[2].plot(residual)
axs[2].set_title("Residual Error")

axs[3].plot(fusion)
axs[3].set_title("Final Detection Score")

plt.xlabel("Time Step")

plt.savefig("full_detection_pipeline.png", dpi=300)
plt.close()

# ==================================================
# Done
# ==================================================

print("All plots generated successfully.")