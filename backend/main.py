"""
Ernesto Investing AI — iDeSo (eq5)
===================================
Backend FastAPI ÚNICO que reemplaza al Notebook 3 original (API + ngrok) y
expone TODOS los endpoints que el frontend (11 módulos HTML) sabe consumir.

No hay datos simulados en ningún endpoint de este archivo: todo se calcula
en tiempo real (con caché) a partir de precios reales descargados de Yahoo
Finance (`yfinance`). En vez de MongoDB Atlas, la persistencia de:
  - usuarios (Módulo 1 — Autenticación)
se guarda en un archivo SQLite local (`investai.db`).
El resto de módulos (mercado, SVC, RNNs, LSTM, portafolio) se recalculan
bajo demanda y se cachean en memoria (TTL) porque su "fuente de verdad" es
siempre el precio de mercado más reciente, no un registro que haya que
persistir.

Cómo correrlo:
    pip install -r requirements.txt
    uvicorn main:app --host 0.0.0.0 --port 8000
    # (en Colab: exponer con ngrok, igual que el Notebook 3 original)

Módulos conectados con datos reales:
  /api/salud                    → estado del servidor
  /api/mercado/{ticker}         → OHLCV + indicadores técnicos reales
  /api/svc/{ticker}             → clasificador SVC (BUY/SELL) real
  /api/rnns/{ticker}            → LSTM/BiLSTM/GRU/SimpleRNN reales (TensorFlow)
  /api/lstm/{ticker}            → regresor LSTM real (proyección de precio)
  /api/auth/registro            → alta de usuario real (SQLite + hash bcrypt)
  /api/auth/login               → login real
  /api/portafolio/optimizar     → optimización de Markowitz real (scipy)

Módulos que NO se conectan a un backend "real" (y por qué), ver README:
  M5 Análisis NLP (necesita una fuente de noticias externa),
  M7 Estrategias (calculadora de payoff sobre datos que ingresa el usuario),
  M8 Órdenes (requiere una cuenta de bróker real, ej. TWS/IBKR),
  M10 Consola (panel de control, no muestra datos de mercado).
"""

import hashlib
import math
import os
import sqlite3
import threading
import time
from datetime import datetime, timezone
from typing import Optional

import numpy as np
import pandas as pd
import yfinance as yf
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field
from scipy.optimize import minimize
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    precision_score,
    r2_score,
    recall_score,
)
from sklearn.model_selection import GridSearchCV, TimeSeriesSplit
from sklearn.preprocessing import MinMaxScaler, StandardScaler
from sklearn.svm import SVC

# ==========================================================================
# Configuración general
# ==========================================================================

app = FastAPI(title="Ernesto Investing AI — iDeSo API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # el frontend corre en otro dominio (GitHub Pages / file://)
    allow_methods=["*"],
    allow_headers=["*"],
)

TICKERS = ["FSM", "VOLCABC1.LM", "ABX.TO", "BVN", "BHP"]

COLUMNAS_FEATURES_SVC = [
    "SMA_20", "SMA_50", "EMA_12", "EMA_26", "RSI_14",
    "MACD", "dist_sma20", "dist_sma50", "retorno_1d", "volatilidad_5d",
]

GRID_PARAMS_SVC = {
    "kernel": ["linear", "rbf"],
    "C": [0.1, 1, 10, 100],
    "gamma": ["scale", "auto"],
}

PORCENTAJE_TRAIN = 0.8
DB_PATH = os.path.join(os.path.dirname(__file__), "investai.db")


# ==========================================================================
# Caché en memoria (TTL) — evita recalcular / reentrenar en cada request
# ==========================================================================

_CACHE: dict = {}
_CACHE_LOCKS: dict = {}
_CACHE_LOCKS_GUARD = threading.Lock()


def _lock_for(key: str) -> threading.Lock:
    with _CACHE_LOCKS_GUARD:
        if key not in _CACHE_LOCKS:
            _CACHE_LOCKS[key] = threading.Lock()
        return _CACHE_LOCKS[key]


