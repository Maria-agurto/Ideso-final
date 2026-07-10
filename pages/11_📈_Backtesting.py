"""
Backtesting histórico — equivalente a modulo6.11-backtesting.html.
El notebook no incluye un backtester real todavía (el propio index.html
original lo marcaba como "simulado por diseño, podría mejorarse con
señales SVC reales"), así que se mantiene la simulación, pero con semilla
fija para que sea reproducible en Streamlit.
"""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core.session_guard import requiere_sesion

st.set_page_config(page_title="Ernesto Investing AI · Backtesting", page_icon="📈", layout="wide")
requiere_sesion()

st.title("📈 Backtesting Histórico")
st.caption("⚪ Simulado por diseño: podría mejorarse alimentándolo con las señales reales del clasificador SVC.")

rng = np.random.default_rng(42)
dates = pd.date_range(end=pd.Timestamp.today(), periods=250, freq="D")
equity_ai = [10000.0]
equity_bh = [10000.0]
for _ in range(249):
    ret_bh = (rng.random() - 0.48) * 0.02
    ret_ai = (rng.random() - 0.42) * 0.018
    equity_bh.append(equity_bh[-1] * (1 + ret_bh))
    equity_ai.append(equity_ai[-1] * (1 + ret_ai))
equity_ai[-1] = 14250.0
equity_bh[-1] = 11820.0

col_chart, col_kpi = st.columns([3, 1])

with col_chart:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=dates, y=equity_ai, name="Estrategia IA", line=dict(color="#E4B94E", width=2.5), fill="tozeroy", fillcolor="rgba(228,185,78,0.1)"))
    fig.add_trace(go.Scatter(x=dates, y=equity_bh, name="Buy & Hold", line=dict(color="#64748B", width=1.5, dash="dot")))
    fig.update_layout(
        paper_bgcolor="#16294C", plot_bgcolor="#16294C", font=dict(color="#94A3B8", family="monospace"),
        margin=dict(l=50, r=20, t=20, b=40), xaxis=dict(gridcolor="#1F3864"),
        yaxis=dict(gridcolor="#1F3864", tickprefix="$"),
        legend=dict(orientation="h", y=1.1), height=420,
    )
    st.plotly_chart(fig, use_container_width=True)

with col_kpi:
    st.markdown("###### Estrategia IA")
    st.metric("Retorno total", "+42.5%")
    st.write("Max Drawdown: **-12.3%**")
    st.write("Win Rate: **68%**")
    st.write("Factor de beneficio: **1.85**")
    st.divider()
    st.markdown("###### Buy & Hold (Benchmark)")
    st.metric("Retorno total", "+18.2%")
    st.write("Max Drawdown: **-24.8%**")
