"""
Terminal de órdenes (paper trading) — equivalente a modulo6.8-ordenes.html.
Simulación en memoria de sesión (st.session_state), no ejecuta operaciones
reales — igual que el original.
"""
import random

import pandas as pd
import streamlit as st

from core.session_guard import requiere_sesion

st.set_page_config(page_title="Ernesto Investing AI · Órdenes", page_icon="🧾", layout="wide")
requiere_sesion()

st.warning("⚠️ MODO PAPER TRADING — SIMULACIÓN. No afecta fondos reales.")
st.title("🧾 Terminal de Órdenes")
st.caption("Simulación de enrutador hacia Interactive Brokers (TWS API).")

if "historial_ordenes" not in st.session_state:
    st.session_state["historial_ordenes"] = []

col_form, col_resumen = st.columns([2, 1])

with col_form:
    direccion = st.radio("Dirección", ["COMPRAR", "VENDER"], horizontal=True)
    c1, c2 = st.columns(2)
    ticker = c1.text_input("Ticker", value="FSM").upper()
    cantidad = c2.number_input("Cantidad", min_value=1, value=100, step=1)
    c3, c4 = st.columns(2)
    tipo = c3.selectbox("Tipo", ["Market (MKT)", "Limit (LMT)"])
    precio = c4.number_input("Precio referencial ($)", min_value=0.0, value=15.50, step=0.01)

    subtotal = cantidad * precio
    comision = max(1.00, cantidad * 0.005)
    total = subtotal + comision

    if st.button("ENVIAR ORDEN →", type="primary", use_container_width=True):
        st.session_state["historial_ordenes"].insert(0, {
            "ID": f"#{random.randint(1000, 9999)}",
            "Ticker": ticker or "UNK",
            "Dir": "BUY" if direccion == "COMPRAR" else "SELL",
            "Qty": cantidad,
            "Total": f"${total:,.2f}",
            "Estado": "FILLED",
        })
        st.success(f"Orden {direccion} de {cantidad} {ticker} enviada y llenada (simulado).")

with col_resumen:
    st.markdown("###### Resumen financiero")
    st.metric("Subtotal", f"${subtotal:,.2f}")
    st.metric("Comisión IB (est.)", f"${comision:,.2f}")
    st.metric("Total estimado", f"${total:,.2f}")
    st.caption("Basado en cartera simulada de $50k")

st.divider()
st.markdown("###### Historial de transmisiones")
if st.session_state["historial_ordenes"]:
    st.dataframe(pd.DataFrame(st.session_state["historial_ordenes"]), use_container_width=True, hide_index=True)
else:
    st.info("No hay órdenes en la sesión.")