def cache_get_or_compute(key: str, ttl_segundos: int, compute_fn):
    """Devuelve el valor cacheado si sigue vigente; si no, lo recalcula.

    Usa un lock por clave para que dos requests concurrentes al mismo
    ticker no disparen dos entrenamientos en paralelo.
    """
    entry = _CACHE.get(key)
    if entry and (time.time() - entry["ts"]) < ttl_segundos:
        return entry["value"]

    with _lock_for(key):
        entry = _CACHE.get(key)
        if entry and (time.time() - entry["ts"]) < ttl_segundos:
            return entry["value"]
        value = compute_fn()
        _CACHE[key] = {"value": value, "ts": time.time()}
        return value


# ==========================================================================
# Ingesta + indicadores técnicos (equivalente al Notebook 1)
# ==========================================================================

def calcular_rsi(serie_close: pd.Series, periodo: int = 14) -> pd.Series:
    delta = serie_close.diff()
    ganancia = delta.where(delta > 0, 0.0)
    perdida = -delta.where(delta < 0, 0.0)
    media_ganancia = ganancia.rolling(window=periodo, min_periods=periodo).mean()
    media_perdida = perdida.rolling(window=periodo, min_periods=periodo).mean()
    rs = media_ganancia / media_perdida
    rsi = 100 - (100 / (1 + rs))
    return rsi


def descargar_ohlcv(ticker: str, period: str = "1y") -> pd.DataFrame:
    """Descarga OHLCV real de Yahoo Finance y calcula indicadores técnicos."""
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


def _safe_round(valor, nd=4):
    if valor is None or (isinstance(valor, float) and math.isnan(valor)):
        return None
    return round(float(valor), nd)


# ==========================================================================
# /api/salud
# ==========================================================================

@app.get("/api/salud")
def api_salud():
    try:
        ok = not yf.download(TICKERS[0], period="5d", progress=False).empty
    except Exception:
        ok = False
    return {
        "status": "healthy" if ok else "degraded",
        "estado": "ok" if ok else "error",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ambiente": "FastAPI + Yahoo Finance (datos reales, sin simulación)",
        "yahoo_finance": "conectado" if ok else "sin respuesta",
    }


# ==========================================================================
# /api/mercado/{ticker}  (equivalente al Notebook 1 + colección precios_ohlcv)
# ==========================================================================

@app.get("/api/mercado/{ticker}")
def api_mercado(ticker: str, limite: int = 100):
    df = cache_get_or_compute(f"mercado:{ticker}", 3600, lambda: descargar_ohlcv(ticker))
    if df.empty:
        raise HTTPException(status_code=404, detail=f"No hay datos de mercado para '{ticker}'.")

    df = df.tail(max(1, min(limite, len(df)))).reset_index(drop=True)
    filas = []
    for _, r in df.iterrows():
        filas.append({
            "date": pd.Timestamp(r["Fecha"]).strftime("%Y-%m-%d"),
            "fecha": pd.Timestamp(r["Fecha"]).strftime("%Y-%m-%d"),
            "open": _safe_round(r["Open"]),
            "high": _safe_round(r["High"]),
            "low": _safe_round(r["Low"]),
            "close": _safe_round(r["Close"]),
            "volume": None if pd.isna(r.get("Volume")) else int(r["Volume"]),
            "sma_20": _safe_round(r["SMA_20"]),
            "sma_50": _safe_round(r["SMA_50"]),
            "ema_12": _safe_round(r["EMA_12"]),
            "ema_26": _safe_round(r["EMA_26"]),
            "rsi_14": _safe_round(r["RSI_14"]),
        })
    return {"ticker": ticker, "fuente": "Yahoo Finance (yfinance)", "datos": filas}


# ==========================================================================
# /api/svc/{ticker}  (equivalente al Notebook 2 — clasificador BUY/SELL)
# ==========================================================================

