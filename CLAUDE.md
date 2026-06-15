# CLAUDE.md — Diesel Engine Air Leak Detection

Read this first. It contains every non-obvious fact about this project that is not immediately derivable from the code.

---

## Project Identity

Caterpillar hackathon project. Goal: real-time air and exhaust leak detection in diesel engine test cells using only the 12 sensor channels already present in a standard CAT test cell. No additional hardware. Detection must work during steady-state dynamometer runs.

Stack: Django 6.0 (ASGI) + Django Channels (WebSocket) + Django REST Framework + TensorFlow/Keras 3.14.1 + scikit-learn 1.7.x. Python 3.12.

---

## File Layout (what matters)

```
DieselEngineLeakDetection/
├── backend/diesel_engine_predictor/     Django application root
│   ├── diesel_engine_predictor/         Django project package
│   │   ├── settings.py                  Loads .env via load_dotenv(BASE_DIR / ".env")
│   │   ├── urls.py                      Routes: /user_auth/ + /api/
│   │   └── asgi.py                      ASGI entrypoint
│   ├── predict/
│   │   ├── views.py                     POST /api/predict
│   │   ├── consumer.py                  WebSocket consumer
│   │   ├── routing.py                   ws/engine/ → EngineConsumer
│   │   └── services/
│   │       ├── pipeline.py              Core ML inference (sys.path MUST be at top)
│   │       ├── kalman_service.py        KalmanLayer wrapper
│   │       └── test_service.py          ORM helpers (get_or_create_engine, save_engine_test)
│   └── user_auth/
│       ├── models.py                    User, Engine, Sensor_Leaky_Data, Engine_Test
│       ├── views.py                     Signup, Login, Logout, Delete_Account
│       └── serializers.py              DRF serializers
├── ml_model/
│   ├── data_gen/engine_simulator_core.py  EngineSimulator (3 leak types)
│   ├── kalman/kalman_layer.py             KalmanLayer (12 channels)
│   └── models/
│       ├── model_stack.py               Singleton: loads all artifacts; predict()/evaluate()/health_check()
│       ├── autoencoders/residual_score/encoded_model/  *.keras + *_preprocessing_*.pkl
│       ├── svm/encoded/svm_model.joblib
│       └── mahalanobis/encoded/mahal_model.pkl
├── engine_simulator/app.py              Streamlit dashboard (standalone, no Django)
├── config/constants.py                  ALL hardcoded values live here
├── tests/                               pytest fixtures + stubs (not yet implemented)
├── docs/                                Architecture, ML decisions, API reference, phase log
├── engine_calibration.pkl               Stability limits + calibrated threshold (in backend root)
└── .env.example                         Copy to backend/diesel_engine_predictor/.env
```

---

## Running the Project

```bash
# Create venv with system-site-packages (required — TensorFlow is global)
python3.12 -m venv .venv --system-site-packages
source .venv/bin/activate
pip install -r requirements.txt

# .env must be at this exact path (load_dotenv resolves relative to settings.py BASE_DIR)
cp .env.example backend/diesel_engine_predictor/.env
# Edit .env: set DATABASE_URL=sqlite:///db.sqlite3 at minimum

cd backend/diesel_engine_predictor
python manage.py migrate
python manage.py runserver   # development

# ASGI (WebSocket support)
daphne -p 8001 diesel_engine_predictor.asgi:application

# Streamlit dashboard (standalone — does NOT require Django to be running)
streamlit run engine_simulator/app.py
```

---

## Critical Lessons Learned

### 1. sys.path injection must be at the TOP of pipeline.py
`manage.py` adds the project root to sys.path before loading Django apps. Daphne loads `asgi.py` directly without this injection. `pipeline.py` imports `ml_model.*`; if those imports appear before `sys.path.insert()`, Daphne crashes with `ModuleNotFoundError: No module named 'ml_model'`. The fix is already in place; never move the path setup block.

### 2. venv must use --system-site-packages for TensorFlow
TensorFlow 2.19.1 is installed in the system Python 3.12. Pip-installing it into a venv takes 5–10 minutes and ~1GB. The venv created with `--system-site-packages` inherits it. If you recreate the venv without this flag, `import tensorflow` will fail in the venv.

### 3. .env location is backend/diesel_engine_predictor/.env (not project root)
`settings.py` calls `load_dotenv(BASE_DIR / ".env")` where `BASE_DIR = Path(__file__).resolve().parent.parent`. That resolves to `backend/diesel_engine_predictor/`. A `.env` at the project root is silently ignored.

### 4. Keras version must be ≥ 3.13.2
Models were saved with Keras 3.13.2. Loading them with an older Keras raises `TypeError: Dense.__init__() got an unexpected keyword argument 'quantization_config'`. Fix: `pip install "keras>=3.13.2"` (current: 3.14.1). If you upgrade Python or recreate the venv, check the Keras version.

### 5. migrations/0001_initial.py must be the only migration file in user_auth
The original repo had 0005 and 0006 migration files referencing missing 0001–0004. This caused `migrate` to fail with a dependency error. The fix (already applied): deleted the broken files and regenerated a clean `0001_initial.py` via `makemigrations user_auth`.

### 6. Double-hashing bug in Signup
The original Signup view called `make_password(data['password'])` before passing to `UserSerializer`. DRF's `create_user()` calls `set_password()` internally. Pre-hashing produces an already-hashed string as the password, which cannot be verified on login. The `make_password()` call has been removed.

### 7. Singleton ModelStack — class-level guard
`ModelStack` uses `__new__` with a class-level `_singleton` attribute. This is intentional: loading 4 Keras models + SVM + Mahalanobis on every request would be ~2s latency. The singleton loads once at first call. If you see stale model weights in tests, add `ModelStack._singleton = None` in a fixture teardown.

