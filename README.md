# Ernesto Investing AI — iDeSo · UNMSM · FISI

Sistema web de apoyo a decisiones de inversión bursátil con IA, para 5 tickers mineros
(`FSM`, `VOLCABC1.LM`, `ABX.TO`, `BVN`, `BHP`). El frontend (`frontend/`, 11 módulos,
GitHub Pages) es el mismo sin importar qué backend uses — ambos exponen exactamente
el mismo contrato de 8 endpoints, así que solo cambia qué URL de ngrok pegas en el
portal (`index.html`).

Este repo documenta **2 formas distintas de implementar el mismo backend**. Ninguna es
"la incorrecta" — son dos arquitecturas válidas con trade-offs distintos.

## Opción A — Notebooks modulares (`notebooks/`)

5 notebooks separados, cada uno con una responsabilidad: ingesta, SVC, RNN, LSTM y
API. Los modelos se **entrenan una sola vez de antemano** (offline) y quedan guardados
en MongoDB; la API solo lee, nunca reentrenar. Es la arquitectura "clásica" que pide el
Cap. III del documento de especificaciones del curso (Alternativa A).

- ✅ Respuestas siempre instantáneas (no hay que esperar a que entrene nada).
- ✅ Más fácil de explicar/documentar capítulo por capítulo en el informe (cada
  notebook = un capítulo).
- ⚠️ Si el mercado cambia, hay que volver a correr los notebooks 1, 2, 4 y 5 a mano
  para refrescar las predicciones.

Ver [`README_opcionA_notebooks_modulares.md`](./README_opcionA_notebooks_modulares.md).

## Opción B — Backend consolidado (`backend/Ernesto_Investing_AI_iDeSo_Mongo.ipynb`)

Un solo notebook con los 8 endpoints. Entrena/calcula **al vuelo** la primera vez que
se pide un ticker, y cachea el resultado en MongoDB por unas horas.

- ✅ Siempre usa datos frescos de mercado sin que nadie tenga que re-correr nada a mano.
- ✅ Un solo archivo, más simple de desplegar.
- ⚠️ La primera petición de RNN/LSTM para cada ticker puede tardar (está entrenando
  20 modelos en vivo) — hay que "calentar" la caché antes de grabar el video de
  exposición (ver el README de esa opción).

Ver [`README_opcionB_backend_consolidado.md`](./README_opcionB_backend_consolidado.md).

## Estructura del repo

```
ernesto-investing-ai/
├── README.md                                  (este archivo)
├── README_opcionA_notebooks_modulares.md
├── README_opcionB_backend_consolidado.md
├── frontend/
│   ├── index.html                (portal: conecta con cualquiera de las 2 opciones)
│   ├── modulo_mercado.html       (dashboard con Plotly.js)
│   ├── modulo_svc.html           (clasificador SVC con Plotly.js)
│   └── ... (otros 9 módulos)
├── notebooks/                    ← Opción A
│   ├── Notebook1_Ingesta_Datos.ipynb
│   ├── Notebook2_SVC_Clasificacion.ipynb
│   ├── Notebook3_API_FastAPI.ipynb
│   ├── Notebook4_RNN_Clasificadores.ipynb
│   └── Notebook5_LSTM_Regresor.ipynb
├── backend/                      ← Opción B
│   ├── Ernesto_Investing_AI_iDeSo_Mongo.ipynb
│   └── requirements.txt
└── data/                         (respaldos JSON generados por los Notebooks 4 y 5)
```

## Integrantes

- Porras Cahuana Daniela Alekzya
- Huallpacuna Gutierrez Jean Piero
- Machaca Ponce Sebastian Emanuel
- Cruz Reyes Martín Alejandro
- Cruz Chavez Mariano Abel
- Agurto Chuye María Fernanda

## Qué usar en el informe

Si el equipo decide quedarse con **ambas** opciones (como en este repo), el Cap. V del
informe Word debe documentar las dos arquitecturas y sus colecciones de MongoDB por
separado — no mezclarlas, porque cada una escribe en colecciones distintas:

| | Opción A | Opción B |
|---|---|---|
| Mercado/SVC | `precios_ohlcv`, `predicciones`, `metricas_modelos` | `cache_modelos` (resultado cacheado) |
| RNN | `clasificaciones_rnn` | `cache_modelos` |
| LSTM | `predicciones_lstm` | `cache_modelos` |
| Usuarios | `usuarios` | `usuarios` (misma colección, mismo esquema) |
| Extra | — | `logs_resultados` (historial de cada respuesta servida) |
