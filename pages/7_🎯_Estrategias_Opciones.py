"""
Estrategias de opciones — equivalente a modulo6.7-estrategias.html.
Cálculo de payoff 100% local (no requiere Mongo ni backend), igual que
en el HTML original.
"""
import numpy as np
import plotly.graph_objects as go
import streamlit as st

from core.session_guard import requiere_sesion

st.set_page_config(page_title="Ernesto Investing AI · Estrategias", page_icon="🎯", layout="wide")
requiere_sesion()

st.title("🎯 Estrategias y Coberturas")
st.caption("Construye estructuras con opciones Call/Put y analiza el perfil P&L en tiempo real.")

ESTRATEGIAS = {
    "Bull Call Spread": {
        "info": "Compra Call strike bajo, vende Call strike alto. Beneficio limitado, costo reducido.",
        "legs": [
            {"tipo": "call", "accion": "buy", "strike": 100, "prima": 5},
            {"tipo": "call", "accion": "sell", "strike": 110, "prima": 2},
        ],
    },
    "Iron Condor": {
        "info": "Combina Bear Call Spread y Bull Put Spread. Recauda prima neta; gana en rango lateral.",
        "legs": [
            {"tipo": "put", "accion": "buy", "strike": 85, "prima": 1},
            {"tipo": "put", "accion": "sell", "strike": 90, "prima": 3},
            {"tipo": "call", "accion": "sell", "strike": 110, "prima": 3},
            {"tipo": "call", "accion": "buy", "strike": 115, "prima": 1},
        ],
    },
    "Straddle": {
        "info": "Compra Call y Put mismo strike. Gana con alta volatilidad en cualquier dirección.",
        "legs": [
            {"tipo": "call", "accion": "buy", "strike": 100, "prima": 6},
            {"tipo": "put", "accion": "buy", "strike": 100, "prima": 5},
        ],
    },
    "Personalizada": {
        "info": "Estrategia manual.",
        "legs": [{"tipo": "call", "accion": "buy", "strike": 100, "prima": 5}],
    },
}

nombre_strat = st.radio("Seleccionar estrategia", list(ESTRATEGIAS.keys()), horizontal=True)
st.caption(ESTRATEGIAS[nombre_strat]["info"])

if "legs_strat" not in st.session_state or st.session_state.get("legs_strat_nombre") != nombre_strat:
    st.session_state["legs_strat"] = [dict(l) for l in ESTRATEGIAS[nombre_strat]["legs"]]
    st.session_state["legs_strat_nombre"] = nombre_strat

st.markdown("###### Configuración de patas")
legs = st.session_state["legs_strat"]
cols_legs = st.columns(len(legs))
for i, (col, leg) in enumerate(zip(cols_legs, legs)):
    with col:
        color = "🟢" if leg["accion"] == "buy" else "🔴"
        st.caption(f"{color} {leg['accion'].upper()} {leg['tipo'].upper()}")
        leg["strike"] = st.number_input("Strike", value=float(leg["strike"]), key=f"strike_{i}")
        leg["prima"] = st.number_input("Prima", value=float(leg["prima"]), key=f"prima_{i}")


def payoff(leg, S):
    K, p = leg["strike"], leg["prima"]
    intr = max(0, S - K) if leg["tipo"] == "call" else max(0, K - S)
    return intr - p if leg["accion"] == "buy" else p - intr


strikes = [l["strike"] for l in legs]
s_min = max(0, min(strikes) - 30)
s_max = max(strikes) + 30
S = np.linspace(s_min, s_max, 201)
pnl = np.array([sum(payoff(l, s) for l in legs) for s in S])

be = []
for i in range(1, len(S)):
    if pnl[i - 1] * pnl[i] < 0:
        t = -pnl[i - 1] / (pnl[i] - pnl[i - 1])
        be.append(S[i - 1] + t * (S[i] - S[i - 1]))

st.markdown("###### Perfil de rendimiento (P&L)")
fig = go.Figure()
fig.add_trace(go.Scatter(x=S, y=np.where(pnl >= 0, pnl, None), fill="tozeroy", fillcolor="rgba(60,140,91,0.2)", mode="none", showlegend=False))
fig.add_trace(go.Scatter(x=S, y=np.where(pnl <= 0, pnl, None), fill="tozeroy", fillcolor="rgba(178,59,59,0.2)", mode="none", showlegend=False))
fig.add_trace(go.Scatter(x=S, y=pnl, line=dict(color="#E4B94E", width=2), showlegend=False))
fig.update_layout(
    paper_bgcolor="#16294C", plot_bgcolor="#16294C", font=dict(color="#94A3B8", family="monospace"),
    margin=dict(l=40, r=20, t=10, b=30), xaxis=dict(gridcolor="#1F3864"), yaxis=dict(gridcolor="#1F3864"),
    height=400,
)
st.plotly_chart(fig, use_container_width=True)

max_p, max_l = float(pnl.max()), float(pnl.min())
c1, c2, c3, c4 = st.columns(4)
c1.metric("Máx. Beneficio", "Ilimitado" if max_p > 999 else f"${max_p * 100:.0f}")
c2.metric("Máx. Riesgo", "Ilimitado" if max_l < -999 else f"${abs(max_l) * 100:.0f}")
c3.metric("Break-evens", ", ".join(f"${b:.2f}" for b in be) if be else "N/A")
ratio = f"1 : {max_p / abs(max_l):.1f}" if (max_p > 0 and max_l < 0 and max_l > -999) else "N/A"
c4.metric("Ratio R/B", ratio)
