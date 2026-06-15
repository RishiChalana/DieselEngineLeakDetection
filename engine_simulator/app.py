"""
Engine Leak Detection Simulator - Production Architecture.
Pipeline: EngineSimulator -> KalmanLayer -> ModelStack
final_score = max(physics_score, svm_z, ae_z)
"""
import sys
import os
import time

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

import streamlit as st
import plotly.graph_objects as go
import numpy as np
import pandas as pd

from ml_model.data_gen.engine_simulator_core import EngineSimulator
from ml_model.kalman.kalman_layer import KalmanLayer
from ml_model.models.model_stack import ModelStack

# -------------------------------------------------
# PAGE CONFIG
# -------------------------------------------------

st.set_page_config(layout="wide")

st.markdown("""
<style>
html, body, [class*="css"] {
    background-color: #0b0f17;
    color: white;
}
.big-card {
    background: rgba(255,255,255,0.03);
    padding: 20px;
    border-radius: 15px;
    box-shadow: 0 0 25px rgba(0,255,255,0.08);
}
.metric-title {
    font-size: 20px;
    font-weight: 600;
    color: #00f5ff;
}
</style>
""", unsafe_allow_html=True)

st.title("Engine Leak Detection - Production Stack")
st.caption("Pipeline: EngineSimulator → Kalman → ModelStack (Residual + SVM + Autoencoder)")

# -------------------------------------------------
# INIT
# -------------------------------------------------

THRESHOLD = 3

if "engine" not in st.session_state:
    st.session_state.engine = EngineSimulator()

if "kalman" not in st.session_state:
    st.session_state.kalman = KalmanLayer()

if "model_stack" not in st.session_state:
    st.session_state.model_stack = ModelStack()

if "history" not in st.session_state:
    st.session_state.history = []

if "running" not in st.session_state:
    st.session_state.running = False

if "use_simulator" not in st.session_state:
    st.session_state.use_simulator = True

engine = st.session_state.engine
kalman = st.session_state.kalman
model_stack = st.session_state.model_stack

# -------------------------------------------------
# CONTROL PANEL
# -------------------------------------------------

colA, colB, colC, colD = st.columns(4)

with colA:
    if st.button("Start Streaming"):
        st.session_state.running = True

with colB:
    if st.button("Stop"):
        st.session_state.running = False

with colC:
    if st.button("Healthy Mode"):
        engine.set_healthy()

with colD:
    if st.button("Introduce Leak"):
        engine.introduce_leak()

interval = st.slider("Update Interval (seconds)", 0.5, 5.0, 1.0, 0.5)
use_simulator = st.checkbox("Use EngineSimulator (sequential)", value=True)
st.session_state.use_simulator = use_simulator

# -------------------------------------------------
# SAMPLE SOURCE
# -------------------------------------------------

if st.session_state.running and use_simulator:
    sample = engine.step()
else:
    rpm = st.slider("RPM", 800, 2200, 1600)
    fuel_rate = st.slider("Fuel Rate", 5.0, 120.0, 75.0)
    turbo_speed = st.slider("Turbo Speed", 60000.0, 140000.0, 90000.0)
    boost_pressure = st.slider("Boost Pressure", 0.0, 1.8, 1.2)
    MAP = st.slider("MAP", 0.9, 3.0, 2.2)
    MAF = st.slider("MAF", 100.0, 900.0, 500.0)
    exhaust_pressure = st.slider("Exhaust Pressure", 1.1, 3.5, 2.5)
    DPF_delta = st.slider("DPF Delta", 5000.0, 60000.0, 20000.0)
    ambient_pressure = st.slider("Ambient Pressure", 0.9, 1.05, 1.0)
    sample = {
        "rpm": rpm,
        "fuel_rate": fuel_rate,
        "turbo_speed": turbo_speed,
        "boost_pressure": boost_pressure,
        "MAP": MAP,
        "IAT": 305,
        "MAF": MAF,
        "EGT": 650,
        "exhaust_pressure": exhaust_pressure,
        "VGT": 50,
        "DPF_delta": DPF_delta,
        "ambient_pressure": ambient_pressure,
    }
    if st.session_state.running:
        sample["rpm"] += np.random.uniform(-10, 10)
        sample["fuel_rate"] += np.random.uniform(-2, 2)
        sample["boost_pressure"] += np.random.uniform(-0.05, 0.05)

