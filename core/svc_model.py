"""
Clasificador SVC (BUY/SELL) — puerto directo de la celda 14 del notebook.
"""
import pandas as pd
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

from core.mercado import descargar_ohlcv

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


def calcular_features_y_target_svc(df: pd.DataFrame):
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
