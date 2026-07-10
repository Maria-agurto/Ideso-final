"""
Core Predictivo — ensamble LSTM / BiLSTM / GRU / SimpleRNN (clasificación
de dirección). Puerto directo de la celda 16 del notebook.

TensorFlow se importa perezosamente dentro de entrenar_rnns() para que el
resto de la app (mercado, SVC, portafolio) funcione aunque tensorflow no
esté instalado.
"""
from datetime import datetime, timezone

import numpy as np
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from sklearn.preprocessing import MinMaxScaler

from core.mercado import descargar_ohlcv

VENTANA_RNN = 10
FEATURES_RNN = ["Close", "SMA_20", "EMA_12", "RSI_14"]
PORCENTAJE_TRAIN = 0.8


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
    try:
        import tensorflow as tf
        from tensorflow.keras.layers import GRU, LSTM, Bidirectional, Dense, SimpleRNN
        from tensorflow.keras.models import Sequential
    except ImportError:
        return {"error": "TensorFlow no está instalado. Agrega 'tensorflow' a requirements.txt para usar este módulo."}

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

    ultima_ventana_raw = X_raw[-VENTANA_RNN:]
    ultima_ventana_s = scaler.transform(ultima_ventana_raw).reshape(1, VENTANA_RNN, n_feat)

    resultados = {}
    for kind in ["lstm", "bilstm", "gru", "simplernn"]:
        modelo = construir(kind)
        early_stop = tf.keras.callbacks.EarlyStopping(monitor="loss", patience=5, restore_best_weights=True)
        modelo.fit(X_train_s, y_train, epochs=40, batch_size=16, verbose=0, callbacks=[early_stop])
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
