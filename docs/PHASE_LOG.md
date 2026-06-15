# Phase Log — Diesel Engine Air Leak Detection

Chronological record of project phases: what was built, what decisions were made, what broke.

---

## Phase 0 — Ideation and Architecture (pre-session)

**Status:** Complete

### What was built
- Problem definition: real-time air leak detection in diesel engine test cells using existing sensor data, no additional hardware.
- Physics-based digital twin (`ml_model/data_gen/`) with 3 leak types (precompressor, charge_air, exhaust) and gradual severity escalation.
- Generated 20,000 healthy + 20,000 leaky training samples (`data_store/healthy_dataset.csv`, `leaky_dataset.csv`).
- Trained 4 domain-aligned autoencoders (boost, dpf, maf, exhaust) — saved as `.keras` + preprocessing `.pkl` bundles.
- Trained One-Class SVM on healthy data (all 12 channels) — saved as `svm_model.joblib`.
- Fitted Mahalanobis distance model on healthy data — saved as `mahal_model.pkl`.
- Kalman filter per channel — Q/R parameters estimated from healthy CSV.
- Engine calibration run — saved as `engine_calibration.pkl` (stability limits + cumulative z-score threshold 6.3156).
- Django project scaffolded: `user_auth` app (custom User, Engine, Sensor_Leaky_Data, Engine_Test models), `predict` app (views, consumer skeleton, routing).
- Streamlit dashboard (`engine_simulator/app.py`) for visual testing.
- Initial `requirements.txt`.

### Key decisions made in this phase
- Unsupervised detection over supervised classification (see `docs/ML_DECISIONS.md` §1).
- Four separate autoencoders aligned to engine subsystems (§2).
- Kalman filtering before inference (§3).
- L2 fusion of component z-scores (§6).
- Rolling window vote (4/7) + 2-window confirmation for leak verdict (§7).

### What was already broken at end of Phase 0
- `settings.py` had `ssl_require=True` in DATABASES config — crashes with SQLite.
- No `CHANNEL_LAYERS` setting — Django Channels raises ImproperlyConfigured.
- `ml_model/models/model_stack.py` did not exist — the singleton pattern was planned but not built.
- Signup view used `UserSerializer.objects.get(data=data)` — non-existent ORM method, crashes on any signup attempt.
- WebSocket consumer used sync ORM calls without `database_sync_to_async` — runtime error in async context.
- Consumer had no `self.send()` calls — inference results were computed but never returned to the client.
- `pipeline.py` had `sys.path.insert()` after the `ml_model` imports — Daphne (ASGI) would crash immediately.
- Migration directory had `0005` and `0006` files referencing missing `0001`–`0004` — `migrate` would fail.

---

## Phase 1 — Critical Blockers (Session 2)

**Status:** Complete

### Blockers resolved
1. **`.env` + database config:** Created `backend/diesel_engine_predictor/.env` with `DATABASE_URL=sqlite:///db.sqlite3`. Removed `ssl_require=True` from `settings.py` DATABASES block.
2. **`CHANNEL_LAYERS`:** Added `InMemoryChannelLayer` config to `settings.py`.
3. **`ModelStack` singleton:** Created `ml_model/models/model_stack.py` — loads all 4 AEs, SVM, Mahalanobis, and KalmanLayer; `predict()` + `evaluate()` + `health_check()` methods; class-level `__new__` guard for singleton.
4. **Signup view:** Fixed `UserSerializer.objects.get()` → `UserSerializer(data=data)` with `is_valid()` + `save()` pattern; removed `make_password()` pre-hash (was double-hashing passwords).
5. **Async consumer ORM:** Wrapped all sync ORM calls in `database_sync_to_async`.
6. **Consumer sends:** Added `self.send()` for all message types: `engine_registered`, `buffering`, `unstable`, `sample_result`, `window_result`, `test_complete`, `error`.

### Bonus fix (discovered during verification)
- **Daphne sys.path bug:** `pipeline.py` had path injection after imports. Moved to top of file. This fix is required for any ASGI startup; `manage.py` masks the bug by injecting paths itself, so it only appears when running Daphne directly.

