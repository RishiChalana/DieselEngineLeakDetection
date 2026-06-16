"""
engine_simulator/app.py — Streamlit dashboard for diesel engine leak detection.

Tabs:
  1. Live Monitor  — real-time simulation, engine zone diagram, z-score charts
  2. Session History — per-window result table and aggregate stats
  3. Batch Analysis — CSV upload → structured Go/No-Go report
  4. Model Info    — health check, threshold, feature lists

All ML is imported directly — no Django API calls.
"""
import sys
import os
import time
from pathlib import Path

# Project root on path before any ml_model imports.
_ROOT = Path(__file__).resolve().parents[1]
_BACKEND = _ROOT / "backend" / "diesel_engine_predictor"
for _p in (_ROOT, _BACKEND):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config.constants import (
    ANOMALY_THRESHOLD,
    DISPLAY_COLOR_SCALE_MAX,
    SENSOR_COLS,
    ZONE_LABELS,
)
from ml_model.data_gen.engine_simulator_core import EngineSimulator
from ml_model.models.model_stack import ModelStack

# SessionReportGenerator is pure Python — no Django dependency.
try:
    from session_analysis.report_generator import SessionReportGenerator
    _REPORT_AVAILABLE = True
except ImportError:
    _REPORT_AVAILABLE = False