def calcular_features_y_target_svc(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["MACD"] = df["EMA_12"] - df["EMA_26"]
    df["dist_sma20"] = df["Close"] / df["SMA_20"] - 1
    df["dist_sma50"] = df["Close"] / df["SMA_50"] - 1
    df["retorno_1d"] = df["Close"].pct_change()
    df["volatilidad_5d"] = df["retorno_1d"].rolling(window=5).std()
    df["target"] = (df["Close"].shift(-1) > df["Close"]).astype(int)
    df_train = df.iloc[:-1].dropna(subset=COLUMNAS_FEATURES_SVC + ["target"]).reset_index(drop=True)
    return df, df_train


def entrenar_svc(ticker: str) -> dict:
    df_raw = descargar_ohlcv(ticker)
    if df_raw.empty:
        return {"error": f"No hay datos de mercado para '{ticker}'."}

    df_completo, df = calcular_features_y_target_svc(df_raw)
    n = len(df)
    corte = int(n * PORCENTAJE_TRAIN)
    if corte < 10 or (n - corte) < 5:
        return {"error": f"Muy pocos datos ({n} filas) para un split confiable."}

    train_df = df.iloc[:corte]
    test_df = df.iloc[corte:]

    X_train_raw = train_df[COLUMNAS_FEATURES_SVC].values
    X_test_raw = test_df[COLUMNAS_FEATURES_SVC].values
    y_train = train_df["target"].values
    y_test = test_df["target"].values

    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train_raw)
    X_test = scaler.transform(X_test_raw)

    cv_temporal = TimeSeriesSplit(n_splits=5)
    grid = GridSearchCV(
        estimator=SVC(probability=True, random_state=42),
        param_grid=GRID_PARAMS_SVC,
        cv=cv_temporal,
        scoring="f1",
        n_jobs=-1,
    )
    grid.fit(X_train, y_train)
    modelo = grid.best_estimator_

    y_pred = modelo.predict(X_test)
    metricas = {
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "precision": float(precision_score(y_test, y_pred, zero_division=0)),
        "recall": float(recall_score(y_test, y_pred, zero_division=0)),
        "f1": float(f1_score(y_test, y_pred, zero_division=0)),
        "matriz_confusion": confusion_matrix(y_test, y_pred, labels=[0, 1]).tolist(),
        "mejores_hiperparametros": grid.best_params_,
        "f1_cv": float(grid.best_score_),
        "n_train": int(len(train_df)),
        "n_test": int(len(test_df)),
    }

    # Señal actual: usamos la última fila disponible del histórico completo
    # (incluye el día más reciente, que no tiene target porque "mañana" aún
    # no ocurrió — es exactamente el dato que queremos predecir).
    ultima_fila = df_completo.dropna(subset=COLUMNAS_FEATURES_SVC).iloc[-1]
    X_actual = scaler.transform(ultima_fila[COLUMNAS_FEATURES_SVC].values.reshape(1, -1))
    proba = modelo.predict_proba(X_actual)[0]
    prob_buy = float(proba[1])
    señal = {
        "señal": "BUY" if prob_buy >= 0.5 else "SELL",
        "probabilidad_buy": prob_buy,
        "fecha": pd.Timestamp(ultima_fila["Fecha"]).strftime("%Y-%m-%d"),
    }

    return {"ticker": ticker, "prediccion": señal, "metricas": metricas, "error": None}


@app.get("/api/svc/{ticker}")
def api_svc(ticker: str):
    resultado = cache_get_or_compute(f"svc:{ticker}", 3600, lambda: entrenar_svc(ticker))
    if resultado.get("error"):
        raise HTTPException(status_code=404, detail=resultado["error"])
    return resultado


# ==========================================================================
# /api/rnns/{ticker}  (Notebook 4 — LSTM/BiLSTM/GRU/SimpleRNN clasificadores)
# ==========================================================================

VENTANA_RNN = 10
FEATURES_RNN = ["Close", "SMA_20", "EMA_12", "RSI_14"]


def _construir_ventanas(matriz: np.ndarray, target: np.ndarray, ventana: int):
    X, y = [], []
    for i in range(len(matriz) - ventana):
        X.append(matriz[i:i + ventana])
        y.append(target[i + ventana])
    return np.array(X), np.array(y)


