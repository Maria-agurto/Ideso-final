"""
Clasificador SVC — equivalente a modulo_svc.html.
"""
import plotly.graph_objects as go
import streamlit as st

from core.cache_utils import cache_get_or_compute_mongo, log_resultado
from core.mercado import TICKERS
from core.session_guard import requiere_sesion
from core.svc_model import entrenar_svc

st.set_page_config(page_title="Ernesto Investing AI · SVC", page_icon="🤖", layout="wide")
requiere_sesion()

st.title("🤖 Clasificador SVC")
st.caption("SVM con GridSearchCV + validación temporal (TimeSeriesSplit). Señal BUY/SELL para el día siguiente.")

ticker = st.selectbox("Ticker", TICKERS)

with st.spinner(f"Entrenando SVC para {ticker}… (se cachea 1 hora en MongoDB)"):
    resultado = cache_get_or_compute_mongo(f"svc:{ticker}", 3600, lambda: entrenar_svc(ticker))

if resultado.get("error"):
    st.error(resultado["error"])
    st.stop()

log_resultado("svc", ticker, resultado)

pred = resultado["prediccion"]
metricas = resultado["metricas"]
senal = pred["señal"]

col_senal, col_prob = st.columns([2, 1])
with col_senal:
    if senal == "BUY":
        st.success(f"### 📈 Señal: BUY  ({ticker})")
    else:
        st.error(f"### 📉 Señal: SELL  ({ticker})")
    st.caption(f"Fecha de la última vela usada: {pred['fecha']}")
with col_prob:
    st.metric("Probabilidad de BUY", f"{pred['probabilidad_buy'] * 100:.1f}%")

st.divider()
st.markdown("###### Métricas de evaluación del modelo (sobre el conjunto de test)")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Accuracy", f"{metricas['accuracy'] * 100:.1f}%")
c2.metric("Precision", f"{metricas['precision'] * 100:.1f}%")
c3.metric("Recall", f"{metricas['recall'] * 100:.1f}%")
c4.metric("F1-Score", f"{metricas['f1'] * 100:.1f}%")

st.caption(
    f"Mejores hiperparámetros (GridSearchCV): `{metricas['mejores_hiperparametros']}` · "
    f"F1 en CV: {metricas['f1_cv']:.3f} · train={metricas['n_train']} / test={metricas['n_test']}"
)

st.markdown("###### Matriz de confusión")
matriz = metricas["matriz_confusion"]
etiquetas = ["SELL", "BUY"]
z = list(reversed(matriz))
y_inv = list(reversed(etiquetas))

fig = go.Figure(data=go.Heatmap(
    z=z, x=etiquetas, y=y_inv,
    colorscale=[[0, "#12203C"], [1, "#C5961A"]],
    showscale=False, text=z, texttemplate="%{text}", textfont=dict(size=22, color="#FFFFFF"),
    hovertemplate="Real: %{y}<br>Predicho: %{x}<br>Casos: %{z}<extra></extra>",
))
fig.update_layout(
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#CBD5E1", family="monospace"),
    margin=dict(t=20, l=70, r=20, b=50),
    xaxis=dict(title="Predicción del modelo"), yaxis=dict(title="Clase real"),
    height=380,
)
st.plotly_chart(fig, use_container_width=True)
