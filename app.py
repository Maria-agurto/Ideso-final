"""
Ernesto Investing AI — Portal unificado en Streamlit.

Reemplaza index.html + el flujo de "pegar URL de ngrok". Ahora la app
habla directo con MongoDB Atlas (sin FastAPI ni túnel), y cada módulo
vive como una página de Streamlit en pages/.
"""
import streamlit as st

from core.db import mongo_status
from core.session_guard import aplicar_tema, usuario_actual

st.set_page_config(
    page_title="Ernesto Investing AI · Portal",
    page_icon="📈",
    layout="wide",
)
aplicar_tema()

# ------------------------------------------------------------------
# NAV / estado de conexión
# ------------------------------------------------------------------
col_nav1, col_nav2 = st.columns([3, 1])
with col_nav1:
    st.markdown(
        "<span style='font-family:monospace; letter-spacing:2px; text-transform:uppercase; "
        "color:#94A3B8; font-size:0.8rem;'>Ernesto <span style='color:#E4B94E; font-weight:600;'>"
        "Investing AI</span></span>",
        unsafe_allow_html=True,
    )
with col_nav2:
    ok, detalle = mongo_status()
    if ok:
        st.success("● MongoDB conectada", icon="✅")
    else:
        st.error(f"● Sin conexión a MongoDB", icon="🚫")

st.divider()

# ------------------------------------------------------------------
# HERO
# ------------------------------------------------------------------
st.markdown(
    "<span style='font-family:monospace; text-transform:uppercase; letter-spacing:2px; "
    "color:#C5961A; font-size:0.8rem;'>Minería · Mercados · Datos reales</span>",
    unsafe_allow_html=True,
)
st.title("Cinco activos mineros, un solo flujo de datos.")
st.markdown(
    "De Yahoo Finance a MongoDB, de MongoDB a un clasificador SVC (y a un ensamble de "
    "redes recurrentes), y de ahí a esta pantalla. **Todo unificado en un solo proceso de "
    "Streamlit** — ya no se necesita FastAPI en Colab ni un túnel de ngrok: cada página lee "
    "y escribe directo en MongoDB Atlas."
)

usuario = usuario_actual()
if usuario:
    st.info(f"Sesión activa: **{usuario['nombre']}** ({usuario['email']}) · perfil {usuario['perfil']}")
else:
    st.warning("No has iniciado sesión. Ve a **🔑 Autenticación** en el menú lateral para entrar o registrarte.")

st.divider()

# ------------------------------------------------------------------
# MÓDULOS — tarjetas equivalentes a la sección "Paso 2" de index.html
# ------------------------------------------------------------------
st.markdown("##### Módulos disponibles")
st.caption("🟡 datos reales · 🟢 no requiere modelos pesados · ⚪ simulado por diseño")

modulos = [
    ("pages/2_📊_Dashboard_Mercado.py", "📊 Dashboard de mercado", "Velas OHLCV, SMA, EMA y RSI de los 5 tickers, en vivo desde Yahoo Finance / Mongo.", "🟡"),
    ("pages/3_🤖_Clasificador_SVC.py", "🤖 Clasificador SVC", "Señal BUY/SELL, métricas de desempeño y matriz de confusión.", "🟡"),
    ("pages/4_🔮_Pronosticos_LSTM.py", "🔮 Pronósticos LSTM", "Regresión iterativa a N días con TensorFlow.", "🟡"),
    ("pages/5_🧠_Core_Predictivo_RNNs.py", "🧠 Core Predictivo (RNNs)", "Ensamble LSTM/BiLSTM/GRU/SimpleRNN consolidado.", "🟡"),
    ("pages/6_📰_Sentimiento_NLP.py", "📰 Sentimiento NLP", "VADER + clasificador complementario sobre titulares. Datos de ejemplo.", "⚪"),
    ("pages/7_🎯_Estrategias_Opciones.py", "🎯 Estrategias de opciones", "Payoff de Call/Put, cálculo 100% en el proceso de Streamlit.", "🟢"),
    ("pages/8_🧾_Ordenes_Paper_Trading.py", "🧾 Órdenes (paper trading)", "Simulador de órdenes de compra/venta. No ejecuta operaciones reales.", "🟢"),
    ("pages/9_📐_Portafolios_Markowitz.py", "📐 Portafolios (Markowitz)", "Frontera eficiente y pesos óptimos vía Sharpe máximo.", "🟡"),
    ("pages/10_🛠️_Consola_Admin.py", "🛠️ Consola de administración", "Estado de colecciones Mongo y kill switch del algoritmo.", "🟢"),
    ("pages/11_📈_Backtesting.py", "📈 Backtesting histórico", "Curva de equity IA vs Buy & Hold. Simulado por diseño.", "⚪"),
]

cols = st.columns(3)
for i, (path, titulo, desc, estado) in enumerate(modulos):
    with cols[i % 3]:
        with st.container(border=True):
            st.markdown(f"**{estado} {titulo}**")
            st.caption(desc)
            st.page_link(path, label="Entrar al módulo →")

st.divider()
st.caption("iDeSo · UNMSM · FISI — Proyecto: Ernesto Investing AI (versión unificada en Streamlit)")
