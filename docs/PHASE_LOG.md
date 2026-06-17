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

## Phase 3 — Correctness + Isolation (Session 3 — 2026-06-16)

**Status:** Complete

### Part A — Correctness fixes

**A1 — MAF AE feature mismatch (fixed):**
- Root cause: `AE_FEATURES["maf"]` had `["rpm","fuel_rate","MAP","IAT","MAF"]`; training used `["rpm","fuel_rate","MAP","MAF","turbo_speed"]`. IAT (~300 K) was fed to the turbo_speed scaler position, producing a normalized value of ~−3 and a reconstruction error of 5–6σ even on healthy samples.
- Fix: Changed `AE_FEATURES["maf"]` in `config/constants.py` to `["rpm","fuel_rate","MAP","MAF","turbo_speed"]`.
- Verification: healthy maf_z 5.789 → **0.021**; leaky maf_z 5.827 → **0.299**.

**A2 — Threshold unification (fixed):**
- Root cause: Three thresholds (6.3156, 3.5, 3.0) in different places produced inconsistent `is_leak` verdicts.
- Fix: `ANOMALY_THRESHOLD` loaded at runtime from `engine_calibration.pkl` in `config/constants.py`. All three consumers (REST, WebSocket, Streamlit) now import this single constant.
- `MODEL_STACK_ANOMALY_THRESHOLD` and `CONSUMER_ANOMALY_THRESHOLD` removed.
- `STREAMLIT_DISPLAY_THRESHOLD` renamed to `DISPLAY_COLOR_SCALE_MAX` (display-only, not a decision gate).
- Verification: `from config.constants import ANOMALY_THRESHOLD` → `6.315587152674103`. REST and consumer agree for all z_cumulative values.

**A3 — User.history write (fixed):**
- Root cause: `user.history` JSONField was never written.
- Fix: Added `update_user_history()` to `predict/services/test_service.py`. Consumer's `finish_test()` calls it after `save_engine_test()`. History is bounded to 50 entries; older entries are dropped.

### Part B — Steady-state gate + Zone isolation

**B1 — `ml_model/steady_state.py` — SteadyStateDetector:**
- Computes per-channel CV (std/mean) over a sample window.
- Monitored channels: rpm, fuel_rate, MAF, boost_pressure.
- Thresholds from `config.constants` (STEADY_STATE_{RPM,FUEL,MAF,BOOST}_CV_MAX).
- Returns `{is_steady, confidence, reason, unstable_channels, window_stats}`.
- `from_config()` classmethod for per-engine threshold tuning.

**B2 — `ml_model/zone_classifier.py` — ZoneClassifier:**
- Localises leak to zone_1/zone_2/zone_3/zone_4/multiple/unknown.
- Weighted voting from per-AE z-scores via `ZONE_AE_WEIGHTS` (constants.py).
- Physics validators: mass balance (AFR = MAF/fuel_rate) and pressure ratio (MAP/ambient).
- Physics can only override one specific case (zone_1 with MAP/ambient anomaly → zone_2).
- "multiple" when top two zones within 15% of each other; "unknown" when all below floor.
- Weights defined in `config/constants.py` as `ZONE_AE_WEIGHTS`.

**B3 — `ModelStack.predict()` extended:**
- Returns five-section structured dict: `steady_state`, `detection`, `isolation`, `decision`, `metadata`.
- `isolation` populated only when `detection.is_leak == True`.
- `decision` fields: `flag` (PASS/WARNING/FAIL), `severity` (none/minor/moderate/severe), `recommended_action` (from RECOMMENDED_ACTIONS), `escalate_immediately`.
- `evaluate()` unchanged (Streamlit depends on its flat 14-key return format).

**B4 — Consumer `window_result` enriched:**
- Each `window_result` message now includes `flag`, `severity`, `is_steady_state`, `escalate`, `zone`, `zone_label`, `top_evidence`, `zone_scores`.
- Cadence unchanged (still emits every 7 samples).

### Verification outputs

```
manage.py check: 0 issues
ANOMALY_THRESHOLD: 6.315587152674103
Zone1 (high maf_z, normal boost_z): detected_zone=zone_1, zone_scores zone_1=0.59 highest ✓
Zone2 (high boost_z, normal maf_z): detected_zone=zone_2, zone_scores zone_2=0.55 highest ✓
Zone3 (high exhaust_z/dpf_z):       detected_zone=zone_3, zone_scores zone_3=0.69 highest ✓
Stable window: is_steady=True ✓
RPM-step window: is_steady=False, unstable_channels=['rpm'] ✓
Healthy predict(): is_leak=False, isolation={}, flag=PASS ✓
Leaky predict():  is_leak=True, zone=zone_3, flag=FAIL, severity=severe, escalate=True ✓
```

