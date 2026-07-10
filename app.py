"""
Ernesto Investing AI — iDeSo (eq5)
==================================
Versión Streamlit "todo en uno" que recrea el pipeline completo de los 3
notebooks originales, SIN depender de servicios externos:

  - Notebook 1 (Ingesta): descarga OHLCV real de Yahoo Finance y calcula
    indicadores técnicos (SMA, EMA, RSI).
  - Notebook 2 (SVC): construye features + target BUY/SELL, hace un split
    temporal 80/20, entrena un SVC con GridSearchCV (TimeSeriesSplit) y
    calcula métricas + señal actual.
  - Notebook 3 (API FastAPI + ngrok): en el original exponía /api/salud,
    /api/mercado/{ticker} y /api/svc/{ticker} vía ngrok para que un
    frontend en GitHub Pages hiciera fetch(). Aquí esa capa desaparece:
    Streamlit ES el frontend y el backend a la vez, todo en un solo proceso.

En vez de MongoDB Atlas, los "documentos" de las 3 colecciones
(precios_ohlcv, predicciones, metricas_modelos) se guardan simplemente en
`st.session_state` y se cachean con `st.cache_data` / `st.cache_resource`.
Esto cumple el mismo rol (persistencia entre pasos del pipeline) sin
necesitar una base de datos externa ni un túnel público.

Cómo correrlo:
    pip install streamlit yfinance scikit-learn pandas numpy plotly
    streamlit run app.py
"""

import math
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import GridSearchCV, TimeSeriesSplit
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

# --------------------------------------------------------------------------
# Configuración general
# --------------------------------------------------------------------------

st.set_page_config(
    page_title="Ernesto Investing AI — iDeSo",
    page_icon="📈",
    layout="wide",
)

TICKERS = ["FSM", "VOLCABC1.LM", "ABX.TO", "BVN", "BHP"]

COLUMNAS_FEATURES = [
    "SMA_20", "SMA_50", "EMA_12", "EMA_26", "RSI_14",
    "MACD", "dist_sma20", "dist_sma50", "retorno_1d", "volatilidad_5d",
]

GRID_PARAMS = {
    "kernel": ["linear", "rbf"],
    "C": [0.1, 1, 10, 100],
    "gamma": ["scale", "auto"],
}

PORCENTAJE_TRAIN = 0.8


# ==========================================================================
# NOTEBOOK 1 — Ingesta + indicadores técnicos (reemplaza MongoDB por cache)
# ==========================================================================

def calcular_rsi(serie_close: pd.Series, periodo: int = 14) -> pd.Series:
    """RSI de N periodos usando promedio móvil simple de ganancias/pérdidas."""
    delta = serie_close.diff()
    ganancia = delta.where(delta > 0, 0.0)
    perdida = -delta.where(delta < 0, 0.0)

    media_ganancia = ganancia.rolling(window=periodo, min_periods=periodo).mean()
    media_perdida = perdida.rolling(window=periodo, min_periods=periodo).mean()

    rs = media_ganancia / media_perdida
    rsi = 100 - (100 / (1 + rs))
    return rsi


@st.cache_data(show_spinner=False, ttl=3600)
def descargar_y_procesar(ticker: str) -> pd.DataFrame:
    """Descarga OHLCV de Yahoo Finance y calcula indicadores técnicos.

    Equivalente al Notebook 1 completo, pero en vez de insertar los
    documentos en la colección `precios_ohlcv` de MongoDB, devuelve
    directamente el DataFrame (Streamlit lo cachea en memoria/disco local).
    """
    df = yf.download(ticker, period="1y", auto_adjust=True, progress=False)
    if df.empty:
        return pd.DataFrame()

    # Corrección del MultiIndex de yfinance (igual que en el notebook)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.index.name = "Fecha"
    df = df.reset_index()

    # Indicadores técnicos
    df["SMA_20"] = df["Close"].rolling(window=20).mean()
    df["SMA_50"] = df["Close"].rolling(window=50).mean()
    df["EMA_12"] = df["Close"].ewm(span=12, adjust=False).mean()
    df["EMA_26"] = df["Close"].ewm(span=26, adjust=False).mean()
    df["RSI_14"] = calcular_rsi(df["Close"], periodo=14)

    return df


# ==========================================================================
# NOTEBOOK 2 — Features, target y clasificador SVC
# ==========================================================================

