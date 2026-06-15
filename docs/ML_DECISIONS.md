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

1. **Fix the MAF AE feature mismatch** — retrain `nn_model_maf.py` with the inference feature set or fix the inference code to use the training feature set.
2. **Unify the three anomaly thresholds** — single source of truth in constants.py, loaded into all consumers.
3. **Validate on real test-cell data** — collect at minimum 10,000 healthy samples and 5 known-leak sessions from real CAT hardware.
4. **Online calibration** — update the Kalman Q/R parameters and the SVM boundary incrementally as new healthy data arrives from deployed test cells.
5. **Add a time-series model (TCN or LSTM) as a 7th component** — autoencoders are stateless per-sample. A temporal model could detect the *rate of change* of sensor correlations, which is an early-warning signal before threshold crossing.
6. **Replace in-memory channel layer with Redis** — prerequisite for multi-worker WebSocket deployment.
7. **Frontend** — currently the entire frontend directory is a `.gitkeep`.