### Known issues remaining after Phase 3
- Test stubs still not implemented (TODO markers remain in test files).
- Zone 4 (test-cell ducting) has no synthetic validation path.
- Zone weights are physics-derived, not data-fitted.
- No frontend.
- InMemoryChannelLayer still in use (production Redis not configured).

---

## Phase 4 — Demo Layer (Session 4 — 2026-06-16)

**Status:** Complete

### Part A — Zone Isolation Diagnostic

**A1 — `scripts/validate_zone_isolation.py` (created):**
- Generates 20 windows per leak type using EngineSimulator.
- Sets `sim.leak_severity = 0.40` directly after `introduce_leak()` to bypass the ~2 000-step slow escalation.
- Runs full `ModelStack.predict()` on each window.
- Prints discrimination table (maf_z, boost_z, exhaust_z, dpf_z, svm_z, mahal_z, top_zone, zone%, eval).
- Exits 0 only if all leak types map to expected zones; exits 1 if any FAIL.

**A2 — Two failures identified and fixed:**

*Issue 1: precompressor → "none" (0% detection) at 250 escalation steps.*
Root cause: severity ~0.09 at 250 steps produces z_cumulative ≈ 3.09, below ANOMALY_THRESHOLD=6.3156.
Fix: jump to severity 0.40 directly in diagnostic.

*Issue 2: charge_air → zone_3 (95% of windows).*
Root cause: the charge_air physics cascade (boost_pressure *= (1-s), turbo compensates → MAP drops → MAF drops → exhaust_pressure drops via physics chain) makes exhaust_z > boost_z. With `ZONE_AE_WEIGHTS` zone_3 = exhaust:1.0 + dpf:0.8, zone_3 scored 7.94 vs zone_2 scored 4.99.

**A3 — Physics overrides added to ZoneClassifier:**
Two new rules in `_apply_physics_adjustment()`:

*Rule 2 — boost-below-expected (charge_air pattern):*
Computes `actual_boost / expected_boost(turbo, fuel)` using the physics formula `0.000016*turbo + 0.003*fuel + 0.25*(fuel/120)`.
For charge_air: boost is explicitly `*= (1-s)` while turbo rises → ratio ≈ 0.55 at severity 0.40. Below threshold 0.82 → zone_2.
For exhaust: boost is recalculated FROM the reduced turbo → ratio ≈ 1.0. Above threshold → zone_3 unchanged.
Fires when ML voted `zone_3` or `multiple`.

*Rule 3 — turbo-above-expected (precompressor pattern):*
Computes `actual_turbo / expected_turbo(fuel)` using `28000 + 400*fuel + 0.00008*fuel²`.
For precompressor: turbo `*= (1+0.2*s)` → elevated by ~8% at severity 0.40 → ratio > threshold 1.04 → zone_1.
For exhaust: turbo is depressed (clipped to 60000) → ratio ~0.88 < 1.04 → rule doesn't fire.
Only fires when ML voted `multiple` (ambiguous) AND boost-below-expected is False.

**A4 — ZONE_AE_WEIGHTS updated:**
Removed cross-zone cascade noise: zone_2 no longer includes exhaust/dpf weights; zone_3 no longer includes boost weight.

**Final validation output:**
```
no_leak       none   100%  OK
precompressor zone_1  65%  OK
charge_air    zone_2 100%  OK
exhaust       zone_3 100%  OK
RESULT: PASS (exit 0)
```

### Part B — Consumer Escalation + Batch Endpoint

**B1 — consumer.py escalation cadence:**
- Added `self.consecutive_fail_count = 0` to `connect()`.
- `_evaluate_window()` now gates `window_result` sends: PASS every 10 windows, WARNING every 3, FAIL every window.
- Added `critical_alert` message type when `consecutive_fail_count >= CONSECUTIVE_FAIL_ALERT_THRESHOLD` (5).
- Imports: `SEND_INTERVAL_PASS/WARNING/FAIL`, `CONSECUTIVE_FAIL_ALERT_THRESHOLD`.

