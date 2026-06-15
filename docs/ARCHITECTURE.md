# Architecture — Diesel Engine Air Leak Detection

## 1. System Overview

The system detects air and exhaust leaks in diesel engines during test-cell development runs by streaming 12 sensor channels through a multi-model ML ensemble in real time. No additional test hardware is required beyond the sensors already present in a standard CAT test cell. The Django backend serves a REST endpoint for single-shot inference and a WebSocket endpoint for streaming detection; a Streamlit dashboard provides a standalone visual monitor that does not depend on the Django server.

---

## 2. Component Map

```
DieselEngineLeakDetection/
│
├── backend/diesel_engine_predictor/          Django ASGI application
│   ├── diesel_engine_predictor/
│   │   ├── settings.py                       Django config; loads .env
│   │   ├── urls.py                           Root URL router (user_auth + predict)
│   │   └── asgi.py                           ASGI app; HTTP via Django + WS via Channels
│   ├── predict/
│   │   ├── views.py                          POST /api/predict — single-shot inference
│   │   ├── consumer.py                       WebSocket consumer — streaming inference
│   │   ├── routing.py                        Maps ws/engine/ → EngineConsumer
│   │   └── services/
│   │       ├── pipeline.py                   Core inference entry point: Kalman → AE → SVM → Mahal → fusion
│   │       ├── kalman_service.py             Thin wrapper: delegates to ml_model KalmanLayer
│   │       └── test_service.py               ORM helpers: get_or_create_engine, save_engine_test
│   └── user_auth/
│       ├── models.py                         User (AbstractUser + role), Engine, Sensor_Leaky_Data, Engine_Test
│       ├── views.py                          Signup, Login, Logout, Delete_Account
│       ├── serializers.py                    DRF serializers for all four models
│       └── urls.py                           /user_auth/signup|login|logout|delete_account/
│
├── ml_model/
│   ├── data_gen/
│   │   ├── physics.py                        10 pure physics equations (no state)
│   │   ├── engine_simulator_core.py          Stateful sequential simulator; 3 leak types
│   │   ├── healthy_data_gen.py               Generates healthy_dataset.csv (20 000 rows)
│   │   └── leaky_data_gen.py                 Generates leaky_dataset.csv (20 000 rows)
│   ├── data_store/
│   │   ├── healthy_dataset.csv               20 000 × 12; healthy engine time series
│   │   └── leaky_dataset.csv                 20 000 × 12; leaky engine time series
│   ├── kalman/
│   │   ├── kalman_filter.py                  2D state-space (position + velocity) per channel
│   │   ├── kalman_layer.py                   12 independent KalmanFilter2D instances; .filter(dict)
│   │   └── kalman_tuning.py                  Offline script: estimates Q and R from healthy CSV
│   └── models/
│       ├── model_stack.py                    Singleton: loads all artifacts, exposes predict() + evaluate()
│       ├── autoencoders/
│       │   ├── train/{nn_model_boost,dpf,maf,exhaust}.py  Training scripts (run once)
│       │   └── residual_score/encoded_model/ Saved .keras + preprocessing .pkl bundles
│       ├── svm/
│       │   ├── train/train_svm.py            Trains OneClassSVM; saves svm_model.joblib
│       │   └── encoded/svm_model.joblib      Trained SVM + scaler + calibration stats
│       ├── mahalanobis/
│       │   ├── train_mahal.py                Fits covariance on healthy Kalman-filtered data
│       │   ├── distance.py                   MahalanobisDistance class (.calculate_z_score)
│       │   └── encoded/mahal_model.pkl       Saved mean, inv_cov, scaler, k
│       └── residual/                         Legacy polynomial residual models (not in main pipeline)
│
├── engine_simulator/
│   ├── app.py                                Streamlit dashboard: EngineSimulator → Kalman → ModelStack
│   └── digital_twin.py                       Re-export of EngineSimulator for backward compatibility
│
├── config/
│   └── constants.py                          All project-wide constants; tuning point for thresholds
│
├── tests/
│   ├── conftest.py                           Session-scoped fixtures: model_stack, healthy_sample, leaky_sample
│   ├── test_ml_pipeline.py                   ModelStack unit tests
│   ├── test_api.py                           REST endpoint integration tests
│   └── test_websocket.py                     WebSocket consumer integration tests
│
├── docs/                                     This documentation
├── engine_calibration.pkl                    Stability limits + cumulative z-score calibration (backend root)
├── requirements.txt                          Python dependencies
└── CLAUDE.md                                 AI session context file (read first)
```

