# ML Design Decisions — Interview Prep

This document explains *why* each architectural decision was made. The format is question-first because these are the exact questions you will be asked in a technical interview.

---

## 1. Why unsupervised / anomaly detection instead of supervised classification?

**The core problem:** We need to distinguish healthy engine operation from air/exhaust leaks. A naive framing is binary classification (healthy=0, leak=1). We did not use that approach.

**Why not supervised:**
- Real leak data is scarce. CAT test cells occasionally run engines to the point of inducing leaks for validation, but these are rare events. We cannot obtain thousands of labelled leaky examples.
- The physics-based digital twin can synthesize leaks, but any supervised model trained entirely on synthetic data has unknown generalization to real hardware. Calibration between synthetic and real operating points is an open research problem.
- Supervised models fail silently on novel leak patterns. A charge-air leak and an exhaust manifold crack produce different sensor signatures. A classifier trained on three leak types would not generalize to a fourth.

**Why anomaly detection:**
- Healthy engine operation is abundant, reproducible, and characterizable. We can always get more healthy data.
- Any deviation from the learned healthy manifold is potentially anomalous, regardless of which failure mode caused it. This gives generalization "for free."
- Reconstruction-based autoencoders produce a continuous anomaly score (z-score), not a hard label, which enables threshold calibration against acceptable false-positive rates.

---

## 2. Why four separate autoencoders instead of one large model?

**Option A (rejected): One autoencoder with all 12 inputs.**
- A 12-input model is harder to interpret. When it flags an anomaly, you do not know which subsystem is responsible.
- A single large latent space tries to capture healthy correlations between unrelated subsystems (e.g., the injection system and the DPF). Spurious cross-correlations can mask real anomalies in one subsystem when another subsystem is operating normally.

**Option B (chosen): Four domain-aligned autoencoders.**
- **boost:** turbo/boost-circuit sensors — directly detects charge-air leaks upstream of the intercooler.
- **dpf:** DPF/exhaust-post-treatment sensors — directly detects DPF pressure faults and exhaust leaks downstream.
- **maf:** intake air path sensors — detects MAF sensor drift and air path obstructions.
- **exhaust:** exhaust manifold and back-pressure sensors — detects exhaust leaks at the manifold.

Each AE learns correlations only within its domain. A charge-air leak perturbs the boost-circuit channels first; the boost AE sees that immediately while the dpf AE may not react at all. This gives *localization*: we know which subsystem is most anomalous.

**Trade-off:** Four models means four training pipelines, four scaler artifacts, and four inference calls. The overhead is negligible at 12-float inference.

---

## 3. Why a Kalman filter before the autoencoders?

**The problem without filtering:**
Test-cell sensor readings contain:
1. Gaussian measurement noise (sensor electronics).
2. Quantization artifacts (integer-step ADC readings for RPM, VGT position).
3. Transient spikes on engine load changes.

A single noisy sample can produce a large reconstruction error even during healthy operation. Without filtering, the false-positive rate at any reasonable threshold is unacceptably high.

**Why Kalman specifically (vs. exponential moving average, Butterworth, etc.):**
- Kalman is optimal for Gaussian noise with a linear dynamic model (constant velocity). Sensor channels approximately satisfy this during steady-state operation.
- Kalman's two-state model (position + velocity) tracks the trend direction, not just the level. A real leak causes a *sustained drift*, not a *spike*. The velocity state makes the filter resistant to spikes but responsive to trends.
- Unlike a low-pass filter, Kalman has a principled update step that can be tuned per-channel using noise estimates from data (`kalman_tuning.py`).
- EMA has no principled parameterization; its smoothing factor is purely empirical.

**The stability gate (separate mechanism):** Kalman filtering reduces noise, but it does not prevent inference during engine transients (load changes, startup). Transients produce valid reconstruction errors that should not be scored. The stability gate uses coefficient-of-variation on the last 7 samples of RPM, fuel_rate, and boost_pressure to block inference while the engine is changing operating point.

---

## 4. Why One-Class SVM in addition to the autoencoders?

The four autoencoders operate *within* their sensor subsets. A failure mode that affects all channels simultaneously but mildly (e.g., a slow exhaust back-pressure build-up affecting all combustion-related sensors) might produce a low reconstruction error in each individual autoencoder while the *multivariate* distribution clearly shifts.

The One-Class SVM operates on all 12 channels jointly. Its RBF kernel implicitly captures all pairwise interactions. It is trained to classify the healthy joint distribution as the "one class" and will score any point that falls outside the learned boundary as anomalous.

**Why not just Mahalanobis distance for multivariate coverage?**
Mahalanobis assumes a Gaussian joint distribution. Real engine sensor data under varying load conditions is multi-modal (different operating points form different clusters in sensor space). The SVM's RBF kernel handles non-Gaussian distributions better.

---

## 5. Why Mahalanobis distance in addition to SVM?

Mahalanobis distance captures the *directions of maximum variance* in the healthy data. It is interpretable: a large Mahalanobis score means the sample is far from the healthy mean in the directions where healthy data is tightly concentrated. This is useful for diagnosis.