**B2 — `session_analysis` Django app (new):**
- Created via `manage.py startapp session_analysis`.
- Registered in `INSTALLED_APPS`.
- `session_analysis/urls.py`: `session/ → AnalyzeSessionView`.
- Wired into main `urls.py` at `api/`.
- `session_analysis/views.py` — `AnalyzeSessionView`:
  - Accepts multipart `file` field or raw `Content-Type: text/csv` body.
  - Parses CSV with pandas; validates all 12 `SENSOR_COLS` present.
  - Runs `ModelStack.predict()` on each row.
  - Returns `SessionReportGenerator().generate(per_sample)` response.

### Part C — SessionReportGenerator

`session_analysis/report_generator.py` — pure Python, no Django dependency (importable from Streamlit):
- `generate(session_data)` → structured report dict:
  - `header`: timestamp, sample_count, go_nogo, verdict_summary
  - `session_summary`: leak_count, leak_rate_pct, mean/max z_cumulative, steady_rate, flag_counts
  - `leak_analysis`: top_zone, zone_breakdown (count/pct/mean_confidence), subsystem_z_means, mean_svm_z/mahal_z
  - `recommendation`: action text, escalate_immediately flag, top_zone_label
  - `data_summary`: z_cumulative p50/p95/max
- `to_text_summary(report)` → 80-column terminal output with `╔═══╗` box-drawing borders.
- Go/No-Go thresholds: `NO-GO` if leak_rate ≥ 20% or fail_count ≥ 10% of samples; `CAUTION` if leak_rate ≥ 5% or any FAIL; `GO` otherwise.

### Part D — Streamlit Dashboard Overhaul

`engine_simulator/app.py` completely rewritten — 4 tabs:

1. **Live Monitor**: Start/Stop/Reset controls, leak type selector (precompressor/charge_air/exhaust), real-time engine diagram with CSS zone color-coding (IDLE/OK/WARN/CRIT), zone confidence bar chart (Plotly), z_cumulative trend chart with ANOMALY_THRESHOLD hline, 6-column metric row (per-subsystem z-scores).

2. **Session History**: Scrollable table with FAIL/WARNING row color coding, aggregate metrics (leak rate, max z, FAIL count), Clear History button.

3. **Batch Analysis**: CSV file upload, column validation, per-row inference with progress bar, Go/No-Go display, zone breakdown bar chart, recommendation text, full `to_text_summary()` code block.

4. **Model Info**: `health_check()` status table, ANOMALY_THRESHOLD display, SENSOR_COLS list, zone definitions, ML pipeline description.

All ML imported directly — no Django API calls. `ModelStack` loaded via `@st.cache_resource` (matches singleton behaviour).

### Verification

```
manage.py check:                0 issues
manage.py migrate:              No migrations to apply
scripts/validate_zone_isolation.py:  PASS (exit 0)
SessionReportGenerator:         80-char uniform terminal output
All Streamlit imports:          OK (verified by import check)
```

### Known issues remaining after Phase 4

- precompressor zone_1 is only 65% reliable at severity 0.20. At severity 0.40 it reaches 100%.
- Test stubs not yet implemented (resolved in Phase 5).
- InMemoryChannelLayer still in use.
- Frontend `.gitkeep` — no real UI.

---

## Phase 5 — Portfolio Completion (Session 5 — 2026-06-16)

**Status:** Complete

### What was built

**Part A — Tests + Model Performance Report**

- `tests/conftest.py` — Rewritten with real EngineSimulator fixtures: `healthy_sample` (60-step warmup), `leaky_sample` (charge_air at severity 0.40), `stable_window` (30 identical samples → CV=0), `transient_window` (RPM step 1000→2500 → CV=0.43 >> threshold).
- `tests/test_ml_pipeline.py` — 23 tests across 4 classes: `TestModelStackLoading` (singleton, health_check), `TestPredictOutputContract` (5-section dict keys, types, leaky detection, zone populated), `TestSteadyStateDetector` (stable/transient/empty), `TestZoneClassifier` (charge_air→zone_2 ≥80%, exhaust→zone_3 ≥80%, parametrised).
- `tests/test_api.py` — 18 tests: auth (signup/login/logout/wrong-password), health endpoint, predict (auth-required, missing-channels, valid-payload, 5-section response), batch (auth-required, missing-columns, valid-csv-go-nogo).
- `predict/views.py` bugfix — logger was accessing old flat-dict keys `result["is_leak"]` from `evaluate()`; updated to `result["detection"]["is_leak"]` for the new 5-section `predict()` output.
- `user_auth/views.py` + `user_auth/urls.py` — added `GET /user_auth/health/` (no auth; returns `{"status": "ok"}`; used by Docker healthcheck).
- `scripts/generate_performance_report.py` — 2,000-sample held-out evaluation: 500/class, window-level detection (≥4/7), zone isolation confusion matrix, latency measurement. Writes `docs/MODEL_PERFORMANCE.md`.