---

## 3. Data Flow Diagram

```
┌─────────────────────────────────────────────────────────┐
│  Diesel Engine Test Cell — 12 Sensor Channels           │
│  rpm  fuel_rate  turbo_speed  boost_pressure  MAP       │
│  IAT  MAF  EGT  exhaust_pressure  VGT  DPF_delta        │
│  ambient_pressure                                        │
└───────────────────────┬─────────────────────────────────┘
                        │  raw float values (one sample per tick)
                        ▼
              ┌──────────────────┐
              │  KalmanLayer     │  12 independent 2D filters
              │  (kalman_layer)  │  removes measurement noise
              └────────┬─────────┘
                       │  smoothed sensor values
           ┌───────────┼────────────────────────┐
           ▼           ▼                        ▼
   ┌──────────────┐ ┌──────────────┐    ┌───────────────────┐
   │ Autoencoder  │ │ Autoencoder  │    │  One-Class SVM    │
   │   (boost)    │ │   (dpf)      │    │  (all 12 channels)│
   │   5 inputs   │ │   7 inputs   │    │  kernel=rbf       │
   └──────┬───────┘ └──────┬───────┘    └────────┬──────────┘
          │                │                     │
   ┌──────────────┐ ┌──────────────┐    ┌────────────────────┐
   │ Autoencoder  │ │ Autoencoder  │    │  Mahalanobis Dist. │
   │   (maf)      │ │  (exhaust)   │    │  (all 12 channels) │
   │   5 inputs   │ │   6 inputs   │    │  learned covariance│
   └──────┬───────┘ └──────┬───────┘    └────────┬───────────┘
          │                │                     │
          └────────────────┴──────────┬──────────┘
                                      │  6 independent z-scores
                                      ▼
                         ┌────────────────────────┐
                         │  Weighted L2 Fusion     │
                         │  z = √(z_boost² + z_dpf²│
                         │    + z_maf² + z_exhaust²│
                         │    + 0.3·z_mahal²       │
                         │    + z_svm²)            │
                         └───────────┬────────────┘
                                     │  z_cumulative (float)
                    ┌────────────────┴─────────────────────┐
                    │                                       │
                    ▼                                       ▼
       ┌────────────────────────┐           ┌──────────────────────────┐
       │  WebSocket Consumer    │           │  REST POST /api/predict  │
       │  7-sample window vote  │           │  immediate response       │
       │  2-window confirmation │           └──────────────────────────┘
       │  → test_complete msg   │
       └────────────────────────┘
```

---

## 4. ML Pipeline in Detail

### 4a. Kalman Filter

**What it does:** Smooths each of the 12 sensor channels independently using a 2D state-space model (state = [position, velocity]).

**Why:** Test-cell sensor readings carry Gaussian measurement noise and step-change transients. Raw signals cause spurious reconstruction errors in the autoencoders. Kalman smoothing suppresses noise while preserving real anomaly signatures (leaks cause sustained, gradual shifts, not single-sample spikes).

**Parameters (data-driven):**
- Process noise Q = Var(second difference of healthy signal) × 0.01
- Measurement noise R = Var(first difference of healthy signal) × 0.05
- Multipliers (0.01 and 0.05) tune the filter to trust measurements moderately but not fully.
- Parameters were estimated from healthy_dataset.csv using `ml_model/kalman/kalman_tuning.py`.

**Channels:** All 12 — rpm, fuel_rate, turbo_speed, boost_pressure, MAP, IAT, MAF, EGT, exhaust_pressure, VGT, DPF_delta, ambient_pressure.

---

### 4b. Four Autoencoders (Reconstruction-Based Anomaly Scoring)

Each autoencoder is trained exclusively on healthy data. An anomaly is detected when the reconstruction error on new data significantly exceeds what was seen during training (measured as a z-score relative to the 99th-percentile healthy error threshold).

Architecture for all four: Input → Dense(8, relu) → Dense(4, relu) → Dense(2, relu) [bottleneck] → Dense(4, relu) → Dense(8, relu) → Output (linear).

| Name | Input channels | Input dim |
|------|---------------|-----------|
| **boost** | rpm, fuel_rate, turbo_speed, exhaust_pressure, boost_pressure | 5 |
| **dpf** | fuel_rate, rpm, MAF, boost_pressure, turbo_speed, exhaust_pressure, DPF_delta | 7 |
| **maf** | rpm, fuel_rate, MAP, IAT, MAF | 5 |
| **exhaust** | rpm, fuel_rate, MAF, turbo_speed, DPF_delta, exhaust_pressure | 6 |

