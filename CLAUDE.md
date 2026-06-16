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
│   ├── session_analysis/
│   │   ├── views.py                     POST /api/session/ — batch CSV → Go/No-Go report
│   │   ├── report_generator.py          SessionReportGenerator (pure Python, no Django)
│   │   └── urls.py                      session/ → AnalyzeSessionView
│   └── user_auth/
│       ├── models.py                    User, Engine, Sensor_Leaky_Data, Engine_Test
│       ├── views.py                     Signup, Login, Logout, Delete_Account
│       └── serializers.py              DRF serializers
├── ml_model/
│   ├── data_gen/engine_simulator_core.py  EngineSimulator (3 leak types)
│   ├── kalman/kalman_layer.py             KalmanLayer (12 channels)
│   ├── steady_state.py                    SteadyStateDetector (CV-based transient gate)
│   ├── zone_classifier.py                 ZoneClassifier (weighted AE z-score voting + physics)
│   └── models/
│       ├── model_stack.py               Singleton: loads all artifacts; predict()/evaluate()/health_check()
│       ├── autoencoders/residual_score/encoded_model/  *.keras + *_preprocessing_*.pkl
│       ├── svm/encoded/svm_model.joblib
│       └── mahalanobis/encoded/mahal_model.pkl
├── engine_simulator/app.py              Streamlit dashboard (standalone, no Django)
├── config/constants.py                  ALL hardcoded values live here
├── tests/                               pytest suite: conftest.py + test_ml_pipeline.py + test_api.py
├── scripts/                             validate_zone_isolation.py + generate_performance_report.py
├── docs/                                Architecture, ML decisions, API reference, phase log, MODEL_PERFORMANCE.md
├── Dockerfile                           Backend ASGI image
├── Dockerfile.streamlit                 Dashboard image
├── docker-compose.yml                   Backend + dashboard services
├── pyproject.toml                       pytest + coverage config
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
| 3 | Complete | MAF AE fix, threshold unification, User.history, SteadyStateDetector, ZoneClassifier, predict() verdict |
| 4 | Complete | Zone isolation diagnostic, physics override fixes (turbo/boost discriminators), consumer escalation cadence, session_analysis app (POST /api/session/), SessionReportGenerator, Streamlit 4-tab dashboard overhaul |
| 5 | Complete | Real pytest test suite (41 pass, 0 fail), performance report script (F1=1.000 on held-out synthetic), Dockerfile + docker-compose, README rewrite |

---

## ML Pipeline in 8 Lines

1. **Steady-state gate:** CV check (rpm, fuel_rate, MAF, boost_pressure) — skip if engine not stable.
2. 12 sensor channels → KalmanLayer (per-channel noise smoothing).
3. Smoothed channels → 4 autoencoders (boost/dpf/maf/exhaust; per-subsystem reconstruction error z-scores).
4. All 12 channels → One-Class SVM (multivariate outlier z-score).
5. All 12 channels → Mahalanobis distance (covariance-aware z-score).
6. Fusion: `z_cumulative = √(z_boost² + z_dpf² + z_maf² + z_exhaust² + 0.3·z_mahal² + z_svm²)`.
7. Decision: z_cumulative ≥ `ANOMALY_THRESHOLD` → anomalous sample. 4/7 samples anomalous → leaky window. 2 consecutive leaky windows → `LEAK_CONFIRMED`.
8. **Zone isolation:** ZoneClassifier uses weighted AE z-scores + physics checks to localise leak to zone_1/zone_2/zone_3/zone_4.

Full details in `docs/ARCHITECTURE.md` and `docs/ML_DECISIONS.md`.

---

## Anomaly Threshold (single source of truth — Phase 3)

| Constant | Value | Used where | Derivation |
|----------|-------|-----------|-----------|
| `ANOMALY_THRESHOLD` | 6.3156 | ALL is_leak decisions (REST, WebSocket, ModelStack) | engine_calibration.pkl: mean+3σ of leaky z-scores |
| `DISPLAY_COLOR_SCALE_MAX` | 3.0 | Streamlit chart colour scale only | NOT a decision threshold |

`ANOMALY_THRESHOLD` is loaded from `engine_calibration.pkl` at `config/constants.py` import time. All three consumers import the same constant — no more threshold disagreement.

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
- `window_result` → cadence-gated: PASS every 10 windows, WARNING every 3, FAIL every window
- `critical_alert` → when `consecutive_fail_count ≥ CONSECUTIVE_FAIL_ALERT_THRESHOLD` (5)
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
| POST | `/api/predict` | Token | Single-shot inference; returns 5-section predict() dict |
| POST | `/api/session/` | Token | Batch CSV inference; returns Go/No-Go session report |