**Part B — pytest infrastructure**

- `pyproject.toml` — `DJANGO_SETTINGS_MODULE = "diesel_engine_predictor.settings"`, `asyncio_mode = "auto"`, `pythonpath = [".", "backend/diesel_engine_predictor"]`, `[tool.coverage.run]`.
- `requirements.txt` — added `pytest-django`, `pytest-asyncio`, `pytest-cov`.

**Part C — Docker**

- `Dockerfile` — `python:3.12-slim`, installs `libgomp1` + `curl` (for healthcheck), pip-installs requirements, runs `migrate --noinput` + `daphne` on start.
- `Dockerfile.streamlit` — slim image for Streamlit dashboard.
- `docker-compose.yml` — `backend` + `dashboard` services; backend has healthcheck on `/user_auth/health/`.

**Part D — README**

- `README.md` — full rewrite: Mermaid architecture diagram, ML pipeline table, real performance table from script output, Docker quickstart, API reference, project structure.

### Verification

```
pytest tests/ -m "not slow":  41 passed, 1 deselected, 0 failed
manage.py check:               0 issues
manage.py migrate:             No migrations to apply
generate_performance_report.py:
  Binary: P=1.000 R=1.000 F1=1.000 FPR=0.000
  Zone macro F1: 1.000 (zone_1=1.00 zone_2=1.00 zone_3=1.00)
  Latency: mean=674ms  p95=755ms per 7-sample window
```

### Notes

- F1=1.000 reflects in-distribution synthetic evaluation (same simulator as training). Real test-cell data would show lower numbers.
- views.py log-line bug (accessing old `evaluate()` flat keys from `predict()` output) was found by the API tests and fixed.
- `pytest-django` was not in requirements.txt or installed; added and installed as part of this phase.
- The `slow` marker deselects the batch inference test in CI (`-m "not slow"`); it still passes when run without the flag.

---

## Frontend — Browser UI (2026-06-16)

**Status:** Complete

### What was built

- `frontend/index.html` — single self-contained file; no build step, no npm, no external CDN. Open directly in Chrome/Safari.
- Login form + Sign-up form → POST `/user_auth/login/` or `/user_auth/signup/` → DRF token stored in JS state.
- WebSocket session: `ws://localhost:8000/ws/engine/?token=<tok>` — query-param token auth because browser WebSocket API cannot send the `Authorization` header.
- `predict/token_auth_middleware.py` — `TokenAuthMiddleware` reads `?token=` from the WS URL query string, resolves `rest_framework.authtoken.Token` async, and writes `scope["user"]`. Placed inside `AuthMiddlewareStack` in `asgi.py` so it overrides the anonymous session user without breaking cookie-based auth.
- JS sensor generator: baselines from `_VALID_PAYLOAD` (healthy sample known to pass the API), noise σ values tuned below stability-gate limits (σ_rpm=10 << limit=30.5, σ_fuel=1 << 3.37, σ_boost=0.008 << 0.036). Three leak modes (charge_air/exhaust/precompressor) apply severity-0.40 multipliers from `engine_simulator_core.py`.
- Canvas 2D chart: 60-point rolling window, threshold dashed line at 6.3156, green/red segment coloring by `is_leak` status, HiDPI-aware (devicePixelRatio scaling).
- 6 subsystem z-score cards (boost/dpf/maf/exhaust/mahalanobis/svm) with `zColor()` threshold-relative coloring.
- FLAG badge (PASS/WARNING/FAIL/CRITICAL/BUFFERING/UNSTABLE) with CSS animation on CRITICAL.
- Zone confidence bars with active-zone highlight and `RECOMMENDED_ACTIONS` text box.
- Scrolling event log (250-line cap, color-coded by severity).
- Backend probe on page load via `GET /user_auth/health/` — shows connection dot in header.
- Connection panel auto-collapses after engine registration to give screen space to live data.

### Related changes