> **Known discrepancy:** `nn_model_maf.py` was trained on `[rpm, fuel_rate, MAP, MAF, turbo_speed]` but `pipeline.py` and `model_stack.py` infer with `[rpm, fuel_rate, MAP, IAT, MAF]`. The 5th feature differs (turbo_speed vs IAT). The scaler inside the .pkl file was fit on the training feature set — passing IAT where turbo_speed is expected produces subtly incorrect scaling. This should be fixed by retraining the MAF autoencoder with the inference feature set.

**Training:** 50 epochs, batch=128, validation_split=0.1, Adam(lr=0.001), MSE loss.

**Threshold:** 99th percentile of reconstruction error on the full healthy training set.

**Z-score formula:** `z = log1p(reconstruction_error / threshold)` — log-compresses large errors; clipped at 0.

---

### 4c. Preprocessing .pkl Bundles

Each autoencoder has a companion `.pkl` file containing:
- `"scaler"`: fitted `sklearn.preprocessing.StandardScaler` for that model's feature subset.
- `"threshold"`: 99th-percentile reconstruction error on healthy data (float).
- `"mean"`: mean reconstruction error on healthy training data.
- `"std"`: std of reconstruction error on healthy training data.

The scaler and threshold are the critical runtime artifacts. `mean` and `std` are for diagnostics only; not used in inference.

---

### 4d. One-Class SVM

