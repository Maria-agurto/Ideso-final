# Opción A — Notebooks modulares (`notebooks/`)

Proyecto del curso **iDeSo** que arma un pipeline completo de datos e IA para el mercado de acciones mineras: ingesta de precios reales, 3 familias de modelos (SVC, RNN×4, LSTM regresor), autenticación y optimización de portafolios, todo servido por una API que **solo lee de MongoDB** (nunca recalcula nada pesado en el momento de la petición).

**Filosofía:** entrenar una sola vez en Colab (offline), guardar en MongoDB, servir instantáneo. Es la contraparte de la Opción B (`backend/Ernesto_Investing_AI_iDeSo_Mongo.ipynb`), que entrena al vuelo con caché — ver `README.md` en la raíz para la comparación completa.

**Flujo de datos:** Yahoo Finance → MongoDB Atlas → modelos (SVC / RNN / LSTM) → MongoDB Atlas → API FastAPI (solo lectura) → Frontend.

No hay datos simulados: los 5 notebooks leen y escriben siempre contra MongoDB.

## Integrantes:
- Porras Cahuana Daniela Alekzya 
- Huallpacuna Gutierrez Jean Piero 
- Machaca Ponce Sebastian Emanuel 
- Cruz Reyes Martín Alejandro 
- Cruz Chavez Mariano Abel 
- Agurto Chuye María Fernanda


## Tickers analizados

Cinco activos mineros:

- `FSM`
- `VOLCABC1.LM`
- `ABX.TO`
- `BVN`
- `BHP`

## Estructura del repo

```
notebooks/
├── Notebook1_Ingesta_Datos.ipynb         # Descarga OHLCV + indicadores → MongoDB
├── Notebook2_SVC_Clasificacion.ipynb     # Entrena el clasificador SVC (BUY/SELL)
├── Notebook3_API_FastAPI.ipynb           # Expone los 8 endpoints (lee de MongoDB)
├── Notebook4_RNN_Clasificadores.ipynb    # Entrena LSTM/BiLSTM/GRU/SimpleRNN → MongoDB
└── Notebook5_LSTM_Regresor.ipynb         # Entrena el regresor de precios → MongoDB
```

## Notebooks

### 1. Ingesta de Datos (`Notebook1_Ingesta_Datos.ipynb`)
- Descarga datos OHLCV de 1 año por ticker desde Yahoo Finance (`yfinance`).
- Corrige el `MultiIndex` que devuelve `yfinance`.
- Calcula indicadores técnicos: `SMA_20`, `SMA_50`, `EMA_12`, `EMA_26`, `RSI_14`.
- Guarda todo en la colección `precios_ohlcv` de MongoDB Atlas (borra duplicados de tickers previos antes de insertar).

### 2. Clasificación SVC (`Notebook2_SVC_Clasificacion.ipynb`)
- Lee `precios_ohlcv` guardada por el Notebook 1.
- Genera features a partir de los indicadores técnicos y un target BUY/SELL.
- Split temporal 80/20 (`shuffle=False`) para no filtrar información futura.
- Entrena un `SVC` con `GridSearchCV` usando `TimeSeriesSplit` como validación cruzada.
- Evalúa con accuracy, precision, recall, F1 y matriz de confusión.
- Calcula la señal actual (BUY/SELL) por ticker y guarda resultados en `predicciones` y `metricas_modelos`.

### 3. Clasificadores RNN (`Notebook4_RNN_Clasificadores.ipynb`)
- Lee `precios_ohlcv` (no vuelve a descargar de yfinance, usa los mismos datos que el SVC).
- Entrena 4 arquitecturas (LSTM, BiLSTM, GRU, SimpleRNN) por cada uno de los 5 tickers — 20 modelos en total.
- Ventanas deslizantes de 10 días, features `Close/SMA_20/EMA_12/RSI_14`.
- Guarda accuracy/precision/recall/F1 y la señal BUY/SELL/HOLD de cada arquitectura en la colección `clasificaciones_rnn` (un documento por ticker con los 4 modelos adentro).
- También exporta un respaldo en `data/clasificaciones_rnn.json`.