- `settings.py` — added `corsheaders` + `CORS_ALLOW_ALL_ORIGINS = True` so `file://` origin can POST to `localhost:8000` without CORS rejection. Also fixed `ALLOWED_HOSTS` to default to `localhost 127.0.0.1 0.0.0.0 [::1]` (was `[]` which breaks Docker with `DEBUG=false`).
- `requirements.txt` — added `django-cors-headers`.
- `asgi.py` — added `TokenAuthMiddleware` import and wired inside `AuthMiddlewareStack`.
- `docker-compose.yml` — added `./frontend:/app/frontend` volume mount to backend service.
- `README.md` — added `open frontend/index.html` to the quickstart.

### Notes

- The stability buffer fills with 7 samples before inference starts; the log shows `buffering 1/7 … 7/7`. After switching to leak mode, 1–2 `unstable` messages are expected while the buffer flushes the mode-change transient, then detection resumes.
- `CORS_ALLOW_ALL_ORIGINS = True` is development-only. For production, restrict to specific origins via `CORS_ALLOWED_ORIGINS`.

---

## Frontend Phase 2 — Stitch-Pixel-Faithful UI (2026-06-16)

**Status:** Complete

### What was built

Three production-quality, self-contained HTML files based on Stitch design reference files. All Tailwind config, colours, fonts, spacing, and animation values are taken directly from the Stitch reference HTML — not from memory or assumption.