# -------------------------------------------------
# PIPELINE: Kalman -> ModelStack
# -------------------------------------------------

filtered = kalman.filter(sample)
result = model_stack.evaluate(filtered)
final_score = result["final_score"]

st.session_state.history.append(result)
if len(st.session_state.history) > 200:
    st.session_state.history = st.session_state.history[-200:]

# -------------------------------------------------
# STATUS (final_score >= 3 = alert)
# -------------------------------------------------

if final_score < THRESHOLD:
    status = "HEALTHY"
    color = "#0f3d0f"
elif final_score < 6:
    status = "SUBTLE LEAK"
    color = "#5c5c00"
else:
    status = "CRITICAL LEAK"
    color = "#5c0000"

st.markdown(f"""
<div class="big-card">
    <div class="metric-title">System Status</div>
    <h2>{status}</h2>
    <h3>Final Score: {final_score:.3f} (threshold={THRESHOLD})</h3>
</div>
""", unsafe_allow_html=True)

# -------------------------------------------------
# SCORE CARDS
# -------------------------------------------------

st.markdown("### Score Breakdown")
c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    st.metric("Physics Score", f"{result['physics_score']:.2f}", help="max(boost_z, maf_z, exhaust_z, dpf_z)")
with c2:
    st.metric("SVM z", f"{result['svm_z']:.2f}", help="One-Class SVM anomaly score")
with c3:
    st.metric("AE z", f"{result['ae_z']:.2f}", help="Autoencoder reconstruction z-score")
with c4:
    st.metric("Final Score", f"{result['final_score']:.2f}", help="max(physics, svm_z, ae_z)")
with c5:
    st.metric("Status", status)

# -------------------------------------------------
# RADAR (4 residual z-scores)
# -------------------------------------------------

categories = ["Boost", "MAF", "Exhaust", "DPF"]
z_vals = [result["boost_z"], result["maf_z"], result["exhaust_z"], result["dpf_z"]]
radar = go.Figure()
radar.add_trace(go.Scatterpolar(
    r=z_vals,
    theta=categories,
    fill="toself",
    line=dict(color="#00f5ff", width=3),
))
radar.update_layout(
    polar=dict(radialaxis=dict(visible=True, range=[0, max(10, max(z_vals) + 2)])),
    template="plotly_dark",
    height=350,
    title="Residual Z-Scores",
)
st.plotly_chart(radar, use_container_width=True)

# -------------------------------------------------
# GAUGE
# -------------------------------------------------

gauge = go.Figure(go.Indicator(
    mode="gauge+number",
    value=final_score,
    gauge={
        "axis": {"range": [0, 15]},
        "bar": {"color": "#00f5ff"},
        "steps": [
            {"range": [0, 3], "color": "#0f3d0f"},
            {"range": [3, 6], "color": "#5c5c00"},
            {"range": [6, 15], "color": "#5c0000"},
        ],
    },
))
gauge.update_layout(height=300, template="plotly_dark", title="Final Anomaly Score")
st.plotly_chart(gauge, use_container_width=True)

# -------------------------------------------------
# TREND
# -------------------------------------------------

if len(st.session_state.history) > 2:
    df = pd.DataFrame(st.session_state.history)
    trend = go.Figure()
    trend.add_trace(go.Scatter(
        y=df["final_score"],
        mode="lines",
        name="Final",
        line=dict(color="#ff004c", width=3),
    ))
    trend.add_trace(go.Scatter(
        y=df["physics_score"],
        mode="lines",
        name="Physics",
        line=dict(color="#00f5ff", width=1),
    ))
    trend.add_hline(y=THRESHOLD, line_dash="dash", line_color="yellow")
    trend.update_layout(template="plotly_dark", height=300, title="Score Trend")
    st.plotly_chart(trend, use_container_width=True)

# -------------------------------------------------
# AUTO RERUN
# -------------------------------------------------

if st.session_state.running:
    time.sleep(interval)
    st.rerun()