`/api/predict` required body: all 12 keys from `SENSOR_COLS`. Returns 5-section dict: `steady_state`, `detection`, `isolation`, `decision`, `metadata`.

`/api/session/` accepts multipart form with `file` (CSV) or raw body (`Content-Type: text/csv`). CSV must have all 12 `SENSOR_COLS` as columns. Returns structured report with `header` (go_nogo), `session_summary`, `leak_analysis`, `recommendation`, `data_summary`.

---

## Known Bugs / Open Issues

1. **Zone 4 (test-cell ducting) has no synthetic validation path.** ZoneClassifier will classify to zone_4 only when no other zone dominates; we have no ground-truth test cases for this.

2. **Zone weights are physics-derived, not data-fitted.** `ZONE_AE_WEIGHTS` in constants.py was set by physical reasoning. The turbo/boost physics overrides (`_boost_below_expected`, `_turbo_above_expected`) were validated against the synthetic simulator. Real CAT data cross-validation needed before production.

3. **precompressor zone classification is 65% reliable at severity 0.20.** At severity 0.40 (evaluation set) it reaches 100% due to the turbo-above-expected physics override. At lower severities the ML vote is ambiguous.

4. **SteadyStateDetector runs per-sample** inside `predict()`. Consumer uses a window which is more robust; REST single-shot uses only one sample.

5. **Evaluation is on synthetic in-distribution data.** The performance report (F1=1.000) is measured on held-out data from the same simulator used for training. Real test-cell data cross-validation is required before production.

6. **InMemoryChannelLayer** still in use — not suitable for multi-worker WebSocket deployment.

7. **Inference latency is ~96ms/sample (674ms per 7-sample window)** measured locally. In production with GPU or optimised TFLite export this would drop significantly.

---

## What Phase 5 Built (Complete)

1. **41 pytest tests passing** — `tests/test_ml_pipeline.py` (23 tests across ModelStack, SteadyStateDetector, ZoneClassifier), `tests/test_api.py` (18 tests for auth + predict + batch + health).
2. **`pyproject.toml`** — `DJANGO_SETTINGS_MODULE`, `asyncio_mode = auto`, `pythonpath`, coverage config.
3. **`GET /user_auth/health/`** — no-auth health endpoint for Docker healthcheck.
4. **`scripts/generate_performance_report.py`** — 2,000-sample held-out eval → `docs/MODEL_PERFORMANCE.md`.
5. **`Dockerfile` + `Dockerfile.streamlit` + `docker-compose.yml`** — both services containerised.
6. **`README.md`** — portfolio-ready with Mermaid architecture diagram, real performance numbers, Docker quickstart.

## If Continuing

- Redis channel layer for production multi-worker WebSocket deployment.
- Real test-cell data validation of zone classifier physics discriminators.
- Frontend (`frontend/.gitkeep` → real UI).

---

## Resume Bullet Points

Use these verbatim or adapt.

- Built a hybrid physics + ML diesel engine air leak detection system in Python; combined Kalman-filtered sensor preprocessing with a 4-autoencoder ensemble, One-Class SVM, and Mahalanobis distance fusion achieving F1=1.000 on held-out synthetic data (2,000 samples, 4 classes, window-level evaluation)
- Implemented zone isolation classifier localising leaks to 4 engine subsystem groups using per-subsystem autoencoder z-score voting validated by physics mass-balance and turbo/boost pressure-ratio consistency checks
- Discovered and fixed a feature ordering bug (IAT fed into turbo_speed scaler) that was inflating healthy MAF z-scores by 280×; debugged by comparing healthy vs leaky z-score distributions before and after fix
- Built real-time WebSocket inference pipeline (Django Channels + Daphne ASGI) with threshold-based escalation cadence (PASS/10, WARNING/3, FAIL/1 windows) and `critical_alert` protocol for 5+ consecutive FAIL windows
- Exposed batch historical CSV analysis REST endpoint returning structured Go/No-Go session reports; built 4-tab Streamlit monitoring dashboard with live engine circuit diagram, z_cumulative trend, and zone confidence visualisation
- Containerised full stack with Docker + docker-compose; wrote pytest suite covering ML pipeline output contract (23 tests), zone isolation accuracy, and API authentication/validation (18 tests); 41/41 passing

---

## Don't Touch

- `engine_calibration.pkl` — calibration artifact; recalibrate only by rerunning `kalman_tuning.py` and the AE threshold scripts.
- `ml_model/models/autoencoders/residual_score/encoded_model/*.keras` — retrain only if you fix the MAF feature mismatch or improve the architecture.
- `user_auth/migrations/0001_initial.py` — do not delete; this is the only migration file and it was regenerated after the 0005/0006 repair.
- The `--system-site-packages` venv setup — switching to a standard venv requires reinstalling TensorFlow.
