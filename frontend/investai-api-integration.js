/**
 * ============================================================
 * ERNESTO INVESTING AI — Módulo de Integración API REST
 * Curso: iDeSo | FISI - UNMSM
 * Archivo: investai-api-integration.js
 *
 * INSTRUCCIÓN DE USO:
 * 1. Incluir este script en cada módulo HTML con:
 *    <script src="investai-api-integration.js"></script>
 * 2. ⚠️ ÚNICA LÍNEA A CAMBIAR CADA VEZ QUE SE REINICIA COLAB:
 *    Actualiza el valor de API_BASE_URL con la URL que imprime Ngrok.
 * ============================================================
 */

// ============================================================
// ⚙️  CONFIGURACIÓN GLOBAL — ACTUALIZAR AQUÍ TRAS CADA REINICIO
// ============================================================

// La URL ya no se edita a mano aquí: se lee la que el usuario pegó
// en index.html (portal), guardada con sessionStorage.setItem('apiUrl', ...).
// Así toda la app usa una sola fuente de verdad para la URL de ngrok.
const API_BASE_URL = sessionStorage.getItem('apiUrl') || "";

// Cabecera requerida por Ngrok para evitar la pantalla de advertencia del browser
const NGROK_HEADERS = {
  "ngrok-skip-browser-warning": "true",
  "Content-Type": "application/json"
};


// ============================================================
// 🛠️  UTILIDADES COMPARTIDAS
// ============================================================

/**
 * Envuelve fetch() con manejo de errores centralizado y cabeceras Ngrok.
 * @param {string} endpoint - Ruta relativa, p.ej. "/api/salud"
 * @returns {Promise<Object>} - JSON parseado de la respuesta
 */
async function apiFetch(endpoint) {
  const url = `${API_BASE_URL}${endpoint}`;
  console.log(`[InvestAI API] → GET ${url}`);

  const response = await fetch(url, { headers: NGROK_HEADERS });

  if (!response.ok) {
    const errorBody = await response.text();
    throw new Error(`HTTP ${response.status} en ${endpoint}: ${errorBody}`);
  }
  return response.json();
}

/**
 * Muestra u oculta un spinner de carga sobre un contenedor dado.
 * Inserta un div con id "spinner-{containerId}" si no existe.
 * @param {string} containerId - id del elemento HTML donde mostrar el spinner
 * @param {boolean} show
 */
function toggleSpinner(containerId, show) {
  const container = document.getElementById(containerId);
  if (!container) return;

  let spinner = document.getElementById(`spinner-${containerId}`);
  if (!spinner) {
    spinner = document.createElement("div");
    spinner.id = `spinner-${containerId}`;
    spinner.style.cssText =
      "position:absolute;inset:0;display:flex;align-items:center;" +
      "justify-content:center;background:rgba(13,17,23,.7);z-index:99;" +
      "border-radius:8px;font-family:monospace;color:#58a6ff;font-size:13px";
    spinner.textContent = "⟳  Cargando datos del servidor…";
    container.style.position = "relative";
    container.appendChild(spinner);
  }
  spinner.style.display = show ? "flex" : "none";
}

/**
 * Muestra un mensaje de error en pantalla en lugar de datos.
 * @param {string} containerId
 * @param {string} message
 */
function mostrarError(containerId, message) {
  toggleSpinner(containerId, false);
  const container = document.getElementById(containerId);
  if (!container) return;
  container.innerHTML =
    `<div style="color:#f85149;padding:16px;font-family:monospace;font-size:12px;">
      ⚠️ Error al conectar con la API:<br>${message}
    </div>`;
}


// ============================================================
// ─── MÓDULO 1: SALUD DEL SERVIDOR (/api/salud) ───────────
// Usado en: cualquier página de inicio / header de estado
// ============================================================

/**
 * Verifica el estado del servidor FastAPI y actualiza los elementos:
 *  · id="server-status"  → texto "healthy" / "offline"
 *  · id="server-timestamp" → timestamp devuelto por el backend
 *  · id="server-env"     → ambiente ("Google Colab + Ngrok")
 */
async function verificarSaludServidor() {
  try {
    const data = await apiFetch("/api/salud");

    // ── Actualizar elementos del DOM ──
    const elStatus    = document.getElementById("server-status");
    const elTimestamp = document.getElementById("server-timestamp");
    const elEnv       = document.getElementById("server-env");

    if (elStatus) {
      elStatus.textContent = data.status;
      elStatus.style.color = data.status === "healthy" ? "var(--buy, #3fb950)" : "var(--sell, #f85149)";
    }
    if (elTimestamp) elTimestamp.textContent = data.timestamp;
    if (elEnv)       elEnv.textContent       = data.ambiente;

    console.log("[InvestAI API] ✅ Servidor OK:", data);
    return data;

  } catch (err) {
    console.error("[InvestAI API] ❌ Servidor no disponible:", err.message);
    const elStatus = document.getElementById("server-status");
    if (elStatus) {
      elStatus.textContent = "offline";
      elStatus.style.color = "var(--sell, #f85149)";
    }
  }
}