def calcular_features_y_target(df: pd.DataFrame) -> pd.DataFrame:
    """Genera features derivados y el target binario BUY/SELL.

    Todo lo usado como feature en la fila t se calcula con información
    disponible hasta t; el target mira t+1 (shift(-1)), por lo que la
    última fila del histórico se descarta para el entrenamiento.
    """
    df = df.copy()

    df["MACD"] = df["EMA_12"] - df["EMA_26"]
    df["dist_sma20"] = df["Close"] / df["SMA_20"] - 1
    df["dist_sma50"] = df["Close"] / df["SMA_50"] - 1
    df["retorno_1d"] = df["Close"].pct_change()
    df["volatilidad_5d"] = df["retorno_1d"].rolling(window=5).std()

    # Target: 1 (BUY) si el cierre de MAÑANA es mayor al de HOY
    df["target"] = (df["Close"].shift(-1) > df["Close"]).astype(int)

    # La última fila no tiene "mañana" conocido -> no sirve para entrenar
    df = df.iloc[:-1]

    df = df.dropna(subset=COLUMNAS_FEATURES + ["target"]).reset_index(drop=True)
    return df


@st.cache_resource(show_spinner=False)
def entrenar_pipeline_ticker(ticker: str, _df_raw: pd.DataFrame):
    """Entrena el SVC para un ticker y devuelve modelo + métricas + señal.

    Equivale a los pasos 4-9 del Notebook 2 (features, split temporal,
    GridSearchCV con TimeSeriesSplit, evaluación y señal actual). En vez de
    escribir en las colecciones `predicciones` / `metricas_modelos` de
    Mongo, se devuelve todo como un diccionario en memoria
    (`st.cache_resource` lo mantiene disponible entre reruns de la app).

    `_df_raw` lleva guion bajo para que Streamlit no intente hashear el
    DataFrame completo (solo usa `ticker` como clave de cache); igual se
    vuelve a entrenar si cambias de ticker.
    """
    df = calcular_features_y_target(_df_raw)

    n = len(df)
    corte = int(n * PORCENTAJE_TRAIN)
    if corte < 10 or (n - corte) < 5:
        return {"error": f"Muy pocos datos ({n} filas) para un split confiable."}

    train_df = df.iloc[:corte]
    test_df = df.iloc[corte:]

    X_train_raw = train_df[COLUMNAS_FEATURES].values
    X_test_raw = test_df[COLUMNAS_FEATURES].values
    y_train = train_df["target"].values
    y_test = test_df["target"].values

    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train_raw)
    X_test = scaler.transform(X_test_raw)

    cv_temporal = TimeSeriesSplit(n_splits=5)
    grid = GridSearchCV(
        estimator=SVC(probability=True, random_state=42),
        param_grid=GRID_PARAMS,
        cv=cv_temporal,
        scoring="f1",
        n_jobs=-1,
    )
    grid.fit(X_train, y_train)
    modelo = grid.best_estimator_

    y_pred = modelo.predict(X_test)
    metricas = {
        "accuracy": accuracy_score(y_test, y_pred),
        "precision": precision_score(y_test, y_pred, zero_division=0),
        "recall": recall_score(y_test, y_pred, zero_division=0),
        "f1": f1_score(y_test, y_pred, zero_division=0),
        "matriz_confusion": confusion_matrix(y_test, y_pred).tolist(),
        "mejores_hiperparametros": grid.best_params_,
        "f1_cv": grid.best_score_,
        "n_train": len(X_train),
        "n_test": len(X_test),
    }

    # --- Señal actual (recalculando features hasta la última fila real) ---
    df_completo = _df_raw.copy()
    df_completo["MACD"] = df_completo["EMA_12"] - df_completo["EMA_26"]
    df_completo["dist_sma20"] = df_completo["Close"] / df_completo["SMA_20"] - 1
    df_completo["dist_sma50"] = df_completo["Close"] / df_completo["SMA_50"] - 1
    df_completo["retorno_1d"] = df_completo["Close"].pct_change()
    df_completo["volatilidad_5d"] = df_completo["retorno_1d"].rolling(window=5).std()
    df_completo = df_completo.dropna(subset=COLUMNAS_FEATURES).reset_index(drop=True)

    ultima_fila = df_completo.iloc[[-1]]
    X_ultima = scaler.transform(ultima_fila[COLUMNAS_FEATURES].values)
    prediccion = modelo.predict(X_ultima)[0]
    probabilidad = modelo.predict_proba(X_ultima)[0][1]

    señal = {
        "fecha": ultima_fila["Fecha"].iloc[0],
        "señal": "BUY" if prediccion == 1 else "SELL",
        "probabilidad_buy": float(probabilidad),
        "created_at": datetime.now(timezone.utc),
    }

    return {
        "modelo": modelo,
        "scaler": scaler,
        "metricas": metricas,
        "señal": señal,
        "df_features": df,
        "error": None,
    }