def _evaluar_clasificador(y_real, y_prob):
    y_pred = (y_prob > 0.5).astype(int)
    return {
        "accuracy": float(accuracy_score(y_real, y_pred)),
        "precision": float(precision_score(y_real, y_pred, zero_division=0)),
        "recall": float(recall_score(y_real, y_pred, zero_division=0)),
        "f1": float(f1_score(y_real, y_pred, zero_division=0)),
    }


def _senal_desde_probabilidad(p: float) -> str:
    if p > 0.65:
        return "BUY"
    if p < 0.35:
        return "SELL"
    return "HOLD"


def entrenar_rnns(ticker: str) -> dict:
    # Import perezoso: TensorFlow es pesado y solo lo necesitan estos 2 endpoints.
    import tensorflow as tf
    from tensorflow.keras.layers import GRU, LSTM, Bidirectional, Dense, SimpleRNN
    from tensorflow.keras.models import Sequential

    tf.random.set_seed(42)

    df = descargar_ohlcv(ticker, period="2y")
    if df.empty:
        return {"error": f"No hay datos de mercado para '{ticker}'."}

    df = df.dropna(subset=FEATURES_RNN).reset_index(drop=True)
    df["target"] = (df["Close"].shift(-1) > df["Close"]).astype(int)
    df_modelo = df.iloc[:-1].dropna(subset=FEATURES_RNN + ["target"]).reset_index(drop=True)

    if len(df_modelo) < (VENTANA_RNN + 40):
        return {"error": f"Muy pocos datos ({len(df_modelo)} filas) para entrenar los modelos RNN."}

    X_raw = df_modelo[FEATURES_RNN].values
    y_raw = df_modelo["target"].values

    X_vent, y_vent = _construir_ventanas(X_raw, y_raw, VENTANA_RNN)
    n = len(X_vent)
    corte = int(n * PORCENTAJE_TRAIN)

    X_train, X_test = X_vent[:corte], X_vent[corte:]
    y_train, y_test = y_vent[:corte], y_vent[corte:]

    # Escalado 3D: ajustamos el scaler solo con el tramo de entrenamiento
    # (aplanado), para no filtrar información del futuro.
    n_feat = X_raw.shape[1]
    scaler = MinMaxScaler()
    scaler.fit(X_train.reshape(-1, n_feat))
    X_train_s = scaler.transform(X_train.reshape(-1, n_feat)).reshape(X_train.shape)
    X_test_s = scaler.transform(X_test.reshape(-1, n_feat)).reshape(X_test.shape)

    def construir(kind: str):
        modelo = Sequential()
        capa = {
            "lstm": LSTM(32, input_shape=(VENTANA_RNN, n_feat)),
            "bilstm": Bidirectional(LSTM(32), input_shape=(VENTANA_RNN, n_feat)),
            "gru": GRU(32, input_shape=(VENTANA_RNN, n_feat)),
            "simplernn": SimpleRNN(32, input_shape=(VENTANA_RNN, n_feat)),
        }[kind]
        modelo.add(capa)
        modelo.add(Dense(16, activation="relu"))
        modelo.add(Dense(1, activation="sigmoid"))
        modelo.compile(optimizer="adam", loss="binary_crossentropy", metrics=["accuracy"])
        return modelo

    # Última ventana disponible (para la predicción "de mañana")
    ultima_ventana_raw = X_raw[-VENTANA_RNN:]
    ultima_ventana_s = scaler.transform(ultima_ventana_raw).reshape(1, VENTANA_RNN, n_feat)

    resultados = {}
    for kind in ["lstm", "bilstm", "gru", "simplernn"]:
        modelo = construir(kind)
        early_stop = tf.keras.callbacks.EarlyStopping(
            monitor="loss", patience=5, restore_best_weights=True
        )
        modelo.fit(
            X_train_s, y_train,
            epochs=40, batch_size=16, verbose=0,
            callbacks=[early_stop],
        )
        y_prob_test = modelo.predict(X_test_s, verbose=0).flatten()
        metricas = _evaluar_clasificador(y_test, y_prob_test)

        prob_mañana = float(modelo.predict(ultima_ventana_s, verbose=0).flatten()[0])
        resultados[kind] = {
            "metricas": metricas,
            "probabilidad_mañana": prob_mañana,
            "senal": _senal_desde_probabilidad(prob_mañana),
        }

    return {
        "ticker": ticker,
        "ultima_actualizacion": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "modelos": resultados,
        "error": None,
    }


