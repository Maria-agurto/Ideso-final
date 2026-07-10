"""
Guard de sesión — reemplaza el patrón verificarSesion() que se repetía
en cada módulo HTML (localStorage.getItem('investai_user') + redirect).
Aquí usamos st.session_state, que vive mientras dure la pestaña/sesión
del navegador contra este server de Streamlit.
"""
import streamlit as st

TEMA_INSTITUCIONAL = """
<style>
    .stApp { background-color: #10182B; }
    section[data-testid="stSidebar"] { background-color: #16294C; }
    div[data-testid="stMetricValue"] { color: #E4B94E; }
</style>
"""


def aplicar_tema():
    st.markdown(TEMA_INSTITUCIONAL, unsafe_allow_html=True)


def usuario_actual() -> dict | None:
    return st.session_state.get("investai_user")


def requiere_sesion():
    """Equivalente a verificarSesion() + window.location.replace(...)."""
    aplicar_tema()
    if usuario_actual() is None:
        st.warning("🔒 Acceso denegado. Inicia sesión para acceder al sistema InvestAI.")
        st.page_link("pages/1_🔑_Autenticacion.py", label="Ir a iniciar sesión →", icon="🔑")
        st.stop()


def cerrar_sesion():
    st.session_state.pop("investai_user", None)