# ==========================================================================
# "NOTEBOOK 3" — capa de acceso, equivalente a los endpoints de la API
# ==========================================================================
# En el proyecto original estas funciones vivían en FastAPI y se llamaban
# vía fetch() HTTP a través de un túnel de ngrok. Aquí son simples
# funciones Python que la propia interfaz de Streamlit invoca directamente
# (no hay red de por medio, así que tampoco hay CORS ni túnel que mantener
# vivo).

def endpoint_salud() -> dict:
    try:
        # "Ping" simbólico: confirmamos que yfinance responde para al menos
        # un ticker de referencia (reemplaza el ping a MongoDB).
        ok = not yf.download(TICKERS[0], period="5d", progress=False).empty
    except Exception:
        ok = False
    return {"estado": "ok" if ok else "error", "api": "activa (en el propio proceso de Streamlit)"}


def endpoint_mercado(ticker: str, limite: int = 100) -> pd.DataFrame:
    df = descargar_y_procesar(ticker)
    if df.empty:
        return df
    return df.tail(limite).reset_index(drop=True)


def endpoint_svc(ticker: str) -> dict:
    df = descargar_y_procesar(ticker)
    if df.empty:
        return {"error": f"No hay datos de mercado para {ticker}"}
    return entrenar_pipeline_ticker(ticker, df)


# ==========================================================================
# INTERFAZ (reemplaza al frontend de GitHub Pages: index.html / modulos)
# ==========================================================================

st.title("📈 Ernesto Investing AI — iDeSo")
st.caption(
    "Todo el pipeline (ingesta → features → SVC → señal) corre localmente, "
    "en un único proceso de Streamlit. Sin MongoDB ni ngrok."
)

with st.sidebar:
    st.header("⚙️ Panel de control")
    ticker = st.selectbox("Ticker", TICKERS, index=0)
    limite_historico = st.slider("Días a mostrar en el gráfico", 30, 250, 100)
    recalcular = st.button("🔄 Descargar / actualizar datos", use_container_width=True)

    if recalcular:
        descargar_y_procesar.clear()
        entrenar_pipeline_ticker.clear()
        st.rerun()

    st.divider()
    st.subheader("🩺 Estado del sistema")
    salud = endpoint_salud()
    if salud["estado"] == "ok":
        st.success(f"API: {salud['api']}\n\nYahoo Finance: conectado")
    else:
        st.error("No se pudo conectar a Yahoo Finance. Intenta de nuevo en un momento.")

tab_mercado, tab_svc, tab_resumen = st.tabs(
    ["📊 Mercado", "🤖 Señal SVC", "📋 Resumen de todos los tickers"]
)

# --------------------------------------------------------------------------
# Tab 1 — Mercado (equivalente a modulo_mercado.html + /api/mercado/{ticker})
# --------------------------------------------------------------------------
with tab_mercado:
    with st.spinner(f"Descargando y procesando {ticker}..."):
        df_mercado = endpoint_mercado(ticker, limite=limite_historico)

    if df_mercado.empty:
        st.warning(f"No se pudieron obtener datos para {ticker}.")
    else:
        col1, col2, col3, col4 = st.columns(4)
        ultimo = df_mercado.iloc[-1]
        anterior = df_mercado.iloc[-2] if len(df_mercado) > 1 else ultimo
        variacion = (ultimo["Close"] / anterior["Close"] - 1) * 100

        col1.metric("Último cierre", f"{ultimo['Close']:.2f}", f"{variacion:.2f}%")
        col2.metric("RSI (14)", f"{ultimo['RSI_14']:.1f}" if not math.isnan(ultimo["RSI_14"]) else "—")
        col3.metric("SMA 20", f"{ultimo['SMA_20']:.2f}" if not math.isnan(ultimo["SMA_20"]) else "—")
        col4.metric("SMA 50", f"{ultimo['SMA_50']:.2f}" if not math.isnan(ultimo["SMA_50"]) else "—")

        fig = go.Figure()
        fig.add_trace(go.Candlestick(
            x=df_mercado["Fecha"], open=df_mercado["Open"], high=df_mercado["High"],
            low=df_mercado["Low"], close=df_mercado["Close"], name="OHLC",
        ))
        fig.add_trace(go.Scatter(x=df_mercado["Fecha"], y=df_mercado["SMA_20"], name="SMA 20", line=dict(width=1)))
        fig.add_trace(go.Scatter(x=df_mercado["Fecha"], y=df_mercado["SMA_50"], name="SMA 50", line=dict(width=1)))
        fig.update_layout(
            title=f"{ticker} — Precio e indicadores",
            xaxis_rangeslider_visible=False,
            height=500,
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
        )
        st.plotly_chart(fig, use_container_width=True)

        fig_rsi = go.Figure()
        fig_rsi.add_trace(go.Scatter(x=df_mercado["Fecha"], y=df_mercado["RSI_14"], name="RSI (14)"))
        fig_rsi.add_hline(y=70, line_dash="dash", line_color="red")
        fig_rsi.add_hline(y=30, line_dash="dash", line_color="green")
        fig_rsi.update_layout(title="RSI (14)", height=250)
        st.plotly_chart(fig_rsi, use_container_width=True)

        with st.expander("Ver datos crudos (OHLCV + indicadores)"):
            st.dataframe(df_mercado, use_container_width=True)

