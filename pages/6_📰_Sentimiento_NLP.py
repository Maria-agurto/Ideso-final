"""
Sentimiento de mercado NLP — equivalente a modulo6.5-nlp-operaciones.html.
El notebook no incluye un endpoint de NLP real (no hay celda VADER/GPT-4o),
así que igual que en el HTML original esto se queda con datos de ejemplo,
listo para conectarse a un endpoint real el día que exista.
"""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core.session_guard import requiere_sesion

st.set_page_config(page_title="Ernesto Investing AI · NLP", page_icon="📰", layout="wide")
requiere_sesion()

st.title("📰 Sentimiento de Mercado NLP")
st.caption("VADER SentimentIntensityAnalyzer + clasificador complementario. ⚪ Datos de ejemplo (no hay notebook de NLP en el curso todavía).")

NEWS_DATA = [
    {"ticker": "FSM", "titulo": "Fortuna Silver Mines reporta incremento del 18%", "fuente": "Mining Weekly", "fecha": "2026-06-12", "resumen": "La minera superó las expectativas del mercado.", "vader": 0.76, "gpt4": "BULLISH"},
    {"ticker": "BVN", "titulo": "Buenaventura enfrenta paralización en mina", "fuente": "Gestión Perú", "fecha": "2026-06-12", "resumen": "Comunidades bloquearon el acceso a la operación.", "vader": -0.61, "gpt4": "BEARISH"},
    {"ticker": "BHP", "titulo": "BHP mantiene guidance de producción", "fuente": "Reuters", "fecha": "2026-06-11", "resumen": "El gigante australiano confirmó sus proyecciones.", "vader": 0.03, "gpt4": "NEUTRAL"},
    {"ticker": "ABX.TO", "titulo": "Barrick Gold anuncia nuevo yacimiento", "fuente": "Northern Miner", "fecha": "2026-06-11", "resumen": "Resultados positivos de perforación exploratoria.", "vader": 0.82, "gpt4": "BULLISH"},
    {"ticker": "VOLCABC1.LM", "titulo": "Volcán reduce deuda corporativa", "fuente": "Bolsa de Valores", "fecha": "2026-06-10", "resumen": "Prepago anticipado de obligaciones financieras.", "vader": 0.65, "gpt4": "BULLISH"},
]

col_filtro, col_dist, col_gauge = st.columns(3)
with col_filtro:
    st.markdown("###### Filtros")
    tickers_disponibles = ["ALL"] + sorted({n["ticker"] for n in NEWS_DATA})
    filtro = st.selectbox("Ticker / Activo", tickers_disponibles)

data = [n for n in NEWS_DATA if filtro == "ALL" or n["ticker"] == filtro]

with col_dist:
    st.markdown("###### Distribución")
    counts = {
        "Bull": sum(1 for n in data if n["gpt4"] == "BULLISH"),
        "Neu": sum(1 for n in data if n["gpt4"] == "NEUTRAL"),
        "Bear": sum(1 for n in data if n["gpt4"] == "BEARISH"),
    }
    fig_dist = go.Figure(go.Bar(
        x=list(counts.values()), y=list(counts.keys()), orientation="h",
        marker_color=["#3C8C5B", "#64748b", "#B23B3B"],
    ))
    fig_dist.update_layout(
        paper_bgcolor="#16294C", plot_bgcolor="#16294C", font=dict(color="#94A3B8"),
        margin=dict(l=10, r=10, t=10, b=10), height=180, showlegend=False,
    )
    st.plotly_chart(fig_dist, use_container_width=True)

with col_gauge:
    st.markdown("###### Sentimiento global")
    avg = sum(n["vader"] for n in data) / len(data) if data else 0
    if avg >= 0.15:
        lbl, col = "ALCISTA", "#3C8C5B"
    elif avg <= -0.15:
        lbl, col = "BAJISTA", "#B23B3B"
    else:
        lbl, col = "NEUTRAL", "#94a3b8"
    val = round(((avg + 1) / 2) * 100)
    fig_gauge = go.Figure(go.Pie(
        values=[val, 100 - val], hole=0.8, marker_colors=[col, "#1F3864"],
        textinfo="none", showlegend=False,
    ))
    fig_gauge.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=10, b=10), height=150,
        annotations=[dict(text=lbl, x=0.5, y=0.5, font_size=14, font_color=col, showarrow=False)],
    )
    st.plotly_chart(fig_gauge, use_container_width=True)

st.divider()
st.markdown(f"###### Feed de noticias ({len(data)})")
cols_feed = st.columns(3)
for i, news in enumerate(data):
    with cols_feed[i % 3]:
        with st.container(border=True):
            st.caption(f"**{news['ticker']}**  ·  {news['fecha']}")
            st.markdown(f"**{news['titulo']}**")
            st.write(news["resumen"])
            color = "green" if news["gpt4"] == "BULLISH" else ("red" if news["gpt4"] == "BEARISH" else "gray")
            st.markdown(f"VADER: `{news['vader']}`  ·  :{color}[{news['gpt4']}]")