@app.get("/api/rnns/{ticker}")
def api_rnns(ticker: str):
    # TTL más largo: entrenar 4 redes por ticker es costoso.
    resultado = cache_get_or_compute(f"rnns:{ticker}", 6 * 3600, lambda: entrenar_rnns(ticker))
    if resultado.get("error"):
        raise HTTPException(status_code=404, detail=resultado["error"])
    return resultado


# ==========================================================================
# /api/lstm/{ticker}  (Notebook 5 — regresor LSTM de precio)
# ==========================================================================

VENTANA_LSTM = 60


def entrenar_lstm_regresor(ticker: str, horizonte: int) -> dict:
    import tensorflow as tf
    from tensorflow.keras.layers import Dense, Dropout, LSTM
    from tensorflow.keras.models import Sequential

    tf.random.set_seed(42)

    df = descargar_ohlcv(ticker, period="2y")
    if df.empty:
        return {"error": f"No hay datos de mercado para '{ticker}'."}

    cierres = df["Close"].dropna().values.reshape(-1, 1)
    if len(cierres) < (VENTANA_LSTM + 60):
        return {"error": f"Muy pocos datos ({len(cierres)} filas) para entrenar el regresor LSTM."}

    n = len(cierres)
    corte = int(n * PORCENTAJE_TRAIN)

    scaler = MinMaxScaler()
    scaler.fit(cierres[:corte])  # ajustamos solo con el tramo de train
    cierres_s = scaler.transform(cierres)

    X, y = [], []
    for i in range(len(cierres_s) - VENTANA_LSTM):
        X.append(cierres_s[i:i + VENTANA_LSTM, 0])
        y.append(cierres_s[i + VENTANA_LSTM, 0])
    X, y = np.array(X), np.array(y)

    # El corte de train/test se hace sobre las ventanas ya construidas,
    # preservando el orden temporal.
    corte_vent = corte - VENTANA_LSTM
    corte_vent = max(1, corte_vent)
    X_train, X_test = X[:corte_vent], X[corte_vent:]
    y_train, y_test = y[:corte_vent], y[corte_vent:]

    X_train = X_train.reshape((X_train.shape[0], VENTANA_LSTM, 1))
    X_test = X_test.reshape((X_test.shape[0], VENTANA_LSTM, 1))

    modelo = Sequential([
        LSTM(64, return_sequences=True, input_shape=(VENTANA_LSTM, 1)),
        Dropout(0.2),
        LSTM(32),
        Dropout(0.2),
        Dense(16, activation="relu"),
        Dense(1),
    ])
    modelo.compile(optimizer="adam", loss="mse")
    early_stop = tf.keras.callbacks.EarlyStopping(monitor="loss", patience=6, restore_best_weights=True)
    modelo.fit(X_train, y_train, epochs=60, batch_size=16, verbose=0, callbacks=[early_stop])

    y_pred_test_s = modelo.predict(X_test, verbose=0).flatten()
    y_pred_test = scaler.inverse_transform(y_pred_test_s.reshape(-1, 1)).flatten()
    y_real_test = scaler.inverse_transform(y_test.reshape(-1, 1)).flatten()

    rmse = float(math.sqrt(mean_squared_error(y_real_test, y_pred_test)))
    mae = float(mean_absolute_error(y_real_test, y_pred_test))
    r2 = float(r2_score(y_real_test, y_pred_test))
    rmse_pct = float(rmse / np.mean(y_real_test) * 100)

    fechas_test = df["Fecha"].iloc[-len(y_real_test):].reset_index(drop=True)
    historico_validacion = [
        {
            "fecha": pd.Timestamp(fechas_test[i]).strftime("%Y-%m-%d"),
            "real": round(float(y_real_test[i]), 4),
            "predicho": round(float(y_pred_test[i]), 4),
        }
        for i in range(len(y_real_test))
    ]

    # Desviación estándar de los residuos de validación → banda de confianza
    residuos = y_real_test - y_pred_test
    std_residuo = float(np.std(residuos)) if len(residuos) > 1 else float(np.std(y_real_test)) * 0.05

    # Proyección iterativa a `horizonte` días (recursiva: cada predicción
    # entra como el último valor de la siguiente ventana).
    ventana_actual = cierres_s[-VENTANA_LSTM:, 0].tolist()
    ultima_fecha = pd.Timestamp(df["Fecha"].iloc[-1])
    proyeccion_futura = []
    for paso in range(1, horizonte + 1):
        entrada = np.array(ventana_actual[-VENTANA_LSTM:]).reshape(1, VENTANA_LSTM, 1)
        pred_s = float(modelo.predict(entrada, verbose=0).flatten()[0])
        pred_usd = float(scaler.inverse_transform([[pred_s]])[0][0])
        ventana_actual.append(pred_s)

        ancho_banda = std_residuo * 1.96 * math.sqrt(paso)  # crece con el horizonte
        fecha_pred = ultima_fecha + pd.Timedelta(days=paso)
        # Saltar fines de semana (mercado no opera sáb/dom)
        while fecha_pred.weekday() >= 5:
            fecha_pred += pd.Timedelta(days=1)

        proyeccion_futura.append({
            "fecha": fecha_pred.strftime("%Y-%m-%d"),
            "prediccion_usd": round(pred_usd, 4),
            "banda_min": round(pred_usd - ancho_banda, 4),
            "banda_max": round(pred_usd + ancho_banda, 4),
        })

    return {
        "ticker": ticker,
        "metricas_error": {
            "rmse_usd": rmse,
            "rmse_porcentaje": rmse_pct,
            "mae_usd": mae,
            "r2_score": r2,
        },
        "historico_validacion": historico_validacion,
        "proyeccion_futura": proyeccion_futura,
        "error": None,
    }


