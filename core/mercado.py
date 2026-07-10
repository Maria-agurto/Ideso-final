"""
Ingesta OHLCV + indicadores técnicos — puerto directo de las celdas
8, 10 y 12 del notebook (descargar_ohlcv, calcular_rsi, /api/mercado).
"""
import math
from datetime import datetime, timezone

import pandas as pd
import streamlit as st
import yfinance as yf

TICKERS = ["FSM", "VOLCABC1.LM", "ABX.TO", "BVN", "BHP"]


def calcular_rsi(serie_close: pd.Series, periodo: int = 14) -> pd.Series:
    delta = serie_close.diff()
    ganancia = delta.where(delta > 0, 0.0)
    perdida = -delta.where(delta < 0, 0.0)
    media_ganancia = ganancia.rolling(window=periodo, min_periods=periodo).mean()
    media_perdida = perdida.rolling(window=periodo, min_periods=periodo).mean()
    rs = media_ganancia / media_perdida
    return 100 - (100 / (1 + rs))


@st.cache_data(ttl=3600, show_spinner="Descargando datos de Yahoo Finance…")
def descargar_ohlcv(ticker: str, period: str = "1y") -> pd.DataFrame:
    df = yf.download(ticker, period=period, auto_adjust=True, progress=False)
    if df.empty:
        return pd.DataFrame()

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.index.name = "Fecha"
    df = df.reset_index()

    df["SMA_20"] = df["Close"].rolling(window=20).mean()
    df["SMA_50"] = df["Close"].rolling(window=50).mean()
    df["EMA_12"] = df["Close"].ewm(span=12, adjust=False).mean()
    df["EMA_26"] = df["Close"].ewm(span=26, adjust=False).mean()
    df["RSI_14"] = calcular_rsi(df["Close"], periodo=14)
    return df


def safe_round(valor, nd=4):
    if valor is None or (isinstance(valor, float) and math.isnan(valor)):
        return None
    return round(float(valor), nd)


def verificar_salud() -> dict:
    try:
        ok = not yf.download(TICKERS[0], period="5d", progress=False).empty
    except Exception:
        ok = False
    return {
        "status": "healthy" if ok else "degraded",
        "estado": "ok" if ok else "error",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ambiente": "Streamlit + Yahoo Finance (datos reales, sin simulación)",
        "yahoo_finance": "conectado" if ok else "sin respuesta",
    }


def datos_mercado_tabla(ticker: str, limite: int = 100) -> list[dict]:
    """Equivalente a lo que devolvía GET /api/mercado/{ticker}."""
    df = descargar_ohlcv(ticker)
    if df.empty:
        return []

    df = df.tail(max(1, min(limite, len(df)))).reset_index(drop=True)
    filas = []
    for _, r in df.iterrows():
        filas.append(
            {
                "date": pd.Timestamp(r["Fecha"]).strftime("%Y-%m-%d"),
                "open": safe_round(r["Open"]),
                "high": safe_round(r["High"]),
                "low": safe_round(r["Low"]),
                "close": safe_round(r["Close"]),
                "volume": None if pd.isna(r.get("Volume")) else int(r["Volume"]),
                "sma_20": safe_round(r["SMA_20"]),
                "sma_50": safe_round(r["SMA_50"]),
                "ema_12": safe_round(r["EMA_12"]),
                "ema_26": safe_round(r["EMA_26"]),
                "rsi_14": safe_round(r["RSI_14"]),
            }
        )
    return filas
