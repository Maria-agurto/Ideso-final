"""
Regresor LSTM de precio — puerto directo de la celda 18 del notebook.
"""
import math

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import MinMaxScaler

from core.mercado import descargar_ohlcv

VENTANA_LSTM = 60
PORCENTAJE_TRAIN = 0.8


def entrenar_lstm_regresor(ticker: str, horizonte: int) -> dict:
    try:
        import tensorflow as tf
        from tensorflow.keras.layers import Dense, Dropout, LSTM
        from tensorflow.keras.models import Sequential
    except ImportError:
        return {"error": "TensorFlow no está instalado. Agrega 'tensorflow' a requirements.txt para usar este módulo."}

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
    scaler.fit(cierres[:corte])
    cierres_s = scaler.transform(cierres)

    X, y = [], []
    for i in range(len(cierres_s) - VENTANA_LSTM):
        X.append(cierres_s[i:i + VENTANA_LSTM, 0])
        y.append(cierres_s[i + VENTANA_LSTM, 0])
    X, y = np.array(X), np.array(y)

    corte_vent = max(1, corte - VENTANA_LSTM)
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

    residuos = y_real_test - y_pred_test
    std_residuo = float(np.std(residuos)) if len(residuos) > 1 else float(np.std(y_real_test)) * 0.05

    ventana_actual = cierres_s[-VENTANA_LSTM:, 0].tolist()
    ultima_fecha = pd.Timestamp(df["Fecha"].iloc[-1])
    proyeccion_futura = []
    for paso in range(1, horizonte + 1):
        entrada = np.array(ventana_actual[-VENTANA_LSTM:]).reshape(1, VENTANA_LSTM, 1)
        pred_s = float(modelo.predict(entrada, verbose=0).flatten()[0])
        pred_usd = float(scaler.inverse_transform([[pred_s]])[0][0])
        ventana_actual.append(pred_s)

        ancho_banda = std_residuo * 1.96 * math.sqrt(paso)
        fecha_pred = ultima_fecha + pd.Timedelta(days=paso)
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