# --------------------------------------------------------------------------
# Tab 2 — Señal SVC (equivalente a modulo_svc.html + /api/svc/{ticker})
# --------------------------------------------------------------------------
with tab_svc:
    with st.spinner(f"Entrenando SVC para {ticker} (GridSearchCV, puede tardar unos segundos)..."):
        resultado = endpoint_svc(ticker)

    if resultado.get("error"):
        st.warning(resultado["error"])
    else:
        señal = resultado["señal"]
        metricas = resultado["metricas"]

        col1, col2 = st.columns([1, 2])
        with col1:
            color = "🟢" if señal["señal"] == "BUY" else "🔴"
            st.metric(
                f"{color} Señal actual — {ticker}",
                señal["señal"],
                f"prob. BUY = {señal['probabilidad_buy']:.1%}",
            )
            st.caption(f"Fecha del dato usado: {pd.Timestamp(señal['fecha']).date()}")

        with col2:
            st.write("**Mejores hiperparámetros (GridSearchCV + TimeSeriesSplit):**")
            st.json(metricas["mejores_hiperparametros"])

        st.subheader("Métricas del modelo (sobre el 20% de test, temporal)")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Accuracy", f"{metricas['accuracy']:.2%}")
        m2.metric("Precision", f"{metricas['precision']:.2%}")
        m3.metric("Recall", f"{metricas['recall']:.2%}")
        m4.metric("F1", f"{metricas['f1']:.2%}")
        st.caption(
            f"F1 promedio en validación cruzada (CV): {metricas['f1_cv']:.4f}  |  "
            f"n_train={metricas['n_train']}  n_test={metricas['n_test']}"
        )

        matriz = np.array(metricas["matriz_confusion"])
        fig_cm = go.Figure(data=go.Heatmap(
            z=matriz,
            x=["Predicho: SELL", "Predicho: BUY"],
            y=["Real: SELL", "Real: BUY"],
            text=matriz,
            texttemplate="%{text}",
            colorscale="Blues",
        ))
        fig_cm.update_layout(title="Matriz de confusión", height=350)
        st.plotly_chart(fig_cm, use_container_width=True)

# --------------------------------------------------------------------------
# Tab 3 — Resumen de todos los tickers (barrido rápido)
# --------------------------------------------------------------------------
with tab_resumen:
    st.write("Corre el pipeline completo para los 5 tickers y compara señales.")
    if st.button("▶️ Ejecutar para todos los tickers"):
        filas = []
        progreso = st.progress(0.0)
        for i, tk in enumerate(TICKERS):
            with st.spinner(f"Procesando {tk}..."):
                df_tk = descargar_y_procesar(tk)
                if df_tk.empty:
                    filas.append({"ticker": tk, "señal": "sin datos", "prob_buy": None, "f1": None})
                else:
                    res = entrenar_pipeline_ticker(tk, df_tk)
                    if res.get("error"):
                        filas.append({"ticker": tk, "señal": "error", "prob_buy": None, "f1": None})
                    else:
                        filas.append({
                            "ticker": tk,
                            "señal": res["señal"]["señal"],
                            "prob_buy": res["señal"]["probabilidad_buy"],
                            "f1": res["metricas"]["f1"],
                        })
            progreso.progress((i + 1) / len(TICKERS))

        df_resumen = pd.DataFrame(filas)
        st.dataframe(df_resumen, use_container_width=True)
    else:
        st.info("Presiona el botón para entrenar y comparar los 5 tickers de una sola vez.")