### 4. Regresor LSTM (`Notebook5_LSTM_Regresor.ipynb`)
- Lee `precios_ohlcv`. Ventana de 60 días, red LSTM univariada sobre el precio de cierre.
- Calcula RMSE, MAE y R² sobre el set de validación temporal.
- Genera una proyección autoregresiva a 30 días con bandas de confianza al 95%.
- Guarda todo en la colección `predicciones_lstm`. También exporta `data/predicciones_lstm.json`.
- **Nota:** el horizonte queda fijo en 30 días al pre-calcularse (a diferencia de la Opción B, que puede recalcular cualquier horizonte al vuelo).

### 5. API FastAPI (`Notebook3_API_FastAPI.ipynb`)
- API de solo lectura sobre MongoDB para 7 de los 8 endpoints (no recalcula nada pesado).
- Única excepción: `/api/portafolio/optimizar`, que sí calcula al vuelo porque es una optimización numérica barata (`scipy.optimize`, no un entrenamiento de red).
- CORS habilitado (`allow_origins=['*']`) porque el frontend corre en otro dominio (GitHub Pages).
- Credenciales (`MONGO_URI`, `NGROK_AUTHTOKEN`) leídas de forma segura con `userdata.get()` — nunca hardcodeadas.
- Se expone a internet con **ngrok** para poder conectarse desde el frontend.

**Endpoints:**

| Método | Endpoint | Lee de (colección) |
|---|---|---|
| GET | `/api/salud` | — (ping a MongoDB) |
| GET | `/api/mercado/{ticker}` | `precios_ohlcv` |
| GET | `/api/svc/{ticker}` | `predicciones`, `metricas_modelos` |
| GET | `/api/rnns/{ticker}` | `clasificaciones_rnn` |
| GET | `/api/lstm/{ticker}` | `predicciones_lstm` |
| POST | `/api/auth/registro` | `usuarios` (escribe) |
| POST | `/api/auth/login` | `usuarios` (lee) |
| POST | `/api/portafolio/optimizar` | `precios_ohlcv` (calcula al vuelo) |

## Frontend

Los 11 módulos de `frontend/`, pensados para GitHub Pages (Tailwind CSS vía CDN + Plotly.js/Chart.js). El portal (`index.html`) guarda la URL de ngrok en `sessionStorage('apiUrl')`, y todos los módulos conectados la reutilizan automáticamente — no importa si la URL apunta a esta Opción A o a la Opción B, porque ambas exponen exactamente el mismo contrato de 8 endpoints.

## Cómo correrlo

1. Ejecutar **Notebook 1** para poblar MongoDB con datos OHLCV.
2. Ejecutar **Notebook 2** para entrenar el SVC y guardar señales/métricas.
3. Ejecutar **Notebook 4** para entrenar las RNN (tarda varios minutos: 20 modelos).
4. Ejecutar **Notebook 5** para entrenar el regresor LSTM (5 modelos).
5. Ejecutar **Notebook 3** para levantar la API (te da una URL pública de ngrok). Los pasos 3 y 4 deben correr *antes*, porque la API solo lee lo que ya quedó guardado.
6. Abrir `frontend/index.html`, pegar esa URL de ngrok y conectar.
7. Navegar a cualquiera de los 11 módulos.

## Stack

- **Datos:** Python, `yfinance`, MongoDB Atlas
- **Modelos:** `scikit-learn` (SVC), `TensorFlow/Keras` (LSTM/BiLSTM/GRU/SimpleRNN), `scipy` (Markowitz)
- **API:** FastAPI + ngrok
- **Frontend:** HTML, Tailwind CSS, Plotly.js, Chart.js