- **Input:** All 12 Kalman-filtered sensor channels (scaled by the SVM's own StandardScaler).
- **Kernel:** RBF (`gamma="scale"`).
- **Nu:** 0.05 — assumes 5% of healthy training samples may appear as outliers (contamination assumption).
- **Training data:** 20,000 healthy samples from healthy_dataset.csv after Kalman filtering.
- **Output:** `decision_function` output negated and normalized to a z-score: `(−d.f. − healthy_mean) / healthy_std`. Values > 0 indicate out-of-distribution.

---

### 4e. Mahalanobis Distance

- **Fitted on:** Healthy training data after Kalman filtering and StandardScaler normalization (all 12 channels).
- **Stored:** Mean vector μ (12D), inverse covariance matrix Σ⁻¹ (12×12, computed via `numpy.linalg.pinv` to handle collinear features).
- **Z-score:** `(d² − k) / √(2k)` where d² is the squared Mahalanobis distance and k=12 (degrees of freedom under chi-squared approximation).
- **Interpretation:** Captures multivariate correlations between sensor channels. A single sensor anomaly is weak signal; when multiple correlated channels deviate simultaneously (as in a real leak), the Mahalanobis distance amplifies this.

---

### 4f. Weighted L2 Fusion

```
z_cumulative = √(z_boost² + z_dpf² + z_maf² + z_exhaust² + 0.3·z_mahal² + z_svm²)
```

The Mahalanobis component is down-weighted to 0.3 (vs 1.0 for each of the other five) because Mahalanobis distance is more sensitive to healthy-data distributional shift and produces higher background z-scores than the autoencoder or SVM signals. The weight was chosen empirically during calibration.

**Threshold (consumer):** 6.3156 (mean + 3σ of leaky cumulative scores; from engine_calibration.pkl).
**Threshold (ModelStack):** 3.5 (more sensitive; for live Streamlit display).

---

## 5. Django App Breakdown

| App | Responsibility |
|-----|---------------|
| `predict` | ML inference: REST endpoint (`views.py`), WebSocket consumer (`consumer.py`), pipeline wrapper (`services/pipeline.py`), Kalman service, test persistence service. |
| `user_auth` | Authentication: custom User model with `role` field (viewer/tester/admin), Engine model, test result models, DRF serializers, token auth views. |

Django Channels handles the ASGI layer. The `CHANNEL_LAYERS` setting uses `InMemoryChannelLayer` for development (no Redis dependency).

---

## 6. WebSocket Protocol

### Connection
URL: `ws://host/ws/engine/`  
Auth: `TokenAuthentication` via `AuthMiddlewareStack`. Anonymous connections are immediately closed.

### Client → Server Message Types

**Message 1 (required): Engine registration**
```json
{ "model_no": "CAT-3412-001", "engine_type": "diesel" }
```

**Messages 2…N: Sensor samples**
```json
{
  "rpm": 1600.0, "fuel_rate": 75.0, "turbo_speed": 90000.0,
  "boost_pressure": 1.2, "MAP": 2.2, "IAT": 305.0,
  "MAF": 500.0, "EGT": 650.0, "exhaust_pressure": 2.5,
  "VGT": 50.0, "DPF_delta": 20000.0, "ambient_pressure": 1.0
}
```

### Server → Client Message Types

| `type` | Sent when | Key fields |
|--------|-----------|-----------|
| `engine_registered` | After valid model_no received | `model_no`, `engine_type` |
| `error` | Invalid first message | `message` |
| `buffering` | Stability buffer not yet full | `buffered`, `required` |
| `unstable` | Engine not at steady state | `message` |
| `sample_result` | After each stable inference | `status` (leak/normal), `confidence`, `z_scores` dict, `window_index` |
| `window_result` | After every 7 samples | `window_index`, `window_leak` (bool), `anomaly_count`, `confirmed_windows`, `leaky_samples_last_window` |
| `test_complete` | Leak confirmed or timeout | `leak_detected` (bool), `windows_evaluated`, `confirmed_anomaly_windows` |

---

## 7. REST API

Full documentation: see `docs/API_REFERENCE.md`.

| Method | URL | Auth | Purpose |
|--------|-----|------|---------|
| POST | `/user_auth/signup/` | No | Register new user; returns token |
| POST | `/user_auth/login/` | No | Authenticate; returns token |
| POST | `/user_auth/logout/` | Token | Invalidate current token |
| DELETE | `/user_auth/delete_account/` | Token | Delete user and token |
| POST | `/api/predict` | Token | Single-shot inference; returns full z-score dict |

---

## 8. Database Schema

### User (extends AbstractUser)
| Field | Type | Notes |
|-------|------|-------|
| id | BigAutoField | PK |
| username | CharField | Unique |
| email | EmailField | |
| password | CharField | bcrypt-hashed |
| role | CharField | viewer / tester / admin |
| history | JSONField | Stores test history (currently unpopulated) |
| last_login_time | DateTimeField | Updated on login |

### Engine
| Field | Type | Notes |
|-------|------|-------|
| EID | AutoField | PK |
| model_no | CharField(100) | Unique |
| type | CharField(20) | diesel / petrol |
| created_at | DateTimeField | auto |
| photo | ImageField | optional |

### Sensor_Leaky_Data
| Field | Type | Notes |
|-------|------|-------|
| SID | AutoField | PK |
| rolling_window_data | JSONField | `{"samples": [...]}` — the window that triggered the leak call |
| next_steps | TextField | Rule-based technician guidance from `generate_next_steps()` |

### Engine_Test
| Field | Type | Notes |
|-------|------|-------|
| id | BigAutoField | PK |
| engine | FK → Engine | CASCADE |
| user | FK → User | CASCADE |
| sensor | FK → Sensor_Leaky_Data | CASCADE |
| test_check | CharField | Pass / Fail |
| checked_at | DateTimeField | auto |

---

## 9. Known Limitations

1. **MAF autoencoder feature mismatch:** Trained on `[rpm, fuel_rate, MAP, MAF, turbo_speed]` but served with `[rpm, fuel_rate, MAP, IAT, MAF]`. The scaler treats position 5 as `turbo_speed` but receives `IAT` at inference time. This does not crash (both channels are in-range floats) but produces incorrect anomaly scores for the MAF subsystem.

2. **Three different anomaly thresholds:** consumer.py uses 6.3156 (from calibration pkl), ModelStack uses 3.5, and the Streamlit app uses 3.0. These are not aligned and produce different `is_leak` verdicts for the same sample.

3. **In-memory channel layer:** The current `CHANNEL_LAYERS` config uses `InMemoryChannelLayer`, which does not support multi-worker deployments. Replacing with Redis is required for production.

4. **No HTTPS/WSS enforcement:** `ALLOWED_HOSTS = []` and `ssl_require` removed. Production deployment needs proper SSL termination.

5. **User history field unpopulated:** The `history` JSONField on the User model is never written to. The original design intended to log test results per user there, but this logic was not implemented.

6. **Synthetic training data only:** All 40,000 training samples come from the physics-based digital twin. Models have not been validated on real test-cell sensor data.

7. **No frontend:** The `frontend/` directory contains only a `.gitkeep`. The only UI is the Streamlit dashboard, which does not communicate with the Django backend.
