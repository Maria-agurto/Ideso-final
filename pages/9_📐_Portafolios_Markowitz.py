"""
Optimización de portafolios — equivalente a modulo6.9-portafolio.html,
pero con el cálculo Markowitz REAL del notebook (antes el HTML mostraba
una nube simulada; acá pesos y frontera salen de datos reales de Yahoo
Finance vía core/portafolio.py).
"""
import plotly.graph_objects as go
import streamlit as st

from core.cache_utils import log_resultado
from core.mercado import TICKERS
from core.portafolio import optimizar_portafolio
from core.session_guard import requiere_sesion

st.set_page_config(page_title="Ernesto Investing AI · Portafolios", page_icon="📐", layout="wide")
requiere_sesion()

st.title("📐 Optimización de Portafolios")
st.caption("Rebalanceo mediante teoría de varianza media de Markowitz (scipy.optimize), sobre retornos reales de Yahoo Finance.")

st.markdown("###### Tu asignación actual (%)")
cols = st.columns(len(TICKERS))
pesos_actuales = {}
default_pesos = {"FSM": 35, "BHP": 25, "ABX.TO": 20, "BVN": 15, "VOLCABC1.LM": 5}
for col, tk in zip(cols, TICKERS):
    with col:
        pesos_actuales[tk] = st.number_input(tk, min_value=0, max_value=100, value=default_pesos.get(tk, 0), key=f"peso_{tk}")

with st.spinner("Calculando frontera eficiente y pesos óptimos…"):
    resultado = optimizar_portafolio(pesos_actuales)

log_resultado("portafolio", "optimizar", resultado)

c1, c2, c3 = st.columns(3)
c1.metric("Retorno esperado (óptimo)", f"{resultado['optimo']['retorno']}%")
c2.metric("Volatilidad (óptimo)", f"{resultado['optimo']['riesgo']}%")
sharpe_opt = resultado["ratios"]["optimizado"]["sharpe"]
c3.metric("Ratio de Sharpe (óptimo)", f"{sharpe_opt}")

col_pesos, col_frontera = st.columns([1, 2])

with col_pesos:
    st.markdown("###### Asignación óptima")
    for tk, peso in resultado["optimo"]["pesos"].items():
        st.write(f"**{tk}**  ·  {peso}%")
        st.progress(min(1.0, peso / 100))

with col_frontera:
    st.markdown("###### Frontera eficiente (Monte Carlo, Dirichlet)")
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=resultado["frontera"]["riesgo"], y=resultado["frontera"]["retorno"],
        mode="markers", marker=dict(size=5, color=resultado["frontera"]["retorno"], colorscale="Viridis", showscale=True),
        name="Portafolios simulados",
    ))
    fig.add_trace(go.Scatter(
        x=[resultado["optimo"]["riesgo"]], y=[resultado["optimo"]["retorno"]],
        mode="markers", marker=dict(symbol="star", size=16, color="#E4B94E", line=dict(width=1, color="#FFFFFF")),
        name="Óptimo (Max Sharpe)",
    ))
    fig.add_trace(go.Scatter(
        x=[resultado["actual"]["riesgo"]], y=[resultado["actual"]["retorno"]],
        mode="markers", marker=dict(symbol="diamond", size=14, color="#38BDF8"),
        name="Tu cartera actual",
    ))
    fig.update_layout(
        paper_bgcolor="#16294C", plot_bgcolor="#16294C", font=dict(color="#94A3B8", family="monospace"),
        margin=dict(l=50, r=20, t=30, b=50),
        xaxis=dict(title="Volatilidad / Riesgo Anual (%)", gridcolor="#1F3864"),
        yaxis=dict(title="Retorno Esperado Anual (%)", gridcolor="#1F3864"),
        height=450, showlegend=True,
    )
    st.plotly_chart(fig, use_container_width=True)

st.divider()
c1, c2 = st.columns(2)
with c1:
    st.markdown("###### Tu cartera actual")
    st.write(f"Retorno: **{resultado['actual']['retorno']}%**  ·  Riesgo: **{resultado['actual']['riesgo']}%**")
    r = resultado["ratios"]["actual"]
    st.caption(f"Sharpe {r['sharpe']} · Sortino {r['sortino']} · Calmar {r['calmar']}")
with c2:
    st.markdown("###### Cartera óptima")
    st.write(f"Retorno: **{resultado['optimo']['retorno']}%**  ·  Riesgo: **{resultado['optimo']['riesgo']}%**")
    r = resultado["ratios"]["optimizado"]
    st.caption(f"Sharpe {r['sharpe']} · Sortino {r['sortino']} · Calmar {r['calmar']}")
