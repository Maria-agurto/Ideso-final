"""
Consola de administración — equivalente a modulo6.10-consola.html.
Ahora con datos reales de las colecciones Mongo (antes eran solo
indicadores estáticos "OPERATIVO"/"CONECTADO").
"""
import streamlit as st

from core.db import get_collections, mongo_status
from core.session_guard import requiere_sesion

st.set_page_config(page_title="Ernesto Investing AI · Consola", page_icon="🛠️", layout="wide")
requiere_sesion()

st.title("🛠️ Consola de Administración")
st.caption("Control de variables críticas, estado de colecciones Mongo y Kill Switch de emergencia.")

col1, col2 = st.columns(2)

with col1:
    st.markdown("###### Estado de microservicios")
    ok, detalle = mongo_status()
    st.write("**MongoDB Atlas**", "🟢 CONECTADO" if ok else f"🔴 SIN CONEXIÓN ({detalle})")

    if ok:
        col_usuarios, col_cache, col_logs = get_collections()
        st.write("**Usuarios registrados**", col_usuarios.count_documents({}))
        st.write("**Entradas en caché de modelos**", col_cache.count_documents({}))
        st.write("**Registros de log histórico**", col_logs.count_documents({}))

    st.write("**Yahoo Finance**", "🟢 vía yfinance (sin backend intermedio)")
    st.write("**Interactive Brokers TWS**", "🟡 PAPER TRADING (simulado)")

with col2:
    st.markdown("###### Umbrales algorítmicos")
    st.slider("Tolerancia de slippage máxima", 0.1, 2.0, 0.5, step=0.1, format="%.1f%%")
    st.slider("Confianza mínima (SVC/RNN) para disparo", 50, 95, 75, step=5, format="%d%%")
    st.button("Guardar parámetros", use_container_width=True)

st.divider()
with st.container(border=True):
    st.markdown("###### 🛑 Protocolo de emergencia")
    st.write("Detiene de inmediato cualquier nueva transmisión de órdenes y liquida las posiciones abiertas a precio de mercado. Úsalo solo en caso de anomalías críticas.")
    if st.button("Activar Kill Switch", type="primary"):
        st.session_state["kill_switch"] = True
    if st.session_state.get("kill_switch"):
        st.error("🛑 KILL SWITCH ACTIVADO. Algoritmo detenido (simulado).")
