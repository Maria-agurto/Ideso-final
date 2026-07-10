"""
Core Predictivo — orquestador que consolida LSTM/BiLSTM/GRU/SimpleRNN.
Equivalente a modulo6.6-core-predictivo-central.html (antes dependía de
/api/rnns aún no implementado en el backend; ahora se calcula localmente).
"""
import pandas as pd
import streamlit as st

from core.cache_utils import cache_get_or_compute_mongo, log_resultado
from core.mercado import TICKERS
from core.rnn_model import entrenar_rnns
from core.session_guard import requiere_sesion

st.set_page_config(page_title="Ernesto Investing AI · Core Predictivo", page_icon="🧠", layout="wide")
requiere_sesion()

st.title("🧠 Core Predictivo — Ensamble de RNNs")
st.caption("Compara LSTM, BiLSTM, GRU y SimpleRNN prediciendo la dirección del precio para mañana. Se cachea 6 horas en MongoDB.")

ticker = st.radio("Ticker", TICKERS[:3], horizontal=True)

with st.spinner(f"Entrenando el ensamble de RNNs para {ticker}… esto puede tardar un momento."):
    resultado = cache_get_or_compute_mongo(f"rnns:{ticker}", 6 * 3600, lambda: entrenar_rnns(ticker))

if resultado.get("error"):
    st.warning(resultado["error"])
    st.stop()

log_resultado("rnns", ticker, resultado)

st.caption(f"Última actualización: {resultado['ultima_actualizacion']} UTC")

modelos = resultado["modelos"]
filas = []
for kind, datos in modelos.items():
    filas.append({
        "Modelo": kind.upper(),
        "Señal": datos["senal"],
        "Prob. mañana": f"{datos['probabilidad_mañana'] * 100:.1f}%",
        "Accuracy": f"{datos['metricas']['accuracy'] * 100:.1f}%",
        "Precision": f"{datos['metricas']['precision'] * 100:.1f}%",
        "Recall": f"{datos['metricas']['recall'] * 100:.1f}%",
        "F1": f"{datos['metricas']['f1'] * 100:.1f}%",
    })

df_tabla = pd.DataFrame(filas)
st.dataframe(df_tabla, use_container_width=True, hide_index=True)

cols = st.columns(len(modelos))
for col, (kind, datos) in zip(cols, modelos.items()):
    with col:
        emoji = "📈" if datos["senal"] == "BUY" else ("📉" if datos["senal"] == "SELL" else "➖")
        st.metric(kind.upper(), f"{emoji} {datos['senal']}", f"{datos['probabilidad_mañana'] * 100:.1f}% prob.")
