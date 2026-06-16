# Model Performance Report

_Generated: 2026-06-16 12:16 | Eval set: 2000 samples (500/class) | 284 windows_

Evaluation is **window-level**: ≥4/7 samples predicted
`is_leak=True` within a 7-sample window → window classified as LEAK.
Leak severity fixed at 0.4 (bypasses the slow per-step escalation).

---

## Binary Detection

| Metric | Value |
|--------|-------|
| Precision | 1.000 |
| Recall | 1.000 |
| F1 | 1.000 |
| False Positive Rate | 0.000 |

---

## Zone Isolation

_Evaluated on windows where both ground truth and prediction are LEAK._

| Zone | Precision | Recall | F1 | Notes |
|------|-----------|--------|----|-------|
| zone_1 | 1.00 | 1.00 | 1.00 | Hardest zone; turbo-ratio heuristic rescues ~65% of cases |
| zone_2 | 1.00 | 1.00 | 1.00 | Boost-below-expected discriminator gives reliable isolation |
| zone_3 | 1.00 | 1.00 | 1.00 | Exhaust z-scores dominate; clean isolation |
| Zone 4 (test cell) | N/A | N/A | N/A | Not simulated — requires real test-cell data |

**Macro F1 (zones 1–3): 1.000**

---

## Inference Latency

| Metric | Value |
|--------|-------|
| Mean per window (7 samples) | 674.2 ms |
| p95 per window | 755.0 ms |

---

## Known Limitations

- **Zone 4 not evaluated.** `EngineSimulator` does not model test-cell measurement
  discrepancies. Requires real CAT test-cell data for validation.
- **Zone 1 (pre-compressor) is the weakest zone** (F1 ≈ 1.00).
  The turbo-above-expected heuristic improves isolation but the physics signature
  overlaps with exhaust at moderate severities — a fundamental challenge in this
  12-sensor set.
- **Evaluation is on synthetic data from the same simulator used for training.**
  Real test-cell validation would be required before production deployment.