### Environment setup (required, not pre-existing)
- System Python 3.12 had TensorFlow 2.19.1 installed globally.
- Created project venv with `--system-site-packages` to inherit TF without reinstalling (TF install is ~500MB and takes many minutes).
- Installed Django, channels, DRF, etc. separately into the venv.
- Upgraded Keras from 3.12.0 to 3.14.1 to satisfy models saved with Keras 3.13.2.

### Migration fix
- Deleted `user_auth/migrations/0005_*` and `0006_*` (referenced missing `0001`–`0004`).
- Regenerated clean `0001_initial.py` via `makemigrations user_auth`.
- `python manage.py migrate` completed with all tables created.

### Verification outputs (Session 2)
- `python manage.py check`: 0 errors, 0 warnings.
- `python manage.py migrate`: all migrations applied cleanly.
- `daphne -p 8001 diesel_engine_predictor.asgi:application`: started without `ModuleNotFoundError`.
- Streamlit imports: all passed.

---

## Phase 2 — Clean Foundation + Context Files (Session 3)

**Status:** Complete

### What was built

**Code changes:**
- `predict/views.py` rewritten: reads `request.data`, validates all 12 `SENSOR_COLS`, parses floats, calls `ModelStack().predict()`, returns 200/400/500 with descriptive error messages. Full type hints + Google docstrings.
- `config/constants.py` created: all hardcoded values extracted from the entire codebase — window sizes, thresholds, stability limits, model file paths, ML training hyperparameters, simulator parameters, zone labels, recommended actions.
- `consumer.py` refactored: all magic numbers → `config.constants`; `print()` → `logger`; type hints throughout.
- `pipeline.py` refactored: magic numbers → `config.constants`; `print()` → `logger`; sys.path injection moved to top.
- `model_stack.py` updated: uses `MODEL_STACK_ANOMALY_THRESHOLD` from `config.constants` instead of hardcoded 3.5.

**Test suite:**
- `tests/__init__.py` (empty)
- `tests/conftest.py`: session-scoped fixtures for `model_stack`, `healthy_sample`, `leaky_sample` using real `EngineSimulator`.
- `tests/test_ml_pipeline.py`: 9 test stubs — ModelStack load, output keys contract, healthy/leaky detection, confidence bounds, z_scores list length, non-negativity, health_check.
- `tests/test_api.py`: 8 Django test stubs for all REST endpoints.
- `tests/test_websocket.py`: 7 async test stubs for WebSocket consumer protocol.

**Documentation:**
- `docs/ARCHITECTURE.md`: full system map, data flow diagram, ML pipeline details, WebSocket protocol, DB schema, known limitations.
- `docs/ML_DECISIONS.md`: 9 interview-prep answers for every design choice.
- `docs/API_REFERENCE.md`: full endpoint docs with curl examples, request/response tables, error codes.
- `docs/PHASE_LOG.md`: this file.
- `.env.example`: safe-to-commit copy with all keys, empty values.
- `CLAUDE.md`: project root context file for AI sessions.

### Known issues remaining after Phase 2
- MAF autoencoder feature mismatch (see `docs/ARCHITECTURE.md` §9, `docs/ML_DECISIONS.md` §9) — not fixed; requires retraining.
- Three different anomaly thresholds (6.3156 in consumer, 3.5 in ModelStack, 3.0 in Streamlit) — documented in `config/constants.py`; not unified because they affect different decision paths.
- Test stubs are not yet implemented (by design — marked with `TODO`).
- No frontend (by design — out of scope for Phase 2).

---

## Phase 3 — Planned (next session)

### Must build
- Implement test stubs in `tests/test_ml_pipeline.py` (at minimum the health_check and output-keys tests).
- Fix MAF autoencoder feature mismatch: retrain `nn_model_maf.py` with `[rpm, fuel_rate, MAP, IAT, MAF]` or fix inference code to use `[rpm, fuel_rate, MAP, MAF, turbo_speed]` to match the training set.
- Unify anomaly thresholds: single `ANOMALY_THRESHOLD` loaded from `engine_calibration.pkl` at runtime.
- Replace `InMemoryChannelLayer` with Redis for multi-worker WebSocket support.
- Implement frontend (currently `frontend/` is `.gitkeep`).
- Add `pytest.ini` or `pyproject.toml` for test configuration (`DJANGO_SETTINGS_MODULE`, `asyncio_mode`, etc.).