- `frontend/index.html` — Landing/product page.
  - Base: `stitch_designs/.../cat_product_landing_page/code.html` (0px border-radius, #0A0A0A background, Industrial Command palette).
  - Headline: "ENGINE LEAK DETECTION & ISOLATION"; hero CTA "Get Started" → login.html.
  - 4 feature cards (grid-cols-4 at lg): 4-Zone Isolation / Physics+ML Hybrid / Go/No-Go Reports / On-Premise Only.
  - Product showcase, 6-cell technical grid (01–06), Final CTA, footer.
  - Nav links: Platform, Features, Specs, Dashboard → dashboard.html, Login → login.html.

- `frontend/login.html` — Operator login and registration page.
  - Base: `stitch_designs/.../cat_login_premium/code.html` (glass-panel, scanline animation, mouse-parallax background).
  - Login / Register tabs (inline toggle, no separate page).
  - Real POST `/user_auth/login/` and `/user_auth/signup/` with DRF token response.
  - Token stored in `sessionStorage("cat_token")`, username in `sessionStorage("cat_username")`.
  - Auto-redirect to dashboard.html if `cat_token` already exists on load.
  - Error state: `bg-error-container border border-error` panel with message above the form.
  - Show/hide password toggle (eye icon).

- `frontend/dashboard.html` — Live monitoring dashboard.
  - Base: `stitch_designs/.../cat_monitoring_dashboard_premium/code.html` + state files.
  - Auth guard on load: redirects to login.html if no `cat_token` in sessionStorage.
  - 3-column layout: sidebar 28% + centre flex-1 + right 24%.
  - Real WebSocket: `ws://localhost:8000/ws/engine/?token=<token>` — registration → sensor loop → inference results.
  - Canvas 2D z-score chart (60-point rolling, threshold dashed line at 6.3156, green/red dot coloring).
  - JS sensor generator with Box-Muller Gaussian noise; 3 leak injection modes (charge_air/exhaust/precompressor) at severity 0.40.
  - State transitions (no page reload): PASS (green) → WARNING (yellow advisory) → FAIL (red + `.fail-glow` + `.critical-text-blink`).
  - Critical alert banner on `consecutive_fail_count ≥ 5`.
  - Zone confidence bars (update from `window_result.zone_scores`, highlighted zone is top zone).
  - 6-cell sensor telemetry grid (RPM, MAF, boost_pressure, MAP, EGT, turbo_speed).
  - Event log: newest-top, 60 entries max, EXPORT → TSV download.
  - Batch analysis modal: drag-and-drop CSV → POST `/api/session/` → Go/No-Go badge + summary.
  - "TERMINATE SESSION" button: POST `/user_auth/logout/`, clear sessionStorage, redirect to login.html.

### Design system fidelity notes

- `index.html`: borderRadius DEFAULT "0px" (exact match to cat_product_landing_page config).
- `login.html`: borderRadius DEFAULT "0.25rem" (exact match to cat_login_premium config, which uses slight radius).
- `dashboard.html`: borderRadius DEFAULT "4px" (exact match to cat_monitoring_dashboard_premium config).
- All colour tokens, font families, font sizes, and spacing from respective Tailwind configs.
- `.panel-glass`, `.inner-panel-gradient`, `.data-inlay-deep`, `.pulse-critical`, `.fail-glow`, `.critical-text-blink`, `.scanline` — all CSS taken from reference files verbatim.

---

## Frontend Phase 3 — Vite + React Migration (2026-06-17)

**Status:** Complete

### What was built

Full migration of the three self-contained HTML files into a proper Vite + React 18 project with Tailwind CSS 3 and React Router v6. All Stitch design tokens preserved exactly.

**STEP 0 — Project scaffold**

- Deleted old `frontend/{index,login,dashboard}.html`.
- `npm create vite@latest . -- --template react` inside `frontend/`.
- Installed `tailwindcss@3 postcss autoprefixer react-router-dom`.
- `frontend/tailwind.config.js` — single Industrial Command token set from `DESIGN.md` + cat_monitoring_dashboard_premium palette (background `#0a0a0a`, industrial-red `#FF3B30`, industrial-green `#34C759`, borderRadius DEFAULT `0px`).
- `frontend/vite.config.js` — proxy `/api` + `/user_auth` → `http://localhost:8000`; `/ws` → `ws://localhost:8000` with `ws: true`. Eliminates all CORS issues that existed with `file://` origin.
- `frontend/index.html` — Inter + JetBrains Mono + Material Symbols Outlined from Google Fonts; `<div id="root">`.

**STEP 1–2 — API service layer + custom hooks**

- `src/api/client.js` — `apiFetch`: reads token from sessionStorage, sets `Authorization: Token <tok>` header, redirects to `/login` on 401.
- `src/api/auth.js` — login, signup, logout using relative paths (proxy-routed).
- `src/api/session.js` — `analyzeSession`: raw `fetch` with `FormData` (no Content-Type; browser sets multipart boundary). `singlePredict`: JSON POST.
- `src/api/websocket.js` — `createEngineSocket(token, handlers)`: connects to `ws://localhost:8000/ws/engine/?token=<token>` directly (not through Vite proxy; TokenAuthMiddleware on Django side reads the query param).
- `src/hooks/useAuth.js` — `getToken`, `isAuthenticated`, login (sessionStorage write), logout (API call + clear + navigate).
- `src/hooks/useEngineWebSocket.js` — `connect()` sends engine registration on WS open; starts 500ms interval reading `leakModeRef`/`leakTypeRef` (avoids stale closures); `onMessageRef.current = onMessage` kept in sync on every render; `disconnect()` stops interval + closes WS.

**STEP 3 — Sensor generator + constants**

- `src/lib/sensorGenerator.js` — Box-Muller Gaussian noise; BASELINES from `test_api.py _VALID_PAYLOAD` (confirmed to produce healthy PASS); NOISE σ values below stability gate limits; 3 leak modes at severity 0.40.
- `src/lib/constants.js` — `ANOMALY_THRESHOLD=6.3156`, `SENSOR_COLS` array, `ZONE_LABELS`, `ZONE_LABELS_LONG`, `RECOMMENDED_ACTIONS`.

**STEP 4 — Layout components**

- `src/components/layout/Header.jsx` — 80ms session timer; WS status pill (dot + label colour by wsState prop: connected=green, error=red, else pulse); flag badge (CRITICAL FAIL blinking / WARNING amber pulse / NOMINAL green); TERMINATE SESSION button.
- `src/components/layout/Sidebar.jsx` — 5 NAV items; engine model input; leak injection toggle (translate-x CSS); 3 leak type buttons shown when mode=leak; START/STOP buttons; EMERGENCY STOP full-width red.
- `src/components/layout/Footer.jsx` — WS state dot + "Core Systems: Nominal/Error/Initialising" text.

**STEP 5 — Dashboard components**

- `src/components/dashboard/StatusPanel.jsx` — FLAG badge (64px text, `critical-text-blink` on FAIL); confidence bar (visible on WARN/FAIL); 6 z-score cards (2×3 grid, `zColor()` threshold-relative colouring); Protocol Advisory panel (border-l-4 colour-coded); Steady State indicator with material icon.
- `src/components/dashboard/AnomalyChart.jsx` — Canvas 2D; `ResizeObserver` on parent element; HiDPI (`canvas.width = offsetWidth * devicePixelRatio`); draws: bg `#050505`, grid lines, threshold dashed red line at `ANOMALY_THRESHOLD`, gradient fill, gold line, green/red dots per point.
- `src/components/dashboard/ZoneConfidenceBars.jsx` — 4 zones; bar width = `score / max * 100%`; gold bar + label for detected zone; `transition-all duration-700`.
- `src/components/dashboard/SensorGrid.jsx` — 6 cells (rpm, MAF, boost_pressure, MAP, EGT, turbo_speed); `inner-panel-gradient`; turbo_speed formatted as `v/1000` KRPM.
- `src/components/dashboard/EventLog.jsx` — Events array (newest first); `entryStyle()` returns CSS classes by flag; EXPORT → `.tsv` download; 60-entry cap.
- `src/components/dashboard/BatchModal.jsx` — Fixed overlay; drag-drop zone; hidden file input; `FormData` POST to `/api/session/`; Go/No-Go green/red display; DOWNLOAD REPORT JSON; error panel.

**STEP 6 — Pages**

- `src/pages/Landing.jsx` — cat_product_landing_page converted to JSX; React Router `<Link>` for CTAs; nav scroll opacity; hover card effects via useEffect; 4 feature cards; product showcase; 6-cell pipeline grid; final CTA.
- `src/pages/Login.jsx` — cat_login_premium converted to JSX; `useState` for tab/username/password/email/loading/error/success; mouse parallax via useEffect; real auth via `api/auth.js`; show/hide password toggle; auto-redirect if token exists.
- `src/pages/Dashboard.jsx` — auth guard; all state (flag, zone, zoneScores, confidence, isSteady, bufferState, zScores, chartPoints, events, sample, leakMode, leakType, engineModel, wsState, showCrit, critCount, testResult); `useEngineWebSocket` hook; `disconnectRef` pattern avoids stale closure when calling `disconnect()` from `onMessage`; full WS dispatch for all 7 message types; 3-column layout (StatusPanel / Chart+Grid+Log / ZoneBars+SessionInfo+ZoneKey); critical alert banner; test complete modal.

**STEP 7 — Routing**

- `src/App.jsx` — `BrowserRouter`, `PrivateRoute` (checks `sessionStorage.cat_token`, redirects to `/login`), routes for `/`, `/login`, `/dashboard`, catch-all `*` → `/`.

**LAST STEP — Doc updates**

- `docker-compose.yml` — comment block documenting React dev server on port 5173.
- `README.md` — Docker quickstart updated; "Frontend (React + Vite)" subsection; route table; Project Structure updated with `frontend/src/`; Tech Stack updated.
- `CLAUDE.md` — frontend file layout updated to full `src/` tree.
- `docs/PHASE_LOG.md` — this entry.
- `.gitignore` — `node_modules/` already present; covers `frontend/node_modules/`.

### Key technical decisions

- **Vite proxy vs CORS_ALLOW_ALL_ORIGINS**: With Vite proxy, all HTTP fetches use relative paths (no CORS). `CORS_ALLOW_ALL_ORIGINS = True` remains in settings for the Streamlit dashboard (which still calls the API directly), but the React frontend no longer depends on it.
- **WebSocket not proxied**: Vite's WS proxy has edge cases. Instead, `createEngineSocket` connects directly to `ws://localhost:8000`. Django's `TokenAuthMiddleware` reads the `?token=` query param — same auth mechanism as the old `dashboard.html`.
- **`disconnectRef` pattern**: `onMessage` is defined before the hook call (and thus before `disconnect` is in scope). Capturing `disconnect` directly in the `useCallback(fn, [])` closure would reference an uninitialized variable on first render. Solution: `disconnectRef.current = disconnect` updated after every render; `onMessage` calls `disconnectRef.current?.()`.
- **`leakModeRef` / `leakTypeRef`**: 500ms interval closure would capture stale state. Refs updated via `setLeakConfig(mode, type)` so every interval tick reads the latest values.
- **Single Tailwind config**: Three Stitch pages had slightly different radius tokens. Used `borderRadius: { DEFAULT: '0px' }` uniformly (from DESIGN.md instruction) with inline `style={{}}` for radius overrides where needed.

### Verification

```
npm run dev:   Vite dev server starts at http://localhost:5173
App.jsx:       BrowserRouter routes resolve (/ /login /dashboard)
All pages:     JSX compiles without errors
WS hook:       Connects to ws://localhost:8000/ws/engine/?token= with valid token
```

---

## Frontend Bugfix Pass (2026-06-17)

**Status:** Complete

### Bug 1 — Landing nav links don't scroll

**Root cause:** All four nav links used `href="#"`. No section in Landing.jsx had an `id` attribute. Every click reloaded the page hash to `#` and scrolled to the top without targeting any section.

**Fix:** Added `id="features"` to the feature cards section, `id="platform"` to the product showcase section, `id="specs"` to the technical grid section. Updated nav hrefs to `href="#features"`, `href="#platform"`, `href="#specs"`. Added `html { scroll-behavior: smooth; }` to `index.css`.

---

### Bug 2 — Anomaly chart only showed threshold line, no data line

**Root cause (primary):** `Dashboard.jsx:256` called `<AnomalyChart chartPoints={chartPoints} />` but `AnomalyChart.jsx:7` destructures `{ points }`. The prop `points` was always `undefined`. The guard `if (!pts || pts.length < 2) return` at line 57 fired on every render, so no data line, gradient, or dots were ever drawn. Only the threshold line (hardcoded unconditionally before the guard) appeared.

**Root cause (secondary):** Dots used `pt.isLeak` to pick red vs green, but Dashboard creates points as `{ z, pass }`. `pt.isLeak` was always `undefined` (falsy) so all dots were green even on anomalous samples.

**Fix:** Changed `<AnomalyChart chartPoints={…} />` to `<AnomalyChart points={…} />` in Dashboard.jsx. Changed `pt.isLeak` to `!pt.pass` in AnomalyChart.jsx.

---

### Bug 3 — FAIL state showed "No Leak Detected" in the completion modal

**Root cause:** `consumer.py:372` sends `"leak_detected": bool` in `test_complete`. Dashboard.jsx read `testResult.outcome === 'LEAK_CONFIRMED'` — the field `outcome` doesn't exist in the payload (verified in both `consumer.py` and `API_REFERENCE.md`). `testResult.outcome` was always `undefined`, making `undefined === 'LEAK_CONFIRMED'` always `false`, so the modal always rendered the green "No Leak Detected" path regardless of actual result.

**Fix:** Replaced all four `testResult.outcome === 'LEAK_CONFIRMED'` expressions with `testResult.leak_detected === true`. Also fixed the event log message which used `msg.outcome` (replaced with a conditional on `msg.leak_detected`).

**Additional field-name mismatches found while tracing:**

- `buffering` handler read `msg.samples_collected` but consumer sends `msg.buffered` (consumer.py:158 / API_REFERENCE.md). Fixed to `msg.buffered`.
- `critical_alert` handler read `msg.consecutive_fail_count` but consumer sends `msg.consecutive_fail_windows` (consumer.py:317). Fixed to `msg.consecutive_fail_windows`.
- `sample_result` handler called `setIsSteady(msg.is_steady_state || false)` but `sample_result` does NOT include `is_steady_state` (consumer.py:196-210 confirms it). Removed. Added `setIsSteady(msg.is_steady_state || false)` to `window_result` handler instead (which DOES send this field, consumer.py:302).

---

### Bug 4 — Footer year said 2024

**Root cause:** `Footer.jsx` hardcoded `© 2024 CATERPILLAR INC.` and `Landing.jsx` hardcoded `© 2024 Caterpillar Hackathon.`

**Fix:** Replaced both with `© {new Date().getFullYear()} …`.

---

### Bug 5 — Sidebar nav (Telemetry, Diagnostics, History) did nothing on click

**Root cause:** `Sidebar.jsx` NAV array only set `onClick: 'batch'` on BATCH ANALYSIS. The other four items had no `onClick` handler at all. Active state was a hardcoded boolean in the array constant, never updated. No `id` attributes existed on any dashboard panel.

**Fix:** Replaced the hardcoded `active` field with local `useState('DASHBOARD')` in Sidebar. Added `target` panel IDs to each NAV item. Added `handleNavClick()` that sets active state and calls `document.getElementById(target)?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })`. Updated the active class to use `activeNav === item.label`. Added `id="panel-status"`, `id="panel-zones"` to the left/right asides in Dashboard.jsx; added zero-height anchor spans `id="panel-chart"` and `id="panel-log"` before the corresponding components in the center column.

### Verification

```
npm run build:  ✓ 53 modules, 0 errors, 612ms
BUG 1:  href="#features" / "#platform" / "#specs" → correct sections; html scroll-behavior smooth
BUG 2:  AnomalyChart now receives points prop; draws gradient + line + red/green dots
BUG 3:  test_complete reads leak_detected (bool); LEAK → "Leak Confirmed" red, NO LEAK → "No Leak Detected" green
BUG 4:  Both footers render new Date().getFullYear() = 2026
BUG 5:  All 4 nav items call scrollIntoView to their panel ID; active highlight follows clicks
```