Additionally, Mahalanobis and SVM tend to be sensitive to *different* types of deviations: SVM is better at detecting out-of-convex-hull outliers while Mahalanobis is better at detecting within-envelope but cross-correlation-violating samples.

**Why the 0.3 weight?** During calibration on the healthy-vs-leaky CSV data, Mahalanobis z-scores had a higher baseline than the AE and SVM z-scores during healthy operation. Down-weighting to 0.3 equalizes the contribution to the fused score so that no single component dominates.

---

## 6. Why L2 (root sum of squares) for fusion instead of average or max?

**Average:** Penalizes scenarios where only one component fires strongly. If the SVM fires at z=8 but the four AEs each give z=0.5, the average of 6 values is ~1.6, suggesting normal. But a strong SVM signal is meaningful.

**Max:** Prone to false positives if any single component has a noisy day. A momentary spike in one z-score triggers the whole system.

**L2 fusion:**
- Scales super-linearly: two components firing at z=3 gives a fused score of √18 ≈ 4.2, higher than one component firing at z=6 giving √36 = 6. This rewards *corroboration* from multiple components.
- Provides natural down-weighting via the coefficient: 0.3·z_mahal² reduces Mahalanobis contribution without zeroing it.
- The fusion score has a clear interpretation: it is the Euclidean distance from the origin in a 6D z-score space where each axis is one detection component.

---

## 7. Why a rolling window vote for the leak decision (not per-sample threshold)?

A single sample crossing the threshold could be a measurement artefact, a brief engine transient, or a sensor glitch. Requiring 4 out of 7 consecutive samples to score as anomalous (≥ threshold) before declaring a *window leak* reduces false positives dramatically.

Requiring 2 consecutive leaky windows before declaring `LEAK_CONFIRMED` further reduces the false positive rate: 2 × 7 = 14 samples must predominantly score anomalous.

**The numbers:** Given a ~1% false positive rate per sample (empirically calibrated), the probability of 4/7 samples all being false positives is C(7,4) × 0.01⁴ × 0.99³ ≈ 0.000035, or 1-in-28,000. The probability of this happening in two consecutive windows is ~1-in-800,000,000. This is aggressive enough for production use.

---

## 8. Why synthetic training data (physics-based digital twin)?

**Practical reason:** No real labelled leak dataset was available for this project (hackathon context).

**Technical reason:** A physics-based simulator can generate arbitrarily many samples, can be controlled precisely (inject a precompressor leak at severity 0.3 at timestep 150), and produces ground-truth labels. Real test-cell data would require manual annotation and careful alignment of sensor timestamps with observed physical events.

**Limitations acknowledged:**
- The simulator uses simplified physics (the turbo lag model is a first-order exponential filter with α=0.15, not a full compressor map model).
- Sensor noise is modelled as Gaussian. Real sensors have additional 1/f noise, quantization, and occasional dropouts.
- The simulator does not model engine-to-engine manufacturing variation.
- All models have been validated only on synthetic data. Validation on real CAT test-cell data is required before production use.

---

## 9. What would you change if you had 6 more months?

Items 1 and 2 are now resolved in Phase 3 (see §10).

1. ~~**Fix the MAF AE feature mismatch**~~ — **Fixed in Phase 3**: inference now uses `[rpm, fuel_rate, MAP, MAF, turbo_speed]`, matching the training feature set.
2. ~~**Unify the three anomaly thresholds**~~ — **Fixed in Phase 3**: `ANOMALY_THRESHOLD` loaded from `engine_calibration.pkl`; old `CONSUMER_ANOMALY_THRESHOLD` and `MODEL_STACK_ANOMALY_THRESHOLD` removed.
3. **Validate on real test-cell data** — collect at minimum 10,000 healthy samples and 5 known-leak sessions from real CAT hardware.
4. **Online calibration** — update the Kalman Q/R parameters and the SVM boundary incrementally as new healthy data arrives from deployed test cells.
5. **Add a time-series model (TCN or LSTM) as a 7th component** — autoencoders are stateless per-sample. A temporal model could detect the *rate of change* of sensor correlations, which is an early-warning signal before threshold crossing.
6. **Replace in-memory channel layer with Redis** — prerequisite for multi-worker WebSocket deployment.
7. **Frontend** — currently the entire frontend directory is a `.gitkeep`.

---

## 10. Phase 3 correctness fixes and new components (why)

### 10a. Why the MAF AE was producing wrong scores (and how it was fixed)

The MAF autoencoder training script (`nn_model_maf.py`) selected features in the order `["rpm", "fuel_rate", "MAP", "MAF", "turbo_speed"]` and fit a `StandardScaler` on that data. The scaler stored the mean and variance of each position independently; position 4 was fit on `turbo_speed` values (range: 30 000–150 000 rpm).

At inference, `AE_FEATURES["maf"]` was set to `["rpm", "fuel_rate", "MAP", "IAT", "MAF"]`. This put `IAT` (~300 K) at position 3 and `MAF` at position 4. The scaler applied `turbo_speed` statistics to `IAT` values at position 3, producing a normalized value of roughly `(300 - 90 000) / 30 000 ≈ -3`. This extreme out-of-range value propagated through the autoencoder and produced reconstruction errors around 5–6σ even for perfectly healthy samples. The fix was purely a constant change — correcting `AE_FEATURES["maf"]` to match the training order. No retraining required.

