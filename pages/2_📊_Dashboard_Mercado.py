"""
Dashboard de mercado — equivalente a modulo_mercado.html.
"""
import plotly.graph_objects as go
import streamlit as st

from core.mercado import TICKERS, descargar_ohlcv
from core.session_guard import requiere_sesion

st.set_page_config(page_title="Ernesto Investing AI · Mercado", page_icon="📊", layout="wide")
requiere_sesion()

st.title("📊 Dashboard de mercado")
st.caption("Precios OHLCV e indicadores técnicos en vivo desde Yahoo Finance. Sin datos simulados.")

ticker = st.radio("Ticker", TICKERS, horizontal=True)

df = descargar_ohlcv(ticker)
if df.empty:
    st.error(f"No se pudieron cargar los datos de {ticker}.")
    st.stop()

col_chart, col_stats = st.columns([2.2, 1])

with col_chart:
    st.markdown("###### Precio + medias móviles")
    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=df["Fecha"], open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"],
        name=ticker, increasing_line_color="#3C8C5B", decreasing_line_color="#B23B3B",
    ))
    fig.add_trace(go.Scatter(x=df["Fecha"], y=df["SMA_20"], name="SMA-20", line=dict(color="#C5961A", width=1.4)))
    fig.add_trace(go.Scatter(x=df["Fecha"], y=df["EMA_12"], name="EMA-12", line=dict(color="#38BDF8", width=1.4)))
    fig.update_layout(
        paper_bgcolor="#16294C", plot_bgcolor="#16294C", font=dict(color="#94A3B8", family="monospace"),
        margin=dict(l=40, r=20, t=10, b=30), xaxis=dict(gridcolor="#1F3864", rangeslider_visible=False),
        yaxis=dict(gridcolor="#1F3864"), showlegend=False, height=420,
    )
    st.plotly_chart(fig, use_container_width=True)

with col_stats:
    last = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else last
    change = float(last["Close"] - prev["Close"])
    pct = (change / float(prev["Close"])) * 100 if prev["Close"] else 0.0

    st.markdown("###### Último cierre")
    st.metric("Cierre", f"${last['Close']:.2f}", f"{change:+.2f} ({pct:+.2f}%)")
    st.caption(f"Fecha: {last['Fecha'].strftime('%Y-%m-%d')}")

    st.markdown("###### RSI-14")
    rsi = last["RSI_14"]
    if rsi != rsi:  # NaN check
        st.write("—")
    else:
        st.progress(min(1.0, max(0.0, rsi / 100)))
        st.write(f"**{rsi:.1f}**  ·  0 sobrevendido / 100 sobrecomprado")

st.divider()
st.markdown("###### Últimas filas")
st.dataframe(
    df[["Fecha", "Open", "High", "Low", "Close", "SMA_20", "SMA_50", "EMA_12", "EMA_26", "RSI_14"]].tail(20),
    use_container_width=True, hide_index=True,
)
