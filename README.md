# Ernesto Investing AI — versión unificada en Streamlit

Esta es la versión "todo en uno" del proyecto iDeSo (eq5). Reemplaza el
esquema anterior:

```
Antes:  Notebook (Colab) → FastAPI → ngrok → GitHub Pages (11 HTMLs sueltos)
Ahora:  Streamlit (app.py + pages/) → MongoDB Atlas directo
```

Ya **no hace falta ngrok ni el notebook de Colab corriendo**: toda la
lógica que antes vivía en las celdas del notebook (`descargar_ohlcv`,
`entrenar_svc`, `entrenar_rnns`, `entrenar_lstm_regresor`, Markowitz,
auth con PBKDF2) ahora vive en `core/` como funciones Python normales que
Streamlit llama directamente, en el mismo proceso.

## Estructura

```
app.py                              → Portal (equivalente a index.html)
core/
  db.py                             → Conexión a MongoDB Atlas (st.cache_resource)
  cache_utils.py                    → Caché persistente en Mongo + logging (igual que el notebook)
  mercado.py                        → OHLCV + indicadores técnicos (yfinance)
  svc_model.py                      → Clasificador SVC (GridSearchCV + TimeSeriesSplit)
  rnn_model.py                      → Ensamble LSTM/BiLSTM/GRU/SimpleRNN (clasificación)
  lstm_model.py                     → Regresor LSTM de precio (con banda de confianza)
  portafolio.py                     → Optimización de Markowitz (scipy.optimize)
  auth.py                           → Registro/login (PBKDF2-SHA256 + salt, en MongoDB)
  session_guard.py                  → Guard de sesión (reemplaza verificarSesion() de los HTML)
pages/
  1_🔑_Autenticacion.py              → modulo6.1-autenticacion.html
  2_📊_Dashboard_Mercado.py          → modulo_mercado.html
  3_🤖_Clasificador_SVC.py           → modulo_svc.html
  4_🔮_Pronosticos_LSTM.py           → modulo6.4-lstm.html
  5_🧠_Core_Predictivo_RNNs.py       → modulo6.6-core-predictivo-central.html
  6_📰_Sentimiento_NLP.py            → modulo6.5-nlp-operaciones.html (datos de ejemplo, igual que el original)
  7_🎯_Estrategias_Opciones.py       → modulo6.7-estrategias.html
  8_🧾_Ordenes_Paper_Trading.py      → modulo6.8-ordenes.html
  9_📐_Portafolios_Markowitz.py      → modulo6.9-portafolio.html (ahora con Markowitz REAL, no simulado)
  10_🛠️_Consola_Admin.py            → modulo6.10-consola.html (con stats reales de Mongo)
  11_📈_Backtesting.py               → modulo6.11-backtesting.html (sigue simulado, como en el original)
```

## Cómo correrlo

1. Instala dependencias:
   ```bash
   pip install -r requirements.txt
   ```
   Si no quieres usar TensorFlow (páginas 4 y 5), puedes borrar la línea
   `tensorflow` del `requirements.txt` — el resto de la app sigue
   funcionando igual, esas dos páginas solo muestran un aviso.

2. Configura tu conexión a MongoDB Atlas:
   ```bash
   cp .streamlit/secrets.toml.example .streamlit/secrets.toml
   ```
   Y pega tu connection string real (`mongodb+srv://usuario:pass@cluster...`)
   en `MONGO_URI`. En Atlas → Network Access agrega `0.0.0.0/0` si vas a
   desplegar en Streamlit Community Cloud.

3. Corre la app:
   ```bash
   streamlit run app.py
   ```

## Diferencias clave respecto a la versión HTML + ngrok

- **Sesión**: antes `localStorage.getItem('investai_user')` en cada HTML;
  ahora `st.session_state["investai_user"]`, controlado por
  `core/session_guard.requiere_sesion()` en cada página.
- **API URL**: antes se pegaba manualmente la URL de ngrok en el portal
  (`sessionStorage.setItem('apiUrl', ...)`); ahora no existe ese paso —
  Streamlit llama las funciones de `core/` directo.
- **Caché de modelos caros** (SVC/RNNs/LSTM): sigue en la colección
  `cache_modelos` de MongoDB con el mismo esquema y TTL que el notebook
  (1h para SVC, 6h para RNNs/LSTM), vía
  `core/cache_utils.cache_get_or_compute_mongo`.
- **Log histórico**: cada resultado se sigue insertando en
  `logs_resultados`, igual que `log_resultado()` en el notebook.
- **Portafolio**: el HTML original (`modulo6.9-portafolio.html`) mostraba
  una nube Monte Carlo **simulada** con pesos fijos hardcodeados. En esta
  versión, `core/portafolio.py` reproduce el cálculo real del notebook
  (retornos/covarianzas de Yahoo Finance + `scipy.optimize.minimize` para
  Sharpe máximo).
- **NLP y Backtesting** siguen con datos de ejemplo/simulados, tal como
  estaban en los HTML originales — el notebook no tiene celdas para esos
  dos módulos todavía.

## Nota sobre el repo de GitHub (Ideso-final)

Este `app.py` reemplaza al `app.py` que hay en el repo (el que ignoraste).
Si me pasas el contenido de las carpetas `frontend/` y `backend/` de ese
repo, puedo ajustar cualquier detalle de contrato de datos que difiera de
lo que asumí acá (nombres de campos, tickers adicionales, etc.).
