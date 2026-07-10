"""
Pronósticos LSTM — equivalente a modulo6.4-lstm.html.
"""
import plotly.graph_objects as go
import streamlit as st

from core.cache_utils import cache_get_or_compute_mongo, log_resultado
from core.lstm_model import entrenar_lstm_regresor
from core.mercado import TICKERS
from core.session_guard import requiere_sesion

st.set_page_config(page_title="Ernesto Investing AI · LSTM", page_icon="🔮", layout="wide")
requiere_sesion()

st.title("🔮 Pronósticos LSTM")
st.caption("Regresión iterativa a N días calculada con TensorFlow. Se cachea 6 horas en MongoDB.")

col1, col2 = st.columns([1, 2])
with col1:
    ticker = st.radio("Ticker", TICKERS[:3], horizontal=True)
with col2:
    horizonte = st.slider("Horizonte (días)", 7, 60, 30)

with st.spinner(f"Calculando proyección a {horizonte} días para {ticker}…"):
    resultado = cache_get_or_compute_mongo(
        f"lstm:{ticker}:{horizonte}", 6 * 3600, lambda: entrenar_lstm_regresor(ticker, horizonte)
    )

if resultado.get("error"):
    st.error(resultado["error"])
    st.stop()

log_resultado("lstm", f"{ticker}:{horizonte}", resultado)

hist = resultado["historico_validacion"]
fut = resultado["proyeccion_futura"]
met = resultado["metricas_error"]

col_chart, col_kpi = st.columns([3, 1])

with col_chart:
    fechas_hist = [d["fecha"] for d in hist]
    fechas_fut = [d["fecha"] for d in fut]
    all_fechas = fechas_hist + fechas_fut
    null_pad = [None] * len(hist)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=all_fechas, y=[d["real"] for d in hist] + null_pad, name="Real", line=dict(color="#94A3B8")))
    fig.add_trace(go.Scatter(x=all_fechas, y=[d["predicho"] for d in hist] + null_pad, name="Validación", line=dict(color="#38BDF8", dash="dot")))
    fig.add_trace(go.Scatter(x=all_fechas, y=null_pad + [d["prediccion_usd"] for d in fut], name="Proyección", line=dict(color="#C5961A", width=2)))
    fig.add_trace(go.Scatter(x=fechas_fut, y=[d["banda_max"] for d in fut], name="Banda 95%", line=dict(width=0), showlegend=False))
    fig.add_trace(go.Scatter(x=fechas_fut, y=[d["banda_min"] for d in fut], name="Banda 95%", line=dict(width=0), fill="tonexty", fillcolor="rgba(197,150,26,0.15)"))
    fig.update_layout(
        paper_bgcolor="#16294C", plot_bgcolor="#16294C", font=dict(color="#94A3B8", family="monospace"),
        margin=dict(l=40, r=20, t=20, b=30), xaxis=dict(gridcolor="#1F3864"), yaxis=dict(gridcolor="#1F3864"),
        height=420,
    )
    st.plotly_chart(fig, use_container_width=True)

with col_kpi:
    st.markdown("###### Métricas del modelo")
    st.metric("RMSE", f"${met['rmse_usd']:.4f}")
    st.metric("RMSE %", f"{met['rmse_porcentaje']:.2f}%")
    st.metric("MAE", f"${met['mae_usd']:.4f}")
    st.metric("R² Score", f"{met['r2_score']:.4f}")