### 10b. Why we unified three anomaly thresholds to one

Three values (6.3156, 3.5, 3.0) existed for historical reasons: the consumer was calibrated from the leaky z-score distribution; the ModelStack threshold was hand-tuned for Streamlit visual sensitivity; the Streamlit display threshold was an arbitrary visual cutoff. This caused the REST endpoint to disagree with the WebSocket consumer on the same sample (z=5.0 would be `is_leak=True` in REST, but not in consumer).

The fix: `ANOMALY_THRESHOLD = 6.3156` loaded from `engine_calibration.pkl` (mean+3σ of leaky scores) is the single decision gate everywhere. The old 3.0 value is preserved as `DISPLAY_COLOR_SCALE_MAX`, explicitly documented as a display-only constant with no bearing on decisions.

### 10c. Why zone isolation uses weighted subsystem z-score voting

Detection tells you *that* a leak exists; isolation tells you *where*. The four autoencoders are already domain-aligned (boost/dpf/maf/exhaust map directly to the four engine zones). Zone isolation is therefore a natural extension: weight each AE's z-score by how much physical relevance that subsystem has to each zone.

**Zone 1 (pre-compressor):** A leak before the compressor reduces mass airflow without affecting boost. `maf_z` fires; `boost_z` stays low. Weight: `zone_1 ← maf:1.0, boost:0.2`.

**Zone 2 (charge-air):** A leak between compressor and intake manifold reduces boost without reducing MAF (MAF sensor is upstream). `boost_z` fires; `maf_z` stays low. Weight: `zone_2 ← boost:1.0, maf:0.2`.

**Zone 3 (exhaust):** EGT anomaly, exhaust backpressure changes, DPF delta changes. `exhaust_z` and `dpf_z` fire. Weight: `zone_3 ← exhaust:1.0, dpf:0.8`.

**Zone 4 (test cell ducting):** Diffuse anomaly that doesn't align clearly with any single subsystem. Scores are spread across all zones; zone 4 scores non-zero contributions from all four AEs equally, making it the winner when nothing dominates.

This approach requires zero additional ML training — it uses scores we already compute.

### 10d. Why physics checks validate rather than replace ML

ML zone voting answers "which zone's sensors are most anomalous?" Physics checks answer "does the cross-channel relationship still make sense?" These are complementary questions.

The mass balance check (AFR = MAF/fuel_rate) catches cases where the ML zone vote is correct but the contamination mechanism is ambiguous. The pressure ratio check (MAP/ambient) is a diagnostic for charge-air circuit integrity that cannot be easily captured by a single AE's reconstruction error.

Physics checks are deliberately conservative: they only *override* the ML zone under one specific rule (zone_1 with MAP/ambient anomaly → upgrade to zone_2). In all other cases they add to the `notes` field without changing the verdict. This avoids replacing a well-calibrated ML signal with a coarser physics rule.

**Limitation:** Both physics checks use approximate thresholds (AFR 15–90, pressure ratio 1.1–2.5). Real diesel engines operating at different load points or altitudes may require per-engine calibration of these bands.

### 10e. Why steady-state gating prevents false positives during transients

An engine acceleration event (e.g. +200 rpm in 2 seconds) produces sensor changes that look structurally similar to a charge-air leak: boost_pressure temporarily drops relative to MAP, MAF increases faster than boost responds (due to turbo lag), EGT spikes. A leak detector without steady-state gating would fire during every load step.

The CV-based gate is effective because steady-state operation has low within-window variation (CV < 1% for RPM), while transients have high variation. The threshold values were set to match the calibration data spread and can be tuned per engine via `SteadyStateDetector.from_config()`.

**Limitation:** The current gate only checks RPM, fuel_rate, MAF, and boost_pressure. A slow drift (e.g. a coolant temperature effect on IAT over minutes) would pass the gate. Long-term trend detection would require a larger window or a dedicated drift detector.

### 10f. Honest limitations of the zone classifier

1. **No training data for zone scoring.** Zone weights in `ZONE_AE_WEIGHTS` are physics-derived, not data-driven. We have no labelled examples of "this test resulted in a zone_1 leak" to validate the weights against.

2. **Zone 4 (test-cell ducting) is speculative.** The signature is defined negatively ("none of the other zones dominated") rather than from a positive physical model. This is the weakest zone definition.

3. **Multiple-zone reporting is conservative.** When two zones are within 15% of each other, we report "multiple" rather than committing to one. This reduces false precision but may frustrate operators who want a single answer.

4. **Validated only on synthetic data.** The EngineSimulator generates precompressor/charge_air/exhaust leaks; it does not generate zone_4 (test cell ducting) scenarios. Zone 4 detection has no synthetic validation path.

5. **Per-sample analysis.** Zone classification runs on one sample at a time inside `predict()`. The consumer averages subsystem z-scores across a window, which is more robust but not the same as running the full verdict chain on each sample.