# ---------------------------------------------------------------------------
# Page config (must be first Streamlit call)
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Diesel Engine Leak Detection",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
  html, body, [class*="css"] { background-color: #0b0f17; color: #e0e6f0; }
  .zone-box {
    display: inline-block; padding: 8px 14px; border-radius: 8px;
    font-weight: 700; font-size: 13px; margin: 4px; letter-spacing: 0.5px;
  }
  .zone-ok   { background: #0d3b1e; border: 2px solid #1e8c4a; color: #4cde8c; }
  .zone-warn { background: #3b2d00; border: 2px solid #b08000; color: #ffd54f; }
  .zone-crit { background: #3b0000; border: 2px solid #cc2200; color: #ff6b6b; }
  .zone-idle { background: #1a1e2e; border: 2px solid #3a4060; color: #8898bb; }
  .status-ok   { color: #4cde8c; font-size: 28px; font-weight: 800; }
  .status-warn { color: #ffd54f; font-size: 28px; font-weight: 800; }
  .status-crit { color: #ff4444; font-size: 28px; font-weight: 800; }
  .engine-diagram { font-family: monospace; line-height: 1.8; font-size: 14px; }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Cached singleton — same behaviour as Django's ModelStack singleton
# ---------------------------------------------------------------------------

@st.cache_resource
def get_model_stack() -> ModelStack:
    return ModelStack()


# ---------------------------------------------------------------------------
# Session state initialisation
# ---------------------------------------------------------------------------

_defaults = {
    "simulator": EngineSimulator(seed=0),
    "history": [],          # list of predict() result dicts
    "running": False,
    "leak_type": None,      # None = healthy
    "window_counter": 0,
    "batch_report": None,
}
for k, v in _defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

ms = get_model_stack()
sim: EngineSimulator = st.session_state.simulator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ZONE_ORDER = ["zone_1", "zone_2", "zone_3", "zone_4"]

_ZONE_DISPLAY = {
    "zone_1": "Zone 1 — Pre-compressor",
    "zone_2": "Zone 2 — Charge-air",
    "zone_3": "Zone 3 — Exhaust path",
    "zone_4": "Zone 4 — Test ducting",
}


def _zone_css(score: float, detected: bool) -> str:
    if not detected:
        return "zone-idle"
    if score >= 0.5:
        return "zone-crit"
    if score >= 0.25:
        return "zone-warn"
    return "zone-ok"


def _status_css(flag: str) -> str:
    return {"FAIL": "status-crit", "WARNING": "status-warn"}.get(flag, "status-ok")


def _engine_diagram_html(isolation: dict, detected: bool) -> str:
    zone_scores = isolation.get("zone_scores", {})
    top = isolation.get("detected_zone", "none")

    def box(zone: str, label: str) -> str:
        score = zone_scores.get(zone, 0.0)
        css = _zone_css(score, detected and top in (zone, "multiple"))
        pct = f"{score * 100:.0f}%"
        return f'<span class="zone-box {css}">{label}<br><small>{pct}</small></span>'

    arrow = '<span style="color:#4a6080;margin:0 6px;">→</span>'
    nl = "<br>"

    return f"""
<div class="engine-diagram">
  <b style="color:#8898bb;font-size:12px;">ENGINE CIRCUIT — ZONE CONFIDENCE</b>{nl}{nl}
  [AIR&nbsp;INLET]
  {arrow}
  {box("zone_1", "Z1 Pre-comp")}
  {arrow}
  [COMPRESSOR]
  {arrow}
  {box("zone_2", "Z2 Charge-air")}
  {nl}
  <span style="margin-left:340px;color:#4a6080;">↓ intake ports</span>{nl}
  <span style="margin-left:340px;">[CYLINDERS&nbsp;&amp;&nbsp;COMBUSTION]</span>{nl}
  <span style="margin-left:340px;color:#4a6080;">↓ exhaust</span>{nl}
  {box("zone_4", "Z4 Test-cell")}
  {arrow}
  [DPF/SCR]
  {arrow}
  {box("zone_3", "Z3 Exhaust")}
  {arrow}
  [TURBO&nbsp;TURBINE]
</div>
"""


# ---------------------------------------------------------------------------
# Tab layout
# ---------------------------------------------------------------------------

tab_live, tab_history, tab_batch, tab_info = st.tabs(
    ["Live Monitor", "Session History", "Batch Analysis", "Model Info"]
)


# ===========================================================================
# TAB 1 — Live Monitor
# ===========================================================================

with tab_live:
    st.subheader("Live Engine Monitor")

    ctrl_col1, ctrl_col2, ctrl_col3, ctrl_col4, ctrl_col5 = st.columns(5)
    with ctrl_col1:
        if st.button("Start", use_container_width=True):
            st.session_state.running = True
    with ctrl_col2:
        if st.button("Stop", use_container_width=True):
            st.session_state.running = False
    with ctrl_col3:
        if st.button("Reset Sim", use_container_width=True):
            st.session_state.simulator = EngineSimulator(seed=int(time.time()))
            st.session_state.history = []
            st.session_state.leak_type = None
            sim = st.session_state.simulator
    with ctrl_col4:
        if st.button("Set Healthy", use_container_width=True):
            sim.set_healthy()
            st.session_state.leak_type = None
    with ctrl_col5:
        leak_choice = st.selectbox(
            "Introduce Leak",
            ["(none)", "precompressor", "charge_air", "exhaust"],
            label_visibility="collapsed",
        )
        if leak_choice != "(none)" and st.session_state.leak_type != leak_choice:
            sim.introduce_leak(leak_type=leak_choice)
            st.session_state.leak_type = leak_choice

    update_interval = st.slider(
        "Update interval (s)", 0.3, 3.0, 0.8, 0.1,
        key="interval_slider",
    )

    # --- Live inference step ---
    if st.session_state.running:
        sample = sim.step()
        result = ms.predict(sample)
        st.session_state.history.append(result)
        if len(st.session_state.history) > 300:
            st.session_state.history = st.session_state.history[-300:]

    # Display from last history entry
    current = st.session_state.history[-1] if st.session_state.history else None

    if current:
        det = current["detection"]
        dec = current["decision"]
        iso = current.get("isolation", {})
        flag = dec.get("flag", "PASS")
        z_cum = det["z_cumulative"]
        is_leak = det["is_leak"]

        # --- Status banner ---
        st.markdown(
            f'<div class="{_status_css(flag)}">'
            f'{flag} &nbsp; z={z_cum:.3f} / {ANOMALY_THRESHOLD:.2f}'
            f'</div>',
            unsafe_allow_html=True,
        )

        # --- Engine diagram + zone bar ---
        diag_col, bar_col = st.columns([3, 2])
        with diag_col:
            st.markdown(
                _engine_diagram_html(iso, is_leak),
                unsafe_allow_html=True,
            )
        with bar_col:
            zone_scores = iso.get("zone_scores", {z: 0.0 for z in _ZONE_ORDER})
            bar_fig = go.Figure(go.Bar(
                x=[zone_scores.get(z, 0.0) for z in _ZONE_ORDER],
                y=[_ZONE_DISPLAY[z] for z in _ZONE_ORDER],
                orientation="h",
                marker_color=["#4cde8c", "#4cde8c", "#4cde8c", "#4cde8c"],
                marker_line_color="#ffffff22",
            ))
            bar_fig.update_layout(
                template="plotly_dark",
                height=220,
                margin=dict(l=10, r=10, t=30, b=10),
                title=dict(text="Zone Confidence", font_size=13),
                xaxis=dict(range=[0, 1], title="normalised score"),
                yaxis=dict(tickfont=dict(size=11)),
            )
            st.plotly_chart(bar_fig, use_container_width=True)

        # --- Metric row ---
        m1, m2, m3, m4, m5, m6 = st.columns(6)
        sz = det["subsystem_z"]
        m1.metric("boost_z", f"{sz['boost']:.3f}")
        m2.metric("maf_z",   f"{sz['maf']:.3f}")
        m3.metric("exhaust_z", f"{sz['exhaust']:.3f}")
        m4.metric("dpf_z",  f"{sz['dpf']:.3f}")
        m5.metric("svm_z",  f"{det['svm_z']:.3f}")
        m6.metric("mahal_z", f"{det['mahal_z']:.3f}")

    # --- z_cumulative trend ---
    if len(st.session_state.history) > 2:
        hist = st.session_state.history
        z_vals = [h["detection"]["z_cumulative"] for h in hist]
        confidence_vals = [h["detection"]["confidence"] for h in hist]

        trend = go.Figure()
        trend.add_trace(go.Scatter(
            y=z_vals, mode="lines", name="z_cumulative",
            line=dict(color="#00ccff", width=2),
        ))
        trend.add_trace(go.Scatter(
            y=[v * ANOMALY_THRESHOLD * 2 for v in confidence_vals],
            mode="lines", name="confidence×scale",
            line=dict(color="#ff8c00", width=1, dash="dot"),
        ))
        trend.add_hline(
            y=ANOMALY_THRESHOLD, line_dash="dash",
            line_color="#ff4444", annotation_text=f"threshold {ANOMALY_THRESHOLD:.2f}",
        )
        trend.update_layout(
            template="plotly_dark", height=280,
            title="Anomaly Score over Time",
            yaxis_title="z_cumulative",
            xaxis_title="sample index",
            margin=dict(l=10, r=10, t=40, b=30),
            legend=dict(orientation="h", y=-0.15),
        )
        st.plotly_chart(trend, use_container_width=True)

    # Auto-rerun when streaming
    if st.session_state.running:
        time.sleep(update_interval)
        st.rerun()


# ===========================================================================
# TAB 2 — Session History
# ===========================================================================

with tab_history:
    st.subheader("Session History")

    hist = st.session_state.history
    if not hist:
        st.info("No history yet. Start the Live Monitor to collect data.")
    else:
        rows = []
        for i, h in enumerate(hist):
            det = h["detection"]
            dec = h["decision"]
            iso = h.get("isolation", {})
            rows.append({
                "sample": i,
                "is_leak": det["is_leak"],
                "z_cumulative": round(det["z_cumulative"], 3),
                "boost_z": round(det["subsystem_z"]["boost"], 3),
                "maf_z": round(det["subsystem_z"]["maf"], 3),
                "exhaust_z": round(det["subsystem_z"]["exhaust"], 3),
                "dpf_z": round(det["subsystem_z"]["dpf"], 3),
                "svm_z": round(det["svm_z"], 3),
                "mahal_z": round(det["mahal_z"], 3),
                "flag": dec.get("flag", "PASS"),
                "severity": dec.get("severity", "none"),
                "zone": iso.get("detected_zone", "—"),
            })
        df = pd.DataFrame(rows)

        # Summary metrics
        leak_pct = df["is_leak"].mean() * 100
        max_z = df["z_cumulative"].max()
        fail_n = (df["flag"] == "FAIL").sum()

        s1, s2, s3, s4 = st.columns(4)
        s1.metric("Samples", len(df))
        s2.metric("Leak rate", f"{leak_pct:.1f}%")
        s3.metric("Max z_cumulative", f"{max_z:.2f}")
        s4.metric("FAIL windows", int(fail_n))

        st.dataframe(
            df.style.apply(
                lambda row: [
                    "background-color: #3b0000" if row["flag"] == "FAIL"
                    else "background-color: #3b2d00" if row["flag"] == "WARNING"
                    else ""
                ] * len(row),
                axis=1,
            ),
            use_container_width=True,
            height=400,
        )

        if st.button("Clear History"):
            st.session_state.history = []
            st.rerun()


# ===========================================================================
# TAB 3 — Batch Analysis
# ===========================================================================

with tab_batch:
    st.subheader("Batch Session Analysis")
    st.caption(
        "Upload a CSV file with header row containing all 12 sensor channels. "
        "Returns a Go/No-Go report across the full session."
    )

    st.code("Required columns:\n" + "  " + ", ".join(SENSOR_COLS), language="text")

    uploaded = st.file_uploader("Upload session CSV", type=["csv"])

    if uploaded is not None:
        try:
            df_up = pd.read_csv(uploaded)
        except Exception as exc:
            st.error(f"CSV parse error: {exc}")
            df_up = None

        if df_up is not None:
            missing = [c for c in SENSOR_COLS if c not in df_up.columns]
            if missing:
                st.error(f"Missing columns: {missing}")
            else:
                st.success(f"Loaded {len(df_up)} rows × {len(df_up.columns)} columns.")

                if st.button("Run Analysis", type="primary"):
                    with st.spinner("Running inference on all rows…"):
                        per_sample = []
                        prog = st.progress(0.0)
                        n = len(df_up)
                        for idx, (_, row) in enumerate(df_up[SENSOR_COLS].iterrows()):
                            sensor_dict = {col: float(row[col]) for col in SENSOR_COLS}
                            per_sample.append(ms.predict(sensor_dict))
                            if idx % max(1, n // 100) == 0:
                                prog.progress((idx + 1) / n)
                        prog.progress(1.0)

                    if _REPORT_AVAILABLE:
                        report = SessionReportGenerator().generate(per_sample)
                        st.session_state.batch_report = report
                    else:
                        # Minimal fallback when SessionReportGenerator not importable
                        leak_count = sum(
                            1 for r in per_sample if r["detection"]["is_leak"]
                        )
                        go_nogo = "NO-GO" if leak_count / len(per_sample) >= 0.2 else "GO"
                        st.session_state.batch_report = {
                            "header": {
                                "go_nogo": go_nogo,
                                "sample_count": len(per_sample),
                                "verdict_summary": f"{leak_count} leaky samples.",
                            }
                        }

    report = st.session_state.batch_report
    if report:
        hdr = report.get("header", {})
        go_nogo = hdr.get("go_nogo", "?")
        verdict_color = "#ff4444" if go_nogo == "NO-GO" else (
            "#ffd54f" if go_nogo == "CAUTION" else "#4cde8c"
        )
        st.markdown(
            f'<h2 style="color:{verdict_color};">{go_nogo}</h2>',
            unsafe_allow_html=True,
        )
        st.write(hdr.get("verdict_summary", ""))

        summ = report.get("session_summary", {})
        if summ:
            b1, b2, b3, b4 = st.columns(4)
            b1.metric("Samples", hdr.get("sample_count"))
            b2.metric("Leak rate", f"{summ.get('leak_rate_pct', 0):.1f}%")
            b3.metric("Max z_cumulative", f"{summ.get('max_z_cumulative', 0):.2f}")
            b4.metric("FAIL windows", summ.get("fail_count", 0))

        leak_an = report.get("leak_analysis", {})
        zone_bd = leak_an.get("zone_breakdown", {})
        if zone_bd:
            st.markdown("#### Zone Breakdown")
            batch_bar = go.Figure(go.Bar(
                x=list(zone_bd.keys()),
                y=[v["pct"] for v in zone_bd.values()],
                marker_color="#00ccff",
                text=[f"{v['pct']:.1f}%" for v in zone_bd.values()],
                textposition="auto",
            ))
            batch_bar.update_layout(
                template="plotly_dark", height=260,
                yaxis_title="% of samples",
                title="Zone distribution across session",
                margin=dict(l=10, r=10, t=40, b=10),
            )
            st.plotly_chart(batch_bar, use_container_width=True)

        rec = report.get("recommendation", {})
        if rec:
            st.markdown("#### Recommendation")
            st.info(rec.get("action", ""))
            if rec.get("escalate_immediately"):
                st.error("ESCALATE IMMEDIATELY — stop test and notify supervisor.")

        if _REPORT_AVAILABLE:
            st.markdown("#### Full Text Report")
            text = SessionReportGenerator.to_text_summary(report)
            st.code(text, language="text")


# ===========================================================================
# TAB 4 — Model Info
# ===========================================================================

with tab_info:
    st.subheader("Model & Pipeline Information")

    health = ms.health_check()
    all_ok = health.get("all_loaded", False)
    if all_ok:
        st.success("All model components loaded successfully.")
    else:
        st.error("One or more model components failed to load.")

    comps = health.get("components", {})
    if comps:
        rows_h = [{"component": k, "status": ("OK" if v else "FAIL")} for k, v in comps.items()]
        st.dataframe(pd.DataFrame(rows_h), use_container_width=True, hide_index=True)

    st.markdown("#### Anomaly Threshold")
    st.code(f"ANOMALY_THRESHOLD = {ANOMALY_THRESHOLD:.6f}  (loaded from engine_calibration.pkl)")
    st.caption("Mean + 3σ of leaky z_cumulative distribution from calibration run.")

    st.markdown("#### Sensor Channels")
    st.code("SENSOR_COLS = " + str(SENSOR_COLS))

    st.markdown("#### Zone Definitions")
    for zone, label in ZONE_LABELS.items():
        st.markdown(f"- **{zone}**: {label}")

    st.markdown("#### ML Pipeline")
    st.markdown("""
1. Raw 12-channel sample → **KalmanLayer** (per-channel noise smoothing)
2. Smoothed channels → **4 Autoencoders** (boost, dpf, maf, exhaust; per-subsystem z-scores)
3. All 12 channels → **One-Class SVM** (multivariate outlier z-score)
4. All 12 channels → **Mahalanobis distance** (covariance-aware z-score)
5. Fusion: `z_cum = √(boost² + dpf² + maf² + exhaust² + 0.3·mahal² + svm²)`
6. Decision: `z_cum ≥ ANOMALY_THRESHOLD` → anomalous sample
7. Zone isolation: weighted AE voting + turbo/boost physics checks
""")