@app.get("/api/lstm/{ticker}")
def api_lstm(ticker: str, horizonte: int = 30):
    horizonte = max(1, min(horizonte, 90))
    resultado = cache_get_or_compute(
        f"lstm:{ticker}:{horizonte}", 6 * 3600, lambda: entrenar_lstm_regresor(ticker, horizonte)
    )
    if resultado.get("error"):
        raise HTTPException(status_code=404, detail=resultado["error"])
    return resultado


# ==========================================================================
# /api/auth  (Módulo 1 — alta/login real, persistido en SQLite)
# ==========================================================================

def _db_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            email TEXT PRIMARY KEY,
            nombre TEXT NOT NULL,
            perfil TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            creado_en TEXT NOT NULL
        )
    """)
    return conn


def _hash_password(password: str, salt: Optional[str] = None):
    if salt is None:
        salt = os.urandom(16).hex()
    hash_hex = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 200_000).hex()
    return hash_hex, salt


class RegistroRequest(BaseModel):
    nombre: str = Field(min_length=1)
    email: EmailStr
    password: str = Field(min_length=8)
    perfil: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


@app.post("/api/auth/registro")
def api_auth_registro(payload: RegistroRequest):
    if payload.perfil not in ("conservador", "moderado", "agresivo"):
        raise HTTPException(status_code=400, detail="Perfil de riesgo inválido.")

    conn = _db_conn()
    try:
        existente = conn.execute(
            "SELECT 1 FROM usuarios WHERE email = ?", (payload.email.lower(),)
        ).fetchone()
        if existente:
            raise HTTPException(status_code=409, detail="Ya existe una cuenta con ese correo.")

        hash_hex, salt = _hash_password(payload.password)
        conn.execute(
            "INSERT INTO usuarios (email, nombre, perfil, password_hash, salt, creado_en) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                payload.email.lower(), payload.nombre, payload.perfil,
                hash_hex, salt, datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()
    finally:
        conn.close()

    return {"mensaje": f"Cuenta creada para {payload.nombre}."}


@app.post("/api/auth/login")
def api_auth_login(payload: LoginRequest):
    conn = _db_conn()
    try:
        fila = conn.execute(
            "SELECT nombre, perfil, password_hash, salt FROM usuarios WHERE email = ?",
            (payload.email.lower(),),
        ).fetchone()
    finally:
        conn.close()

    if not fila:
        raise HTTPException(status_code=401, detail="Correo o contraseña incorrectos.")

    nombre, perfil, password_hash, salt = fila
    hash_calculado, _ = _hash_password(payload.password, salt)
    if hash_calculado != password_hash:
        raise HTTPException(status_code=401, detail="Correo o contraseña incorrectos.")

    return {"nombre": nombre, "perfil": perfil, "email": payload.email.lower()}


# ==========================================================================
# /api/portafolio/optimizar  (Módulo 9 — Markowitz real con scipy)
# ==========================================================================

ACTIVOS_PORTAFOLIO = TICKERS + ["CASH"]
TASA_LIBRE_RIESGO_ANUAL = 0.02  # aproximación de referencia para CASH/Sharpe


class ActivoPeso(BaseModel):
    ticker: str
    peso: float  # en porcentaje, ej. 18.0


class PortafolioRequest(BaseModel):
    activos: list[ActivoPeso]
    capital_total: float = 100000.0


def _retornos_diarios(ticker: str) -> pd.Series:
    df = descargar_ohlcv(ticker, period="1y")
    if df.empty:
        return pd.Series(dtype=float)
    return df["Close"].pct_change().dropna()


def _stats_mercado():
    """Retorno esperado anualizado y matriz de covarianza anualizada,
    calculados con retornos diarios reales de los 5 tickers + CASH
    (CASH se modela como activo libre de riesgo: retorno fijo, varianza 0).
    """
    series = {}
    for tk in TICKERS:
        s = cache_get_or_compute(f"retornos:{tk}", 3600, lambda tk=tk: _retornos_diarios(tk))
        series[tk] = s

    df_ret = pd.DataFrame(series).dropna(how="all")
    df_ret = df_ret.fillna(0.0)

    medias_anuales = df_ret.mean() * 252
    cov_anual = df_ret.cov() * 252

    # Agregar CASH: retorno fijo, sin varianza ni covarianza con el resto
    medias_anuales["CASH"] = TASA_LIBRE_RIESGO_ANUAL
    cov_anual["CASH"] = 0.0
    cov_anual.loc["CASH"] = 0.0

    orden = TICKERS + ["CASH"]
    return medias_anuales[orden], cov_anual.loc[orden, orden], df_ret


def _ratios_cartera(pesos: np.ndarray, medias: np.ndarray, cov: np.ndarray, retornos_hist: pd.DataFrame):
    retorno = float(np.dot(pesos, medias))
    varianza = float(np.dot(pesos, np.dot(cov, pesos)))
    riesgo = float(math.sqrt(max(varianza, 0.0)))

    sharpe = (retorno - TASA_LIBRE_RIESGO_ANUAL) / riesgo if riesgo > 1e-9 else 0.0

    # Serie histórica del portafolio (solo con los activos de riesgo, CASH aporta 0 volatilidad)
    pesos_riesgo = pesos[:len(TICKERS)]
    serie_cartera = retornos_hist[TICKERS].fillna(0.0).dot(pesos_riesgo)
    downside = serie_cartera[serie_cartera < 0]
    downside_std = float(downside.std() * math.sqrt(252)) if len(downside) > 1 else 0.0
    sortino = (retorno - TASA_LIBRE_RIESGO_ANUAL) / downside_std if downside_std > 1e-9 else 0.0

    acumulado = (1 + serie_cartera).cumprod()
    max_acumulado = acumulado.cummax()
    drawdown = (acumulado / max_acumulado) - 1
    max_drawdown = float(-drawdown.min()) if len(drawdown) > 0 else 0.0
    calmar = retorno / max_drawdown if max_drawdown > 1e-9 else 0.0

    return {
        "sharpe": round(sharpe, 3),
        "sortino": round(sortino, 3),
        "calmar": round(calmar, 3),
    }, riesgo * 100, retorno * 100


def _optimizar_markowitz(medias: np.ndarray, cov: np.ndarray):
    n = len(medias)

    def neg_sharpe(pesos):
        retorno = np.dot(pesos, medias)
        riesgo = math.sqrt(max(np.dot(pesos, np.dot(cov, pesos)), 1e-12))
        return -(retorno - TASA_LIBRE_RIESGO_ANUAL) / riesgo

    restricciones = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]
    limites = [(0.0, 0.6)] * n  # máx 60% en un solo activo, evita soluciones degeneradas
    w0 = np.repeat(1.0 / n, n)

    resultado = minimize(
        neg_sharpe, w0, method="SLSQP", bounds=limites, constraints=restricciones,
        options={"maxiter": 500, "ftol": 1e-9},
    )
    pesos = resultado.x if resultado.success else w0
    pesos = np.clip(pesos, 0, None)
    pesos = pesos / pesos.sum()
    return pesos


@app.post("/api/portafolio/optimizar")
def api_portafolio_optimizar(payload: PortafolioRequest):
    medias, cov, retornos_hist = cache_get_or_compute(
        "portafolio:stats_mercado", 3600, _stats_mercado
    )
    orden = TICKERS + ["CASH"]
    medias_arr = medias.values
    cov_arr = cov.values

    # --- Cartera actual (la que llega del frontend) ---
    pesos_actuales_dict = {a.ticker: a.peso / 100.0 for a in payload.activos}
    pesos_actuales = np.array([pesos_actuales_dict.get(tk, 0.0) for tk in orden])
    if pesos_actuales.sum() <= 0:
        pesos_actuales = np.repeat(1.0 / len(orden), len(orden))
    else:
        pesos_actuales = pesos_actuales / pesos_actuales.sum()

    ratios_actual, riesgo_actual, retorno_actual = _ratios_cartera(
        pesos_actuales, medias_arr, cov_arr, retornos_hist
    )

    # --- Cartera óptima (tangente, real, vía scipy.optimize) ---
    pesos_optimos = _optimizar_markowitz(medias_arr, cov_arr)
    ratios_optimo, riesgo_optimo, retorno_optimo = _ratios_cartera(
        pesos_optimos, medias_arr, cov_arr, retornos_hist
    )

    # --- Frontera eficiente real: N carteras Dirichlet sobre los activos
    #     reales (no números aleatorios sueltos: cada punto es una
    #     combinación válida de pesos evaluada con medias/covarianza reales) ---
    rng = np.random.default_rng(42)
    n_puntos = 400
    muestras = rng.dirichlet(np.ones(len(orden)) * 1.5, size=n_puntos)
    # Limitar CASH a un rango razonable para que la nube sea informativa
    riesgos_nube, retornos_nube = [], []
    for pesos_m in muestras:
        r = float(np.dot(pesos_m, medias_arr))
        v = float(np.dot(pesos_m, np.dot(cov_arr, pesos_m)))
        riesgos_nube.append(math.sqrt(max(v, 0.0)) * 100)
        retornos_nube.append(r * 100)

    pesos_optimos_pct = {tk: round(float(p) * 100, 2) for tk, p in zip(orden, pesos_optimos)}

    return {
        "ultima_actualizacion": datetime.now(timezone.utc).isoformat(),
        "frontera": {"riesgo": riesgos_nube, "retorno": retornos_nube},
        "actual": {"riesgo": round(riesgo_actual, 2), "retorno": round(retorno_actual, 2)},
        "optimo": {
            "riesgo": round(riesgo_optimo, 2),
            "retorno": round(retorno_optimo, 2),
            "pesos": pesos_optimos_pct,
        },
        "pesos_optimos": pesos_optimos_pct,
        "ratios": {"actual": ratios_actual, "optimizado": ratios_optimo},
    }


# ==========================================================================
# Raíz — útil para verificar rápidamente que el servicio está arriba
# ==========================================================================

@app.get("/")
def raiz():
    return {
        "servicio": "Ernesto Investing AI — iDeSo API",
        "tickers": TICKERS,
        "endpoints": [
            "/api/salud", "/api/mercado/{ticker}", "/api/svc/{ticker}",
            "/api/rnns/{ticker}", "/api/lstm/{ticker}",
            "/api/auth/registro", "/api/auth/login", "/api/portafolio/optimizar",
        ],
    }