// ============================================================
// ─── MÓDULO 2: MERCADO — datos históricos + indicadores ───
// Endpoint consumido: datos_mercado_ejemplo.json (estático)
// o bien el endpoint que devuelva el mismo contrato.
// Usado en: modulo6.2-mercado.html
// ============================================================

/**
 * Carga datos de mercado para un ticker y renderiza precio + indicadores.
 * La función reemplaza completamente la lógica de simulación con Math.random().
 *
 * Contrato JSON esperado (datos_mercado_ejemplo.json):
 * {
 *   mercado: {
 *     FSM: {
 *       empresa, bolsa,
 *       dates:  [...],
 *       open:   [...], high: [...], low: [...], close: [...], volume: [...],
 *       indicadores: { sma_20, sma_50, ema_12, ema_26,
 *                      rsi_14, macd, macd_signal, macd_hist,
 *                      bb_upper, bb_middle, bb_lower }
 *     }
 *   }
 * }
 *
 * @param {string} ticker - Ej: "FSM", "BVN", "BHP"
 * @param {Object} allData - Objeto completo ya cargado (para evitar re-fetch)
 */
function renderMercadoTicker(ticker, allData) {
  const tickerData = allData.mercado[ticker];
  if (!tickerData) {
    console.warn(`[InvestAI Mercado] Ticker ${ticker} no encontrado en datos.`);
    return;
  }

  const { dates, close, open, high, low, volume, indicadores, empresa, bolsa } = tickerData;

  // ── KPIs de cabecera ──
  const ultimoPrecio = close[close.length - 1];
  const precioAnterior = close[close.length - 2];
  const cambio = ((ultimoPrecio - precioAnterior) / precioAnterior * 100);

  const elEmpresa = document.getElementById("mkt-empresa");
  const elBolsa   = document.getElementById("mkt-bolsa");
  const elPrecio  = document.getElementById("mkt-precio");
  const elCambio  = document.getElementById("mkt-cambio");
  const elRsi     = document.getElementById("mkt-rsi");
  const elVol     = document.getElementById("mkt-volumen");

  if (elEmpresa) elEmpresa.textContent = empresa;
  if (elBolsa)   elBolsa.textContent   = bolsa;
  if (elPrecio)  elPrecio.textContent  = `$${ultimoPrecio.toFixed(2)}`;
  if (elCambio) {
    elCambio.textContent = `${cambio >= 0 ? "+" : ""}${cambio.toFixed(2)}%`;
    elCambio.style.color = cambio >= 0 ? "var(--buy, #3fb950)" : "var(--sell, #f85149)";
  }
  if (elRsi) {
    const ultimoRsi = indicadores.rsi_14[indicadores.rsi_14.length - 1];
    elRsi.textContent = ultimoRsi ? ultimoRsi.toFixed(1) : "—";
  }
  if (elVol) {
    const ultimoVol = volume[volume.length - 1];
    elVol.textContent = ultimoVol
      ? (ultimoVol >= 1_000_000
          ? `${(ultimoVol / 1_000_000).toFixed(2)}M`
          : `${(ultimoVol / 1_000).toFixed(0)}K`)
      : "—";
  }

  // ── Gráfico de Precio + Bandas de Bollinger (Chart.js) ──
  const ctxPrecio = document.getElementById("priceChart");
  if (ctxPrecio) {
    // Destruir instancia previa si existe
    if (window._mktPriceChart) window._mktPriceChart.destroy();

    const gradCtx = ctxPrecio.getContext("2d");
    const grad = gradCtx.createLinearGradient(0, 0, 0, 340);
    grad.addColorStop(0, "rgba(88,166,255,0.20)");
    grad.addColorStop(1, "rgba(88,166,255,0.00)");

    window._mktPriceChart = new Chart(ctxPrecio, {
      type: "line",
      data: {
        labels: dates,
        datasets: [
          {
            label: "Precio cierre",
            data: close,
            borderColor: "rgba(88,166,255,0.9)",
            borderWidth: 1.8,
            pointRadius: 0,
            fill: true,
            backgroundColor: grad,
            tension: 0.3,
            order: 1
          },
          {
            label: "BB Superior",
            data: indicadores.bb_upper,
            borderColor: "rgba(210,153,34,0.4)",
            borderWidth: 1,
            borderDash: [4, 4],
            pointRadius: 0,
            fill: false,
            tension: 0.3,
            order: 2
          },
          {
            label: "BB Inferior",
            data: indicadores.bb_lower,
            borderColor: "rgba(210,153,34,0.4)",
            borderWidth: 1,
            borderDash: [4, 4],
            pointRadius: 0,
            fill: "-1",                          // rellena entre superior e inferior
            backgroundColor: "rgba(210,153,34,0.05)",
            tension: 0.3,
            order: 3
          },
          {
            label: "SMA 20",
            data: indicadores.sma_20,
            borderColor: "rgba(63,185,80,0.7)",
            borderWidth: 1.2,
            pointRadius: 0,
            fill: false,
            tension: 0.3,
            order: 4
          },
          {
            label: "SMA 50",
            data: indicadores.sma_50,
            borderColor: "rgba(248,81,73,0.7)",
            borderWidth: 1.2,
            pointRadius: 0,
            fill: false,
            tension: 0.3,
            order: 5
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { intersect: false, mode: "index" },
        plugins: {
          legend: {
            labels: { color: "#7d8590", font: { size: 11 } }
          },
          tooltip: {
            backgroundColor: "#1e2530",
            borderColor: "rgba(88,166,255,0.3)",
            borderWidth: 1,
            callbacks: {
              label: ctx => ` ${ctx.dataset.label}: $${ctx.parsed.y.toFixed(4)}`
            }
          }
        },
        scales: {
          x: {
            ticks: { color: "#7d8590", font: { size: 10 }, maxTicksLimit: 10 },
            grid: { color: "rgba(255,255,255,0.04)" }
          },
          y: {
            ticks: {
              color: "#7d8590",
              font: { size: 10 },
              callback: v => `$${v}`
            },
            grid: { color: "rgba(255,255,255,0.05)" }
          }
        }
      }
    });
  }

  // ── Gráfico MACD (Chart.js — tipo bar + line) ──
  const ctxMacd = document.getElementById("macdChart");
  if (ctxMacd) {
    if (window._mktMacdChart) window._mktMacdChart.destroy();
    window._mktMacdChart = new Chart(ctxMacd, {
      data: {
        labels: dates,
        datasets: [
          {
            type: "bar",
            label: "MACD Histograma",
            data: indicadores.macd_hist,
            backgroundColor: indicadores.macd_hist.map(v =>
              v >= 0 ? "rgba(63,185,80,0.55)" : "rgba(248,81,73,0.55)"
            )
          },
          {
            type: "line",
            label: "MACD",
            data: indicadores.macd,
            borderColor: "#58a6ff",
            borderWidth: 1.5,
            pointRadius: 0,
            fill: false,
            tension: 0.3
          },
          {
            type: "line",
            label: "Señal",
            data: indicadores.macd_signal,
            borderColor: "#f78166",
            borderWidth: 1.2,
            pointRadius: 0,
            fill: false,
            tension: 0.3
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { labels: { color: "#7d8590", font: { size: 11 } } }
        },
        scales: {
          x: {
            ticks: { color: "#7d8590", font: { size: 10 }, maxTicksLimit: 8 },
            grid: { color: "rgba(255,255,255,0.04)" }
          },
          y: {
            ticks: { color: "#7d8590", font: { size: 10 } },
            grid: { color: "rgba(255,255,255,0.05)" }
          }
        }
      }
    });
  }

  // ── Gráfico RSI ──
  const ctxRsi = document.getElementById("rsiChart");
  if (ctxRsi) {
    if (window._mktRsiChart) window._mktRsiChart.destroy();
    window._mktRsiChart = new Chart(ctxRsi, {
      type: "line",
      data: {
        labels: dates,
        datasets: [{
          label: "RSI 14",
          data: indicadores.rsi_14,
          borderColor: "#d2a520",
          borderWidth: 1.5,
          pointRadius: 0,
          fill: false,
          tension: 0.3
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { labels: { color: "#7d8590" } },
          annotation: {                         // requiere chartjs-plugin-annotation
            annotations: {
              sobrecompra: {
                type: "line", yMin: 70, yMax: 70,
                borderColor: "rgba(248,81,73,0.5)", borderWidth: 1,
                label: { content: "Sobrecompra 70", enabled: true, color: "#f85149" }
              },
              sobreventa: {
                type: "line", yMin: 30, yMax: 30,
                borderColor: "rgba(63,185,80,0.5)", borderWidth: 1,
                label: { content: "Sobreventa 30", enabled: true, color: "#3fb950" }
              }
            }
          }
        },
        scales: {
          x: { ticks: { color: "#7d8590", font: { size: 10 }, maxTicksLimit: 8 } },
          y: { min: 0, max: 100, ticks: { color: "#7d8590" } }
        }
      }
    });
  }
}

/**
 * Punto de entrada para modulo6.2-mercado.html
 * Sustituye la lógica con Math.random() por datos reales del JSON local/API.
 *
 * OPCIÓN A (archivo estático): Lee datos_mercado_ejemplo.json desde el mismo directorio.
 * OPCIÓN B (API dinámica):     Llama a un endpoint que devuelva el mismo contrato.
 *
 * @param {string} ticker - Ticker activo seleccionado en el <select>
 */
async function cargarMercado(ticker = "FSM") {
  toggleSpinner("chart-container", true);
  try {
    // OPCIÓN A: Archivo JSON local (sin backend activo)
    // const resp = await fetch("datos_mercado_ejemplo.json", { headers: NGROK_HEADERS });
    // const allData = await resp.json();

    // OPCIÓN B: Endpoint dinámico del backend (activo desde semana 13)
    // Nota: esta función (cargarMercado) queda como referencia; el dashboard
    // de mercado real de este proyecto vive en modulo_mercado.html, que ya
    // consume /api/mercado/{ticker} directamente.
    const singleData = await apiFetch(`/api/mercado/${ticker}`);
    const allData = { mercado: { [ticker]: singleData } };

    toggleSpinner("chart-container", false);
    renderMercadoTicker(ticker, allData);
  } catch (err) {
    mostrarError("chart-container", err.message);
  }
}


// ============================================================
// ─── MÓDULO 3: CLASIFICADOR SVC (/api/svc/{ticker}) ──────
// Usado en: modulo6.3-svc.html
// ============================================================

/**
 * Carga datos del clasificador SVC desde la API y renderiza
 * la interfaz completa: semáforo, gráfico de precios + señales,
 * métricas y matriz de confusión.
 *
 * Contrato JSON esperado (datos_svc.json / endpoint /api/svc/{ticker}):
 * {
 *   tickers: {
 *     FSM: {
 *       nombre, ticker, senal, conf,
 *       fechas:  [...],
 *       precios: [...],
 *       senales: [...],   ← 0=HOLD, 1=BUY, 2=SELL
 *       metricas: { accuracy, precision, recall, f1 },
 *       matriz:   [[...],[...],[...]]
 *     }
 *   }
 * }
 *
 * @param {string} ticker
 */
async function cargarSVC(ticker = "FSM") {
  toggleSpinner("chart-container", true);
  try {
    // ── Intentar API dinámica; si falla, usa archivo local ──
    let tickerData;
    try {
      const data = await apiFetch(`/api/svc/${ticker}`);
      tickerData = data;
    } catch (apiErr) {
      console.warn("[SVC] API no disponible, usando JSON local:", apiErr.message);
      const resp = await fetch("datos_svc.json");
      const local = await resp.json();
      tickerData = local.tickers[ticker];
    }

    toggleSpinner("chart-container", false);
    _renderSVC(ticker, tickerData);

  } catch (err) {
    mostrarError("chart-container", err.message);
  }
}

function _renderSVC(ticker, d) {
  // ── Normalizar: el endpoint /api/svc/{ticker} puede devolver los
  //    campos en raíz o bien estar envueltos. Ajustar según el backend.
  const nombre  = d.nombre  || ticker;
  const senal   = d.senal   || "HOLD";
  const conf    = d.conf    || 0;
  const fechas  = d.fechas  || [];
  const precios = d.precios || [];
  const senales = d.senales || [];
  const metricas = d.metricas || {};
  const matriz   = d.matriz  || [[0,0,0],[0,0,0],[0,0,0]];

  // ── Título ──
  const elTitulo = document.getElementById("chart-title");
  if (elTitulo)
    elTitulo.textContent =
      `${ticker} — Precio de cierre + señales SVC (últimos ${fechas.length} días)`;

  // ── Semáforo ──
  const badge = document.getElementById("signal-badge");
  if (badge) {
    badge.className = `signal-badge signal-${senal}`;
    const elText = document.getElementById("signal-text");
    const elConf = document.getElementById("signal-conf");
    if (elText) elText.textContent = senal;
    if (elConf) elConf.textContent = `Conf: ${(conf * 100).toFixed(1)}%`;
  }

  // ── Distribución BUY/HOLD/SELL ──
  const total = senales.length || 1;
  const buy  = senales.filter(s => s === 1).length;
  const hold = senales.filter(s => s === 0).length;
  const sell = senales.filter(s => s === 2).length;

  const elBuy  = document.getElementById("dist-buy");
  const elHold = document.getElementById("dist-hold");
  const elSell = document.getElementById("dist-sell");
  if (elBuy)  elBuy.style.width  = `${(buy  / total * 100).toFixed(1)}%`;
  if (elHold) elHold.style.width = `${(hold / total * 100).toFixed(1)}%`;
  if (elSell) elSell.style.width = `${(sell / total * 100).toFixed(1)}%`;

  // ── Gráfico de precios con triángulos (usa el plugin existente) ──
  const ctxEl = document.getElementById("priceChart");
  if (ctxEl) {
    if (window.priceChart) window.priceChart.destroy();

    const ctx = ctxEl.getContext("2d");
    const grad = ctx.createLinearGradient(0, 0, 0, 340);
    grad.addColorStop(0, "rgba(88,166,255,0.20)");
    grad.addColorStop(1, "rgba(88,166,255,0.00)");

    window.priceChart = new Chart(ctx, {
      type: "line",
      data: {
        labels: fechas,
        datasets: [{
          label: "Precio cierre",
          data: precios,
          borderColor: "rgba(88,166,255,0.9)",
          borderWidth: 1.8,
          pointRadius: 0,
          pointHoverRadius: 4,
          fill: true,
          backgroundColor: grad,
          tension: 0.3
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { intersect: false, mode: "index" },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: "#1e2530",
            borderColor: "rgba(88,166,255,0.3)",
            borderWidth: 1,
            titleColor: "#7d8590",
            bodyColor: "#e6edf3",
            callbacks: {
              label(ctx) {
                const s = senales[ctx.dataIndex];
                const lbl = s === 1 ? "▲ BUY" : s === 2 ? "▼ SELL" : "● HOLD";
                return ` $${ctx.parsed.y.toFixed(2)}   ${lbl}`;
              }
            }
          },
          triangles: {}   // plugin de triángulos definido en el módulo HTML
        },
        scales: {
          x: {
            ticks: { color: "#7d8590", font: { size: 10 }, maxTicksLimit: 12 },
            grid: { color: "rgba(255,255,255,0.04)" }
          },
          y: {
            ticks: {
              color: "#7d8590",
              font: { size: 10, family: "JetBrains Mono, monospace" },
              callback: v => `$${v}`
            },
            grid: { color: "rgba(255,255,255,0.05)" }
          }
        }
      }
    });
    window.priceChart._senales = senales; // para el plugin trianglePlugin
  }

  // ── Métricas ──
  const fmtPct = v => v != null ? `${(v * 100).toFixed(1)}%` : "—";
  const elAcc  = document.getElementById("m-accuracy");
  const elF1   = document.getElementById("m-f1");
  const elPrec = document.getElementById("m-prec");
  const elRec  = document.getElementById("m-recall");
  if (elAcc)  elAcc.textContent  = fmtPct(metricas.accuracy);
  if (elF1)   elF1.textContent   = fmtPct(metricas.f1);
  if (elPrec) elPrec.textContent = fmtPct(metricas.precision);
  if (elRec)  elRec.textContent  = fmtPct(metricas.recall);

  // ── Matriz de confusión ──
  const tabla = document.getElementById("cm-table");
  if (tabla) {
    const clases = ["BUY", "HOLD", "SELL"];
    const maxVal = Math.max(...matriz.flat()) || 1;
    const colMap = { BUY: "var(--buy,#3fb950)", HOLD: "var(--hold,#d2a520)", SELL: "var(--sell,#f85149)" };

    let html = "<tr><th></th>";
    clases.forEach(c => html += `<th style="color:${colMap[c]}">Pred ${c}</th>`);
    html += "</tr>";

    matriz.forEach((fila, ri) => {
      html += `<tr><th style="color:${colMap[clases[ri]]};text-align:right;padding-right:8px">Real ${clases[ri]}</th>`;
      fila.forEach((val, ci) => {
        const intensidad = val / maxVal;
        const esAcierto  = ri === ci;
        const bg = esAcierto
          ? `rgba(63,185,80,${0.10 + intensidad * 0.60})`
          : `rgba(248,81,73,${0.04 + intensidad * 0.40})`;
        const col = intensidad > 0.5 ? "#e6edf3" : "#7d8590";
        html += `<td class="cm-cell" style="background:${bg};color:${col}"
                    data-label="${clases[ri]}→${clases[ci]}: ${val}">${val}</td>`;
      });
      html += "</tr>";
    });

    tabla.innerHTML = html;
  }
}


// ============================================================
// ─── MÓDULO 4: REGRESOR LSTM — /api/rnns/{ticker} ─────────
//              + /api/lstm/{ticker}
// Usado en: modulo6.4-lstm.html  y  modulo6.6-core.html
// ============================================================

/**
 * Carga resultados de los clasificadores RNN/LSTM desde /api/rnns/{ticker}.
 * Renderiza la tabla de modelos con señales de semáforo y barras de probabilidad.
 *
 * Contrato JSON esperado:
 * {
 *   ticker, ultima_actualizacion,
 *   modelos: {
 *     lstm:     { metricas: {accuracy,precision,recall,f1}, probabilidad_mañana, senal },
 *     bilstm:   { ... },
 *     gru:      { ... },
 *     simplernn:{ ... }
 *   }
 * }
 *
 * @param {string} ticker
 */
async function cargarRNNs(ticker = "FSM") {
  const CONTENEDOR = "rnns-container";
  toggleSpinner(CONTENEDOR, true);
  try {
    const data = await apiFetch(`/api/rnns/${ticker}`);
    toggleSpinner(CONTENEDOR, false);
    _renderRNNsTabla(data);
  } catch (err) {
    mostrarError(CONTENEDOR, err.message);
  }
}

function _renderRNNsTabla(data) {
  // ── Timestamp ──
  const elTs = document.getElementById("rnns-timestamp");
  if (elTs) elTs.textContent = data.ultima_actualizacion;

  // ── Tabla / tarjetas por modelo ──
  const MODELOS = [
    { key: "lstm",      label: "LSTM",       color: "#58a6ff" },
    { key: "bilstm",    label: "BiLSTM",     color: "#d2a520" },
    { key: "gru",       label: "GRU",        color: "#3fb950" },
    { key: "simplernn", label: "SimpleRNN",  color: "#f78166" }
  ];

  MODELOS.forEach(({ key, label, color }) => {
    const m = data.modelos[key];
    if (!m) return;

    const senal = m.senal;
    const prob  = m.probabilidad_mañana;
    const met   = m.metricas;

    // Elementos con id estándar: "{key}-senal", "{key}-prob", "{key}-acc", etc.
    const elSenal = document.getElementById(`${key}-senal`);
    const elProb  = document.getElementById(`${key}-prob`);
    const elBar   = document.getElementById(`${key}-prob-bar`);
    const elAcc   = document.getElementById(`${key}-acc`);
    const elF1    = document.getElementById(`${key}-f1`);
    const elPrec  = document.getElementById(`${key}-prec`);
    const elRec   = document.getElementById(`${key}-recall`);

    if (elSenal) {
      elSenal.textContent = senal;
      elSenal.style.color =
        senal === "BUY"  ? "var(--buy,#3fb950)" :
        senal === "SELL" ? "var(--sell,#f85149)" : "var(--hold,#d2a520)";
    }
    if (elProb) elProb.textContent  = `${(prob * 100).toFixed(1)}%`;
    if (elBar)  elBar.style.width   = `${(prob * 100).toFixed(1)}%`;
    if (elAcc)  elAcc.textContent   = `${(met.accuracy  * 100).toFixed(1)}%`;
    if (elF1)   elF1.textContent    = `${(met.f1        * 100).toFixed(1)}%`;
    if (elPrec) elPrec.textContent  = `${(met.precision * 100).toFixed(1)}%`;
    if (elRec)  elRec.textContent   = `${(met.recall    * 100).toFixed(1)}%`;
  });

  // ── Gráfico de barras comparativo de probabilidades (Chart.js) ──
  const ctxEl = document.getElementById("rnnsChart");
  if (ctxEl) {
    if (window._rnnsChart) window._rnnsChart.destroy();
    const probs = MODELOS.map(m => ((data.modelos[m.key]?.probabilidad_mañana || 0) * 100).toFixed(1));
    const colors = MODELOS.map(m => data.modelos[m.key]?.senal === "BUY"
      ? "rgba(63,185,80,0.7)" : data.modelos[m.key]?.senal === "SELL"
      ? "rgba(248,81,73,0.7)" : "rgba(210,153,34,0.7)");

    window._rnnsChart = new Chart(ctxEl, {
      type: "bar",
      data: {
        labels: MODELOS.map(m => m.label),
        datasets: [{
          label: "Prob. alcista mañana (%)",
          data: probs,
          backgroundColor: colors,
          borderRadius: 6
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: { label: ctx => ` ${ctx.parsed.y}%` }
          }
        },
        scales: {
          x: { ticks: { color: "#7d8590" }, grid: { display: false } },
          y: {
            min: 0, max: 100,
            ticks: { color: "#7d8590", callback: v => `${v}%` },
            grid: { color: "rgba(255,255,255,0.05)" }
          }
        }
      }
    });
  }
}

/**
 * Carga el regresor LSTM (histórico de validación + proyección futura)
 * desde /api/lstm/{ticker} y renderiza el gráfico combinado.
 *
 * Contrato JSON esperado:
 * {
 *   ticker, metricas_error: { rmse_usd, rmse_porcentaje, mae_usd, r2_score },
 *   historico_validacion: [ {fecha, real, predicho}, ... ],
 *   proyeccion_futura:    [ {fecha, prediccion_usd, banda_min, banda_max}, ... ]
 * }
 *
 * @param {string} ticker
 * @param {number} horizonte - Días a proyectar (parámetro ?horizonte=N)
 */
async function cargarLSTMRegresor(ticker = "FSM", horizonte = 30) {
  const CONTENEDOR = "lstm-container";
  toggleSpinner(CONTENEDOR, true);
  try {
    const data = await apiFetch(`/api/lstm/${ticker}?horizonte=${horizonte}`);
    toggleSpinner(CONTENEDOR, false);
    _renderLSTMRegresor(data);
  } catch (err) {
    mostrarError(CONTENEDOR, err.message);
  }
}

function _renderLSTMRegresor(data) {
  const { metricas_error, historico_validacion, proyeccion_futura } = data;

  // ── KPIs de error ──
  const elRmse = document.getElementById("lstm-rmse");
  const elMae  = document.getElementById("lstm-mae");
  const elR2   = document.getElementById("lstm-r2");
  const elRmseP = document.getElementById("lstm-rmse-pct");

  if (elRmse)  elRmse.textContent  = `$${metricas_error.rmse_usd.toFixed(4)}`;
  if (elMae)   elMae.textContent   = `$${metricas_error.mae_usd.toFixed(4)}`;
  if (elR2)    elR2.textContent    = metricas_error.r2_score.toFixed(3);
  if (elRmseP) elRmseP.textContent = `${metricas_error.rmse_porcentaje.toFixed(1)}%`;

  // ── Preparar datos del gráfico ──
  const fechasHist   = historico_validacion.map(d => d.fecha);
  const realesHist   = historico_validacion.map(d => d.real);
  const predHist     = historico_validacion.map(d => d.predicho);

  const fechasFut    = proyeccion_futura.map(d => d.fecha);
  const predFut      = proyeccion_futura.map(d => d.prediccion_usd);
  const bandaMinFut  = proyeccion_futura.map(d => d.banda_min);
  const bandaMaxFut  = proyeccion_futura.map(d => d.banda_max);

  // Combinar etiquetas temporales (historial + futuro)
  const allFechas = [...fechasHist, ...fechasFut];
  const nullPad   = new Array(fechasHist.length).fill(null);

  // ── Gráfico LSTM (Chart.js) ──
  const ctxEl = document.getElementById("lstmChart");
  if (!ctxEl) return;

  if (window._lstmChart) window._lstmChart.destroy();

  window._lstmChart = new Chart(ctxEl, {
    type: "line",
    data: {
      labels: allFechas,
      datasets: [
        {
          label: "Precio Real",
          data: [...realesHist, ...nullPad],
          borderColor: "rgba(88,166,255,0.9)",
          borderWidth: 1.8,
          pointRadius: 0,
          fill: false,
          tension: 0.3
        },
        {
          label: "LSTM — Validación",
          data: [...predHist, ...nullPad],
          borderColor: "rgba(63,185,80,0.8)",
          borderWidth: 1.5,
          borderDash: [6, 3],
          pointRadius: 0,
          fill: false,
          tension: 0.3
        },
        {
          label: "LSTM — Proyección",
          data: [...nullPad, ...predFut],
          borderColor: "rgba(210,153,34,0.9)",
          borderWidth: 2,
          pointRadius: 2,
          fill: false,
          tension: 0.3
        },
        {
          label: "Banda Sup. (95%)",
          data: [...nullPad, ...bandaMaxFut],
          borderColor: "rgba(210,153,34,0.25)",
          borderWidth: 1,
          pointRadius: 0,
          fill: false,
          tension: 0.3
        },
        {
          label: "Banda Inf. (95%)",
          data: [...nullPad, ...bandaMinFut],
          borderColor: "rgba(210,153,34,0.25)",
          borderWidth: 1,
          pointRadius: 0,
          fill: "-1",                       // rellena entre banda sup. e inf.
          backgroundColor: "rgba(210,153,34,0.07)",
          tension: 0.3
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { intersect: false, mode: "index" },
      plugins: {
        legend: {
          labels: { color: "#7d8590", font: { size: 11 } }
        },
        tooltip: {
          backgroundColor: "#1e2530",
          borderColor: "rgba(88,166,255,0.3)",
          borderWidth: 1,
          callbacks: {
            label: ctx =>
              ctx.raw != null ? ` ${ctx.dataset.label}: $${ctx.raw.toFixed(4)}` : ""
          }
        }
      },
      scales: {
        x: {
          ticks: { color: "#7d8590", font: { size: 10 }, maxTicksLimit: 12 },
          grid: { color: "rgba(255,255,255,0.04)" }
        },
        y: {
          ticks: {
            color: "#7d8590",
            font: { size: 10, family: "JetBrains Mono, monospace" },
            callback: v => `$${v}`
          },
          grid: { color: "rgba(255,255,255,0.05)" }
        }
      }
    }
  });

  // ── Línea divisoria entre histórico y proyección ──
  // (Plugin inline opcional — añade anotación visual)
  if (window._lstmChart && fechasHist.length > 0) {
    const dividerPlugin = {
      id: "lstmDivider",
      afterDraw(chart) {
        const idx = fechasHist.length - 1;
        const { ctx, scales } = chart;
        const x = scales.x.getPixelForValue(idx);
        ctx.save();
        ctx.setLineDash([4, 4]);
        ctx.strokeStyle = "rgba(255,255,255,0.2)";
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(x, scales.y.top);
        ctx.lineTo(x, scales.y.bottom);
        ctx.stroke();
        ctx.restore();
      }
    };
    Chart.register(dividerPlugin);
    window._lstmChart.update();
  }
}


// ============================================================
// ─── INICIALIZACIÓN AUTOMÁTICA POR PÁGINA ─────────────────
// El script detecta en qué módulo está cargado y ejecuta
// la función de carga correspondiente.
// ============================================================

document.addEventListener("DOMContentLoaded", async () => {

  // 1. Verificar salud del servidor en todas las páginas
  
  // 2. Detectar página activa por nombre del archivo
  const pagina = window.location.pathname.split("/").pop();
  
  if (pagina.includes("modulo6.2-mercado")) return;
  
  await verificarSaludServidor();

  // Helper: obtener ticker del <select> o usar el primero disponible
  function tickerActivo() {
    const sel = document.getElementById("ticker-select");
    return sel ? sel.value : "FSM";
  }

  if (pagina.includes("mercado")) {
    // modulo6.2-mercado.html
    await cargarMercado(tickerActivo());
    const sel = document.getElementById("ticker-select");
    if (sel) sel.addEventListener("change", e => cargarMercado(e.target.value));

  } else if (pagina.includes("svc")) {
    // modulo6.3-svc.html
    // Este módulo usa su propia función cargarSVCReal (definida
    // en el HTML), que respeta el contrato real del backend
    // (modelo binario BUY/SELL, matriz 2x2). No usamos cargarSVC()
    // de aquí para evitar duplicar la carga y el listener del
    // selector, y para no depender del fallback a datos_svc.json.
    if (typeof window.cargarSVCReal === "function") {
      // La carga inicial ya la dispara el propio HTML en
      // DOMContentLoaded; aquí solo evitamos doble listener.
    }

  } else if (pagina.includes("lstm")) {
    // modulo6.4-lstm.html
    const horizonte = 30;
    await Promise.all([
      cargarRNNs(tickerActivo()),
      cargarLSTMRegresor(tickerActivo(), horizonte)
    ]);
    const sel = document.getElementById("ticker-select");
    if (sel) sel.addEventListener("change", async e => {
      await Promise.all([
        cargarRNNs(e.target.value),
        cargarLSTMRegresor(e.target.value, horizonte)
      ]);
    });

  } else if (pagina.includes("core")) {
    // modulo6.6-core-predictivo-central.html
    // Este módulo usa su propia función (definida en el HTML),
    // ya que sus IDs (radarChart, table-body) son distintos a
    // los del módulo 6.4 (rnnsChart, lstm-senal, etc.)
    if (typeof window.cargarCoreResumen === "function") {
      await window.cargarCoreResumen();
    }
  }
});


// ============================================================
// EXPORTAR funciones para uso manual desde la consola del
// navegador durante la verificación de integración (F12)
// ============================================================
window.InvestAI = {
  API_BASE_URL,
  verificarSaludServidor,
  cargarMercado,
  cargarSVC,
  cargarRNNs,
  cargarLSTMRegresor
};
