# 🔧 Diesel Engine Air Leak Detection

A production-grade ML-based anomaly detection system for diesel engine air leaks using deep learning autoencoders, statistical methods, and real-time WebSocket inference.

## 📋 Table of Contents

- [Overview](#overview)
- [Tech Stack](#tech-stack)
- [Installation & Setup](#installation--setup)
- [How to Run](#how-to-run)
- [Project Structure](#project-structure)
- [Main Workflow & Pipeline](#main-workflow--pipeline)
- [Database Design](#database-design)
- [API Endpoints](#api-endpoints)
- [Features](#features)

---

## 🎯 Overview

**Diesel Engine Air Leak Detection** is a comprehensive anomaly detection platform that identifies air leaks in diesel engine systems using a multi-model fusion approach. The system processes real-time sensor data from 12 engine parameters through multiple ML pipelines:

- **Deep autoencoders** (reconstruction-based anomaly scoring)
- **One-Class SVM** (distribution-based outlier detection)
- **Mahalanobis distance** (statistical distance metrics)
- **Kalman filtering** (signal smoothing across 12 sensor channels)

Real-time detection happens via WebSocket with rolling-window confirmation (2-window validation) to minimize false positives.

### Key Use Cases
- ✅ Predictive maintenance for diesel engine fleets
- ✅ Early detection of air intake system failures
- ✅ Automated health monitoring dashboards
- ✅ Real-time alerting for critical anomalies

---

## 🛠 Tech Stack

### Backend & ML Framework
- **Django 6.0** - Web framework & ORM
- **Django REST Framework** - API development
- **Django Channels** - WebSocket/ASGI for real-time inference
- **TensorFlow/Keras** - Deep learning (autoencoders)
- **scikit-learn** - Classical ML (SVM, Mahalanobis)

### Data & Processing
- **NumPy** - Numerical computing
- **Pandas** - Data manipulation
- **Kalman Filters** (custom implementation) - Signal filtering

### Visualization & Monitoring
- **Streamlit** - Real-time dashboard
- **Plotly** - Interactive charts

### Utilities
- **joblib** - Model serialization
- **python-dotenv** - Environment management
- **dj-database-url** - Database URL parsing
- **gunicorn** - Production WSGI server
- **daphne** - WebSocket ASGI server

---

## 📦 Installation & Setup

### Prerequisites
- Python 3.8+
- pip or conda
- Virtual environment (recommended)

### Step 1: Clone the Repository

```bash
git clone https://github.com/[YOUR_USERNAME]/DieselEngineLeakDetection.git
cd DieselEngineLeakDetection
```

### Step 2: Create a Virtual Environment

```bash
# Using venv
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Or using conda
conda create -n diesel-leak python=3.9
conda activate diesel-leak
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Environment Configuration

Create a `.env` file in the `backend/diesel_engine_predictor/` directory:

```env
SECRET_KEY=your-secret-key-here-change-in-production
DEBUG=True
DATABASE_URL=sqlite:///db.sqlite3
ALLOWED_HOSTS=localhost,127.0.0.1
```

For production, use a secure secret key and external database.

### Step 5: Database Migrations

```bash
cd backend/diesel_engine_predictor
python manage.py migrate
python manage.py createsuperuser  # Create admin user
```

---

## ▶️ How to Run

### Generate Training Data

```bash
# Generate 20K healthy engine samples
python -m ml_model.data_gen.healthy_data_gen

# Generate 20K leaky engine samples (with 3 leak types)
python -m ml_model.data_gen.leaky_data_gen
```

### Train ML Models

```bash
# Train One-Class SVM on 12 sensor channels
python -m ml_model.models.svm.train.train_svm

# Train 4 subsystem-specific autoencoders
python -m ml_model.models.autoencoders.train.nn_model_boost
python -m ml_model.models.autoencoders.train.nn_model_dpf
python -m ml_model.models.autoencoders.train.nn_model_maf
python -m ml_model.models.autoencoders.train.nn_model_exhaust

# Train Mahalanobis distance model
python -m ml_model.models.mahalanobis.train_mahal

# Compute z-scores on test datasets
python -m ml_model.models.svm.z_score.svm_z_scores
```

### Run the Backend API Server

```bash
cd backend/diesel_engine_predictor

# Development (HTTP only)
python manage.py runserver

# Production (with WebSocket support via ASGI)
daphne -b 0.0.0.0 -p 8000 diesel_engine_predictor.asgi:application
```

API Server runs at: `http://localhost:8000`

### Run the Real-Time Monitoring Dashboard

```bash
# From project root
streamlit run engine_simulator/app.py
```

Dashboard opens at: `http://localhost:8501`

---

## 📁 Project Structure

```
DieselEngineLeakDetection/
│
├── backend/                              # Django REST API backend
│   └── diesel_engine_predictor/
│       ├── manage.py                     # Django CLI
│       ├── db.sqlite3                    # Development database
│       ├── diesel_engine_predictor/      # Project settings
│       │   ├── settings.py              # Django configuration
│       │   ├── urls.py                  # URL routing
│       │   ├── asgi.py                  # ASGI config (WebSocket)
│       │   └── wsgi.py                  # WSGI config
│       ├── predict/                      # Core prediction app
│       │   ├── views.py                 # REST endpoints
│       │   ├── consumers.py             # WebSocket consumer
│       │   ├── services/
│       │   │   ├── pipeline.py          # Inference pipeline (ensemble)
│       │   │   └── kalman_service.py    # Kalman filtering service
│       │   ├── routing.py               # WebSocket routing
│       │   ├── models.py                # DB models
│       │   └── urls.py                  # App URL patterns
│       └── user_auth/                    # Authentication & authorization
│           ├── views.py                 # Login, signup, logout
│           ├── models.py                # User, Engine, Sensor models
│           ├── serializers.py           # DRF serializers
│           └── urls.py                  # Auth URL patterns
│
├── ml_model/                             # ML training & evaluation
│   ├── data_gen/                         # Data generation
│   │   ├── engine_simulator_core.py     # Physics-based engine simulator
│   │   ├── healthy_data_gen.py          # Generate 20K healthy samples
│   │   ├── leaky_data_gen.py            # Generate 20K leaky samples
│   │   └── physics.py                   # 10 physics equations
│   ├── data_store/                       # Datasets (CSV)
│   │   ├── healthy_dataset.csv          # 20K × 12 features
│   │   └── leaky_dataset.csv            # 20K × 12 features
│   ├── kalman/                           # Kalman filter implementations
│   │   ├── kalman_filter.py             # 2D Kalman filter class
│   │   ├── kalman_layer.py              # 12-channel Kalman layer
│   │   └── kalman_tuning.py             # Parameter estimation
│   ├── models/                           # Trained ML models
│   │   ├── residual/                     # Legacy residual models (not used in main pipeline)
│   │   │   ├── train/
│   │   │   │   └── train_residual.py    # Train 4 residual models
│   │   │   └── encoded/                 # Saved .joblib models
│   │   ├── svm/                          # One-Class SVM
│   │   │   ├── train/
│   │   │   │   └── train_svm.py         # Train SVM
│   │   │   ├── encoded/
│   │   │   │   └── svm_model.joblib     # Trained SVM
│   │   │   └── z_score/
│   │   │       └── svm_z_scores.py      # Compute anomaly scores
│   │   ├── autoencoders/                 # Deep autoencoders (reconstruction)
│   │   │   ├── train/
│   │   │   │   ├── nn_model_boost.py    # Boost subsystem AE (5 input features)
│   │   │   │   ├── nn_model_dpf.py      # DPF subsystem AE (7 input features)
│   │   │   │   ├── nn_model_maf.py      # MAF subsystem AE (5 input features)
│   │   │   │   └── nn_model_exhaust.py  # Exhaust subsystem AE (6 input features)
│   │   │   └── residual_score/
│   │   │       └── encoded_model/       # Saved .keras models
│   │   ├── mahalanobis/                  # Mahalanobis distance
│   │   │   ├── train_mahal.py           # Train Mahalanobis model
│   │   │   ├── distance.py              # Mahalanobis distance computation
│   │   │   └── encoded/                 # Saved model
│   │   └── __init__.py
│   └── analysis/                         # Visualizations & analysis
│       └── visualize_results.py         # Generate analysis plots
│
├── engine_simulator/                     # Real-time monitoring dashboard
│   ├── app.py                            # Streamlit dashboard (~280 lines)
│   └── digital_twin.py                   # Backward compatibility
│
├── requirements.txt                      # Python dependencies
└── README.md                             # This file
```

---

## 🔄 Main Workflow & Pipeline

### End-to-End Data Flow

```
Diesel Engine Sensors (12 channels)
        ↓
[Real-time Sensor Input: 12 parameters]
        ↓
Kalman Filtering Layer (12 independent 2D filters)
        ↓
[Smoothed sensor signals]
        ↓
Ensemble Inference Pipeline:
        ├─→ 4 Autoencoders (subsystem-specific)
    │   └─→ 4 reconstruction error z-scores
    ├─→ One-Class SVM (12 channels)
    │   └─→ 1 SVM anomaly z-score
    └─→ Mahalanobis Distance (12D covariance matrix)
        └─→ 1 Mahalanobis z-score
        ↓
Weighted L2 Fusion Scoring:
z_cumulative = √(z_ae_boost² + z_ae_dpf² + z_ae_maf² + z_ae_exhaust² + 0.3·z_mahal² + z_svm²)
        ↓
[Fused anomaly score: 0 = healthy, >3.5 = anomaly]
        ↓
Rolling Window Detector (7-sample window):
    - Majority voting (≥4/7 anomalous)
    - 2-window confirmation (prevent false positives)
        ↓
[Alert Decision: LEAK_CONFIRMED or HEALTHY]
        ↓
WebSocket Real-time Response to Client
```

### Data Generation Pipeline

Uses a **physics-driven digital twin** with:
- **Persistent engine state** (RPM gradually evolves, not random)
- **Turbo lag** (first-order dynamical response)
- **3 leak types**: precompressor, charge_air, exhaust
- **Leak severity escalation** (grows gradually over time)

### Model Training Workflow

1. **Healthy Data**: 20,000 sequential samples from simulator
2. **Leaky Data**: 20,000 samples with leak injections
3. **Autoencoders**: 50 epochs, batch=128, 99th-percentile threshold
4. **SVM**: 5% contamination assumption (nu=0.05)
5. **Mahalanobis**: Covariance-based distance model on healthy distribution
6. **Kalman Parameters**: Estimated from healthy data variance (auto-tuned)

---

## 🗄️ Database Design

### Models (Django ORM)

#### 1. **User** (extends Django AbstractUser)
```python
- id (auto-generated)
- username (unique)
- email
- password (hashed)
- role (Viewer, Tester, Admin)
- history (JSON field - stores test history)
- last_login_time (DateTime)
```

#### 2. **Engine**
```python
- EID (primary key)
- model_no (unique string)
- type (engine type/variant)
- created_at (auto timestamp)
- photo (optional image)
```

#### 3. **Sensor_Leaky_Data**
```python
- SID (primary key)
- rolling_window_data (JSON - anomalous sensor readings)
- next_steps (recommendations as text)
```

#### 4. **Engine_Test**
```python
- id (primary key)
- engine (ForeignKey → Engine)
- user (ForeignKey → User)
- sensor (ForeignKey → Sensor_Leaky_Data)
- test_check (Pass/Fail)
- checked_at (auto timestamp)
```

### Relationships

```
User ←1:N→ Engine_Test
Engine ←1:N→ Engine_Test
Sensor_Leaky_Data ←1:N→ Engine_Test
```

---

## 📡 API Endpoints

### Authentication Endpoints

| Endpoint | Method | Purpose | Auth Required |
|----------|--------|---------|---|
| `/user_auth/signup/` | POST | Register new user | ❌ No |
| `/user_auth/login/` | POST | Generate auth token | ❌ No |
| `/user_auth/logout/` | POST | Invalidate token | ✅ Yes |
| `/user_auth/delete_account/` | DELETE | Delete user account | ✅ Yes |

### Prediction Endpoints

| Endpoint | Method | Purpose | Auth Required |
|----------|--------|---------|---|
| `/api/predict` | POST | One-shot inference (single sensor reading) | ✅ Yes |
| `ws/engine/` | WebSocket | Real-time streaming inference | ✅ Yes |

### WebSocket Message Format

**Client → Server:**
```json
{
  "rpm": 1714.94,
  "fuel_rate": 92.65,
  "turbo_speed": 62902.97,
  "boost_pressure": 1.51,
  "MAP": 2.49,
  "IAT": 306.01,
  "MAF": 1000.0,
  "EGT": 819.44,
  "exhaust_pressure": 3.5,
  "VGT": 41.78,
  "DPF_delta": 50203.11,
  "ambient_pressure": 0.99
}
```

**Server → Client (Health Status):**
```json
{
  "status": "HEALTHY" | "WINDOW_EVALUATED" | "LEAK_CONFIRMED",
  "window_leak": true/false,
  "leaky_samples_last_window": [...],
  "z_scores": {...}
}
```

---

## ✨ Features

### 🤖 Model Ensemble
- ✅ **4 Subsystem Autoencoders** (5-layer architecture, 2-neuron bottleneck)
- ✅ **One-Class SVM** with Kalman-filtered 12-channel input
- ✅ **Mahalanobis Distance** with data-driven covariance matrix
- ✅ **Weighted L2 Fusion** combining 6 independent z-scores

### 🔄 Signal Processing
- ✅ **12 Independent Kalman Filters** (data-driven parameters)
- ✅ **Auto-tuned from healthy data** (variance-based Q & R estimation)
- ✅ **2D state-space** (position + velocity per channel)

### 🚨 Anomaly Detection
- ✅ **Real-time WebSocket inference** (ASGI/Channels)
- ✅ **7-sample rolling window** with majority voting (4/7 threshold)
- ✅ **2-window confirmation** to reduce false positives
- ✅ **Adjustable threshold** (default: 3.5 z-score)

### 🔐 Authentication & Access Control
- ✅ **Token-based authentication** (Django REST Framework)
- ✅ **Role-based permissions** (Viewer, Tester, Admin)
- ✅ **User history tracking** (JSON field)

### 📊 Monitoring & Visualization
- ✅ **Real-time Streamlit dashboard**
- ✅ **4D radar chart** (subsystem anomaly z-scores: Boost, MAF, Exhaust, DPF)
- ✅ **Anomaly score gauge** (0–15 scale)
- ✅ **Trend line visualization** (50-point history)
- ✅ **Dynamic system status** (HEALTHY / SUBTLE LEAK / CRITICAL LEAK)

### 📈 Dataset & Training
- ✅ **40,000 total samples** (20K healthy + 20K leaky)
- ✅ **12 sensor channels** (physics-validated)
- ✅ **3 leak types** (precompressor, charge_air, exhaust)
- ✅ **10 physics equations** for realistic simulation

---

## 📚 Quick Start Commands

```bash
# 1. Setup
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 2. Generate Data
python -m ml_model.data_gen.healthy_data_gen
python -m ml_model.data_gen.leaky_data_gen

# 3. Train Models
python -m ml_model.models.svm.train.train_svm
python -m ml_model.models.autoencoders.train.nn_model_boost
python -m ml_model.models.autoencoders.train.nn_model_dpf
python -m ml_model.models.autoencoders.train.nn_model_maf
python -m ml_model.models.autoencoders.train.nn_model_exhaust
python -m ml_model.models.mahalanobis.train_mahal

# 4. Setup Database
cd backend/diesel_engine_predictor
python manage.py migrate
python manage.py createsuperuser

# 5. Run Backend API
python manage.py runserver

# 6. Run Dashboard (new terminal)
streamlit run engine_simulator/app.py
```

---

**Built with ❤️ for predictive maintenance and real-time anomaly detection.**
