# Cómo correr el backend real y conectar los módulos

## 1. Instalar dependencias

```bash
cd backend
pip install -r requirements.txt
```

(TensorFlow es necesario solo para los módulos RNN/LSTM — es la dependencia
más pesada; si tu máquina es muy limitada, esos dos endpoints tardarán más
la primera vez que se piden para cada ticker, pero luego quedan cacheados).

## 2. Levantar la API

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

Si vas a correrlo en Google Colab (como el proyecto original) para exponerlo
a un frontend estático (GitHub Pages), usa `pyngrok` igual que en el
Notebook 3:

```python
!pip install fastapi uvicorn pyngrok yfinance scikit-learn scipy tensorflow --quiet
from pyngrok import ngrok
import nest_asyncio, uvicorn
nest_asyncio.apply()
public_url = ngrok.connect(8000)
print(public_url)
uvicorn.run(app, host="0.0.0.0", port=8000)
```

## 3. Conectar el frontend

1. Abre `frontend/index.html`, pega la URL pública (la de ngrok, o
   `http://localhost:8000` si corres todo en tu máquina) y conecta.
2. Navega a cualquier módulo: la URL queda guardada en `sessionStorage` y
   todos los módulos conectados la reutilizan automáticamente.

## Qué quedó conectado a datos reales (sin simulación)

| Módulo | Endpoint | Fuente real |
|---|---|---|
| Portal (salud) | `GET /api/salud` | Ping a Yahoo Finance |
| M2 Mercado | `GET /api/mercado/{ticker}` | OHLCV + SMA/EMA/RSI de Yahoo Finance |
| M3 SVC | `GET /api/svc/{ticker}` | Clasificador SVC entrenado con `GridSearchCV` + `TimeSeriesSplit` |
| M4 LSTM (clasificadores) | `GET /api/rnns/{ticker}` | LSTM/BiLSTM/GRU/SimpleRNN entrenados con TensorFlow |
| M4 LSTM (regresor) | `GET /api/lstm/{ticker}?horizonte=N` | Regresor LSTM real, proyección iterativa a N días |
| M6 Core Predictivo | usa `/api/rnns/{ticker}` para los 5 tickers | Igual que M4 |
| M1 Autenticación | `POST /api/auth/registro`, `POST /api/auth/login` | Usuarios reales en SQLite (`backend/investai.db`), contraseñas con hash PBKDF2-SHA256 + salt |
| M9 Portafolios | `POST /api/portafolio/optimizar` | Optimización de Markowitz real (`scipy.optimize`) sobre retornos históricos reales; Sharpe/Sortino/Calmar calculados con datos reales |

Todos los endpoints se cachean en memoria (1h para mercado/SVC, 6h para
RNN/LSTM que son costosos de entrenar) para no re-descargar ni re-entrenar
en cada click.

## Qué quedó SIN conectar a un backend (y por qué)

- **M5 Análisis NLP** — las noticias están hardcodeadas en el HTML. Conectarlo
  de verdad requiere contratar/usar una API de noticias financieras (no hay
  ninguna en el proyecto original). Si quieres, puedo integrar una API de
  noticias gratuita (ej. NewsAPI, Finnhub) y análisis de sentimiento real.
- **M7 Estrategias** — es una calculadora de payoff de opciones que opera
  sobre los "legs" que el propio usuario ingresa; matemáticamente no necesita
  un backend (ya es una función pura). Si quisieras precios de opciones
  reales, haría falta una fuente de datos de opciones (Yahoo Finance no la
  trae vía `yfinance` de forma confiable).
- **M8 Órdenes** — el HTML menciona explícitamente "TWS API" (Interactive
  Brokers). Conectarlo a una ejecución real de órdenes requiere una cuenta
  de bróker con permisos de trading — está fuera del alcance de un proyecto
  académico y no es algo que deba automatizarse sin que lo pidas
  explícitamente.
- **M10 Consola** — es un panel de control (kill-switch, entorno activo), no
  muestra datos de mercado; no hay nada que conectar.
- **M11 Backtesting** — sigue usando `Math.random()` para simular resultados.
  Si quieres, el siguiente paso natural es reemplazarlo con un backtest real:
  correr la señal SVC (o las RNN) día a día sobre el histórico y calcular el
  P&L real vs. buy-and-hold. No estaba incluido en el alcance que elegiste,
  pero es la extensión más directa de lo ya construido.

## Nota sobre las pruebas hechas

Este entorno de desarrollo no tiene acceso de red a Yahoo Finance ni a
paquetes pesados como TensorFlow, así que **no pude ejecutar el backend
contra datos reales de mercado**. Sí probé toda la lógica (mercado, SVC,
auth, portafolio) con datos sintéticos que imitan la forma de los datos
reales, y los 4 endpoints devolvieron exactamente el contrato JSON que cada
HTML espera. Los endpoints de RNN/LSTM no se pudieron ejecutar en este
entorno (requieren TensorFlow), así que revísalos con más atención la
primera vez que los corras en Colab o en tu máquina.
