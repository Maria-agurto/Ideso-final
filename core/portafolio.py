"""
Optimización de portafolios (Markowitz) — puerto directo de la celda 22
del notebook.
"""
import math
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import streamlit as st
from scipy.optimize import minimize

from core.mercado import TICKERS, descargar_ohlcv

ACTIVOS_PORTAFOLIO = TICKERS + ["CASH"]
TASA_LIBRE_RIESGO_ANUAL = 0.02


def _retornos_diarios(ticker: str) -> pd.Series:
    df = descargar_ohlcv(ticker, period="1y")
    if df.empty:
        return pd.Series(dtype=float)
    return df["Close"].pct_change().dropna()


@st.cache_data(ttl=3600, show_spinner="Calculando estadísticas de mercado…")
def _stats_mercado():
    series = {tk: _retornos_diarios(tk) for tk in TICKERS}

    df_ret = pd.DataFrame(series).dropna(how="all").fillna(0.0)

    medias_anuales = df_ret.mean() * 252
    cov_anual = df_ret.cov() * 252

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

    pesos_riesgo = pesos[: len(TICKERS)]
    serie_cartera = retornos_hist[TICKERS].fillna(0.0).dot(pesos_riesgo)
    downside = serie_cartera[serie_cartera < 0]
    downside_std = float(downside.std() * math.sqrt(252)) if len(downside) > 1 else 0.0
    sortino = (retorno - TASA_LIBRE_RIESGO_ANUAL) / downside_std if downside_std > 1e-9 else 0.0

    acumulado = (1 + serie_cartera).cumprod()
    max_acumulado = acumulado.cummax()
    drawdown = (acumulado / max_acumulado) - 1
    max_drawdown = float(-drawdown.min()) if len(drawdown) > 0 else 0.0
    calmar = retorno / max_drawdown if max_drawdown > 1e-9 else 0.0

    return (
        {"sharpe": round(sharpe, 3), "sortino": round(sortino, 3), "calmar": round(calmar, 3)},
        riesgo * 100,
        retorno * 100,
    )


def _optimizar_markowitz(medias: np.ndarray, cov: np.ndarray):
    n = len(medias)

    def neg_sharpe(pesos):
        retorno = np.dot(pesos, medias)
        riesgo = math.sqrt(max(np.dot(pesos, np.dot(cov, pesos)), 1e-12))
        return -(retorno - TASA_LIBRE_RIESGO_ANUAL) / riesgo

    restricciones = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]
    limites = [(0.0, 0.6)] * n
    w0 = np.repeat(1.0 / n, n)

    resultado = minimize(
        neg_sharpe, w0, method="SLSQP", bounds=limites, constraints=restricciones,
        options={"maxiter": 500, "ftol": 1e-9},
    )
    pesos = resultado.x if resultado.success else w0
    pesos = np.clip(pesos, 0, None)
    return pesos / pesos.sum()


def optimizar_portafolio(pesos_actuales_pct: dict[str, float]) -> dict:
    """pesos_actuales_pct: {ticker: peso_en_porcentaje}. Ej: {"FSM": 35, ...}"""
    medias, cov, retornos_hist = _stats_mercado()
    orden = TICKERS + ["CASH"]
    medias_arr = medias.values
    cov_arr = cov.values

    pesos_actuales = np.array([pesos_actuales_pct.get(tk, 0.0) / 100.0 for tk in orden])
    if pesos_actuales.sum() <= 0:
        pesos_actuales = np.repeat(1.0 / len(orden), len(orden))
    else:
        pesos_actuales = pesos_actuales / pesos_actuales.sum()

    ratios_actual, riesgo_actual, retorno_actual = _ratios_cartera(pesos_actuales, medias_arr, cov_arr, retornos_hist)

    pesos_optimos = _optimizar_markowitz(medias_arr, cov_arr)
    ratios_optimo, riesgo_optimo, retorno_optimo = _ratios_cartera(pesos_optimos, medias_arr, cov_arr, retornos_hist)

    rng = np.random.default_rng(42)
    muestras = rng.dirichlet(np.ones(len(orden)) * 1.5, size=400)
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
        "optimo": {"riesgo": round(riesgo_optimo, 2), "retorno": round(retorno_optimo, 2), "pesos": pesos_optimos_pct},
        "ratios": {"actual": ratios_actual, "optimizado": ratios_optimo},
    }
