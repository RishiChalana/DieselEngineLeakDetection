import pandas as pd
from sklearn.preprocessing import StandardScaler
from tensorflow.keras.models import Model
from tensorflow.keras.layers import Input, Dense
from tensorflow.keras.optimizers import Adam
import os
import numpy as np
import joblib as jb
from ....kalman.kalman_layer import KalmanLayer
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score, confusion_matrix


kalman=KalmanLayer()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_PATH = os.path.normpath(
    os.path.join(BASE_DIR,"..", "..", "..", "data_store", "healthy_dataset.csv")
)

df = pd.read_csv(DATA_PATH)
data=[]
for dictionary in df.to_dict(orient="records"):
    filtered_data=kalman.filter(dictionary)
    data.append(filtered_data)

df_new=pd.DataFrame(data)
df_new=df_new[ [
        "fuel_rate",
        "rpm",
        "MAF",
        "boost_pressure",
        "turbo_speed",
        "exhaust_pressure",
        "DPF_delta"
    ]]
# rpm,fuel_rate,turbo_speed,boost_pressure,MAP,IAT,MAF,EGT,exhaust_pressure,VGT,DPF_delta,ambient_pressure
X=df_new.values
sc=StandardScaler()
X_scaled=sc.fit_transform(X)
print(X_scaled)

input_dim=X_scaled.shape[1]

input_layer=Input(shape=(input_dim,))

layer_1=Dense(units=8,activation="relu")(input_layer)
layer_2=Dense(units=4,activation="relu")(layer_1)
layer_3=Dense(units=2,activation="relu")(layer_2)
layer_4=Dense(units=4,activation="relu")(layer_3)
layer_5=Dense(units=8,activation="relu")(layer_4)
output_layer=Dense(units=7,activation="linear")(layer_5)

autoencoder=Model(input_layer,output_layer)

autoencoder.compile(loss="mse",optimizer=Adam(learning_rate=0.001))

autoencoder.summary()
autoencoder.fit(
    X_scaled,
    X_scaled,
    epochs=50,
    batch_size=128,
    validation_split=0.1,
    shuffle=True
)


reconstructions = autoencoder.predict(X_scaled)
healthy_error = np.mean((X_scaled - reconstructions)**2, axis=1)
threshold = np.percentile(healthy_error, 99)


SAVE_DIR = os.path.join(BASE_DIR, "..", "residual_score", "encoded_model")
os.makedirs(SAVE_DIR, exist_ok=True)

jb.dump(
    {"scaler": sc, "threshold": threshold,"mean":healthy_error.mean(),"std":healthy_error.std()},
    os.path.join(SAVE_DIR, "nn_model_preprocessing_dpf.pkl")
)

autoencoder.save(
    os.path.join(SAVE_DIR, "nn_model_dpf.keras")
)

print(threshold)
print("Mean:", healthy_error.mean())
print("Std:", healthy_error.std())
print("95th percentile:", np.percentile(healthy_error, 95))
print("99th percentile:", np.percentile(healthy_error, 99))
print("99.5 percentile:", np.percentile(healthy_error, 99.5))

# =====================================================
# EVALUATION SECTION (ADD BELOW YOUR CURRENT CODE)
# =====================================================

# =====================================================
# EVALUATION WITHOUT DIGITAL TWIN
# =====================================================



# Use original scaled healthy data
# =====================================================
# EVALUATION USING REAL LEAKY DATA
# =====================================================

from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score, confusion_matrix

# -----------------------------------------------------
# HEALTHY DATA (already computed above)
# -----------------------------------------------------

healthy_scores = healthy_error
healthy_labels = np.zeros(len(healthy_scores))

# -----------------------------------------------------
# LEAKY DATA PROCESSING
# -----------------------------------------------------

# Load your leaky dataset here
# Example:

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_PATH = os.path.normpath(
    os.path.join(BASE_DIR,"..", "..", "..", "data_store", "leaky_dataset.csv")
)
leaky_data = pd.read_csv(DATA_PATH)
leak_filtered = []
for dictionary in leaky_data.to_dict(orient="records"):
    filtered = kalman.filter(dictionary)
    leak_filtered.append(filtered)

leak_df = pd.DataFrame(leak_filtered)

# IMPORTANT: Must match training feature order EXACTLY
leak_X = leak_df[ [
        "fuel_rate",
        "rpm",
        "MAF",
        "boost_pressure",
        "turbo_speed",
        "exhaust_pressure",
        "DPF_delta"
    ]].values

# Use SAME scaler (do NOT fit again)
leak_X_scaled = sc.transform(leak_X)

# Reconstruction
recon_anomaly = autoencoder.predict(leak_X_scaled, verbose=0)

anomaly_error = np.mean((leak_X_scaled - recon_anomaly)**2, axis=1)
anomaly_labels = np.ones(len(anomaly_error))

# -----------------------------------------------------
# COMBINE HEALTHY + LEAKY
# -----------------------------------------------------

all_scores = np.concatenate([healthy_scores, anomaly_error])
all_labels = np.concatenate([healthy_labels, anomaly_labels])

predictions = (all_scores > threshold).astype(int)

# -----------------------------------------------------
# METRICS
# -----------------------------------------------------

accuracy = accuracy_score(all_labels, predictions)
precision = precision_score(all_labels, predictions)
recall = recall_score(all_labels, predictions)
f1 = f1_score(all_labels, predictions)
roc_auc = roc_auc_score(all_labels, all_scores)
cm = confusion_matrix(all_labels, predictions)

print("\n===== EVALUATION (REAL LEAK DATA) =====")
print("Accuracy :", accuracy)
print("Precision:", precision)
print("Recall   :", recall)
print("F1 Score :", f1)
print("ROC-AUC  :", roc_auc)
print("\nConfusion Matrix:")
print(cm)