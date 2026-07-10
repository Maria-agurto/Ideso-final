# iDeSo — Ernesto Investing AI

Proyecto del curso **iDeSo** que arma un pipeline completo de datos e IA para el mercado de acciones mineras: ingesta de precios reales, un modelo de clasificación BUY/SELL, una API que expone todo, y un frontend que lo consume.

**Flujo de datos:** Yahoo Finance → MongoDB Atlas → modelo SVC → API FastAPI → Dashboard web.

No hay datos simulados: los tres módulos (ingesta, modelo y API) leen y escriben siempre contra MongoDB.

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
ideso-eq5/
├── notebooks/
│   ├── Notebook1_Ingesta_Datos.ipynb       # Descarga OHLCV + indicadores → MongoDB
│   ├── Notebook2_SVC_Clasificacion.ipynb   # Entrena el clasificador SVC (BUY/SELL)
│   └── Notebook3_API_FastAPI.ipynb         # Expone la API que lee de MongoDB
└── frontend/
    ├── index.html            # Portal: conexión con la API (URL de ngrok)
    ├── modulo_mercado.html   # Dashboard de mercado (precios + indicadores técnicos)
    └── modulo_svc.html       # Panel de señales del clasificador SVC
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

### 3. API FastAPI (`Notebook3_API_FastAPI.ipynb`)
- API de solo lectura sobre MongoDB (no recalcula nada).
- CORS habilitado (`allow_origins=['*']`) porque el frontend corre en otro dominio (GitHub Pages).
- Se expone a internet con **ngrok** para poder conectarse desde el frontend.

**Endpoints:**

| Método | Endpoint | Descripción |
|---|---|---|
| GET | `/api/salud` | Verifica que la API esté arriba. |
| GET | `/api/mercado/{ticker}` | Histórico OHLCV + indicadores de un ticker (por defecto, últimos 100 registros). |
| GET | `/api/svc/{ticker}` | Última señal BUY/SELL y métricas del modelo SVC para un ticker. |

## Frontend

Tres páginas estáticas (Tailwind CSS vía CDN + Plotly.js para gráficos), pensadas para GitHub Pages:

- **`index.html`** — Portal de entrada: pegás la URL pública de ngrok de la API y valida la conexión (`/api/salud`) antes de habilitar el resto.
- **`modulo_mercado.html`** — Dashboard de mercado: selector de tickers, precios OHLCV e indicadores técnicos en vivo (`/api/mercado/{ticker}`).
- **`modulo_svc.html`** — Panel del clasificador: señal BUY/SELL más reciente y matriz de confusión del modelo (`/api/svc/{ticker}`).

## Cómo correrlo

1. Ejecutar **Notebook 1** para poblar MongoDB con datos OHLCV.
2. Ejecutar **Notebook 2** para entrenar el modelo y guardar señales/métricas.
3. Ejecutar **Notebook 3** para levantar la API (te da una URL pública de ngrok).
4. Abrir `frontend/index.html`, pegar esa URL de ngrok y conectar.
5. Navegar a los dashboards (`modulo_mercado.html`, `modulo_svc.html`) para ver datos y señales en vivo.

## Stack

- **Datos:** Python, `yfinance`, MongoDB Atlas
- **Modelo:** `scikit-learn` (SVC, GridSearchCV, TimeSeriesSplit)
- **API:** FastAPI + ngrok
- **Frontend:** HTML, Tailwind CSS, Plotly.js