---

## Phase Status

| Phase | Status | What was built |
|-------|--------|---------------|
| 0 | Complete | ML models trained, Django scaffolded, digital twin, datasets generated |
| 1 | Complete | All 6 critical blockers fixed, Daphne path bug fixed, migrations repaired |
| 2 | Complete | `/api/predict` view, `config/constants.py`, tests skeleton, full docs |
| 3 | Not started | Implement test stubs, fix MAF AE mismatch, unify thresholds, frontend |

---

## ML Pipeline in 6 Lines

1. 12 sensor channels → KalmanLayer (per-channel noise smoothing).
2. Smoothed channels → 4 autoencoders (boost/dpf/maf/exhaust; per-subsystem reconstruction error z-scores).
3. All 12 channels → One-Class SVM (multivariate outlier z-score).
4. All 12 channels → Mahalanobis distance (covariance-aware z-score).
5. Fusion: `z_cumulative = √(z_boost² + z_dpf² + z_maf² + z_exhaust² + 0.3·z_mahal² + z_svm²)`.
6. Decision: z_cumulative ≥ threshold → anomalous sample. 4/7 samples anomalous → leaky window. 2 consecutive leaky windows → `LEAK_CONFIRMED`.

Full details in `docs/ARCHITECTURE.md` and `docs/ML_DECISIONS.md`.

---

## Anomaly Threshold Map (3 values — intentional)

| Constant | Value | Used where | Derivation |
|----------|-------|-----------|-----------|
| `CONSUMER_ANOMALY_THRESHOLD` | 6.3156 | WebSocket consumer window vote | engine_calibration.pkl: mean+3σ of leaky z-scores |
| `MODEL_STACK_ANOMALY_THRESHOLD` | 3.5 | ModelStack.evaluate() `is_leak` field | Empirically tuned for Streamlit sensitivity |
| `STREAMLIT_DISPLAY_THRESHOLD` | 3.0 | Streamlit dashboard color indicator | Matches live-display visual range |

These are not aligned. A sample can be `is_leak=True` from ModelStack (≥3.5) but not count as a leaky vote in the consumer (needs ≥6.3156). Phase 3 should unify them if a consistent truth source is needed.

---

## WebSocket Quick Reference

**Connect:** `ws://localhost:8000/ws/engine/` with `Authorization: Token <token>`

**Message 1 (required):** `{"model_no": "CAT-3412-001", "engine_type": "diesel"}`

**Messages 2…N:** 12-channel sensor dict (see `config.constants.SENSOR_COLS` for exact keys)

**Responses:**
- `engine_registered` → after registration
- `buffering` → first 7 samples (stability buffer filling)
- `unstable` → stability check failed
- `sample_result` → after each scored sample (z_scores dict, confidence, status)
- `window_result` → after every 7 samples (vote result)
- `test_complete` → leak confirmed or session timeout

Full protocol in `docs/API_REFERENCE.md`.

---

## API Quick Reference

| Method | URL | Auth | Purpose |
|--------|-----|------|---------|
| POST | `/user_auth/signup/` | No | Create user; returns `{"token": "..."}` with status 201 |
| POST | `/user_auth/login/` | No | Authenticate; returns `{"token": "..."}` |
| POST | `/user_auth/logout/` | Token | Invalidate token |
| DELETE | `/user_auth/delete_account/` | Token | Delete user |
| POST | `/api/predict` | Token | Single-shot inference; returns 14-key result dict |

`/api/predict` required body: all 12 keys from `SENSOR_COLS`. Returns `is_leak`, `confidence`, `z_cumulative`, `boost_z`, `dpf_z`, `maf_z`, `exhaust_z`, `svm_z`, `ae_z`, `z_mahalanobis`, `z_scores` (list of 6), `leak_type`, `final_score`, `physics_score`.

---

## Known Bugs (not yet fixed)

1. **MAF autoencoder feature mismatch:** Trained on `[rpm, fuel_rate, MAP, MAF, turbo_speed]`; served with `[rpm, fuel_rate, MAP, IAT, MAF]`. The scaler was fit on the training set — position 5 is `turbo_speed` in the artifact but receives `IAT` at inference. Scores are subtly wrong. Fix: retrain with the inference feature set.

2. **Threshold misalignment:** Three different `is_leak` thresholds in use (see table above). Inconsistent verdicts between the REST endpoint and WebSocket consumer.

3. **User.history field never written:** The `JSONField` on the User model is always empty. The ORM call to populate it was not implemented.

---

## What Phase 3 Must Build

1. Implement real assertions in `tests/test_ml_pipeline.py` (currently all `pass`).
2. Retrain MAF autoencoder with correct feature set or fix inference code.
3. Single `ANOMALY_THRESHOLD` loaded from `engine_calibration.pkl` at runtime — replace all three separate constants with one source of truth.
4. `pytest.ini` or `pyproject.toml` with `DJANGO_SETTINGS_MODULE`, `asyncio_mode = auto`, test paths.
5. Redis channel layer for production WebSocket support (replace `InMemoryChannelLayer`).
6. Frontend (currently `frontend/.gitkeep`).

---

## Don't Touch

- `engine_calibration.pkl` — calibration artifact; recalibrate only by rerunning `kalman_tuning.py` and the AE threshold scripts.
- `ml_model/models/autoencoders/residual_score/encoded_model/*.keras` — retrain only if you fix the MAF feature mismatch or improve the architecture.
- `user_auth/migrations/0001_initial.py` — do not delete; this is the only migration file and it was regenerated after the 0005/0006 repair.
- The `--system-site-packages` venv setup — switching to a standard venv requires reinstalling TensorFlow.
