"""
Autenticación — equivalente a modulo6.1-autenticacion.html, pero contra
MongoDB directo (sin /api/auth/registro ni /api/auth/login por HTTP).
"""
import streamlit as st

from core.auth import login_usuario, registrar_usuario
from core.db import mongo_status
from core.session_guard import aplicar_tema, cerrar_sesion, usuario_actual

st.set_page_config(page_title="Ernesto Investing AI · Autenticación", page_icon="🔑", layout="centered")
aplicar_tema()

st.title("🔑 Autenticación")

ok, _ = mongo_status()
st.caption("● MongoDB conectada" if ok else "● Sin conexión a MongoDB")

usuario = usuario_actual()
if usuario:
    st.success(f"Ya iniciaste sesión como **{usuario['nombre']}** ({usuario['email']}).")
    if st.button("Cerrar sesión"):
        cerrar_sesion()
        st.rerun()
    st.page_link("app.py", label="← Volver al portal")
    st.stop()

tab_login, tab_registro = st.tabs(["Iniciar sesión", "Crear cuenta"])

with tab_login:
    st.caption("Accede al sistema predictivo")
    with st.form("form_login"):
        email = st.text_input("Correo electrónico", key="log_email")
        password = st.text_input("Contraseña", type="password", key="log_pass")
        enviado = st.form_submit_button("Ingresar", use_container_width=True)

    if enviado:
        if not ok:
            st.error("Falta conexión a MongoDB. Revisa .streamlit/secrets.toml.")
        else:
            exito, mensaje, datos = login_usuario(email, password)
            if exito:
                st.session_state["investai_user"] = datos
                st.success(mensaje)
                st.rerun()
            else:
                st.error(mensaje)

with tab_registro:
    st.caption("Registro en MongoDB (colección 'usuarios')")
    with st.form("form_registro"):
        nombre = st.text_input("Nombre completo", key="reg_nombre")
        email_r = st.text_input("Correo electrónico", key="reg_email")
        password_r = st.text_input("Contraseña", type="password", key="reg_pass")
        perfil = st.selectbox("Perfil de riesgo", ["conservador", "moderado", "agresivo"], index=1)
        enviado_r = st.form_submit_button("Crear cuenta", use_container_width=True)

    if enviado_r:
        if not ok:
            st.error("Falta conexión a MongoDB. Revisa .streamlit/secrets.toml.")
        else:
            exito, mensaje = registrar_usuario(nombre, email_r, password_r, perfil)
            if exito:
                st.success(mensaje)
            else:
                st.error(mensaje)
