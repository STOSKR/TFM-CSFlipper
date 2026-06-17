const fallbackDashboard = {
  pipeline: [
    ["Scraping", "Semanal listo, logs compactos"],
    ["Persistencia", "Historial incremental en market_history_points"],
    ["Modelo", "Direccion experimental, no compra automatica"],
    ["MARL", "Entorno minimo iniciado, PettingZoo pendiente"],
  ],
  summary: {
    total: 2,
    review: 0,
    observe: 1,
    blocked: 1,
  },
  recommendations: [
    {
      name: "AK-47 | Asiimov",
      quality: "Minimal Wear",
      stattrak: false,
      status: "observe",
      route: "BUFF listing -> Steam listing",
      routeDetail: "Compra BUFF, venta Steam neta",
      buySide: "BUFF listing",
      sellSide: "Steam listing",
      steam: "CNY 591.10",
      buff: "CNY 384",
      steamEur: 73.89,
      buffEur: 48,
      profitEur: 16.28,
      profit: "16.28 EUR",
      scrapedAt: "Sin fecha",
      model: "Experimental, validar",
      agents: "Scout: revisar, Trader: esperar, Portfolio: ok",
      steamUrl: "https://steamcommunity.com/market/",
      buffUrl: "https://buff.163.com/market/csgo",
    },
    {
      name: "Dataset trading_profit_v1",
      quality: "Senal insuficiente",
      stattrak: false,
      status: "blocked",
      route: "Ruta incompleta",
      routeDetail: "Faltan precios para calcular",
      buySide: "BUFF listing",
      sellSide: "Steam listing",
      steam: "steam/sell_price ok",
      buff: "buff/sell_price falta",
      steamEur: null,
      buffEur: null,
      profitEur: null,
      profit: "Sin datos",
      scrapedAt: "Sin fecha",
      model: "No usar metricas como precision final",
      agents: "Portfolio: bloquea decision real",
      steamUrl: "https://steamcommunity.com/market/",
      buffUrl: "https://buff.163.com/market/csgo",
    },
  ],
  agents: [
    ["Scout", "Activo en entorno minimo", "Marca oportunidad o ignora"],
    ["Trader", "Activo en entorno minimo", "Compra uno o mantiene"],
    ["Portfolio", "Riesgo conectado", "Aprueba o rechaza por limites"],
  ],
  risk: [
    ["Max posicion", "20%"],
    ["Max articulo", "30%"],
    ["Max plataforma", "70%"],
    ["Capital bloqueado", "60%"],
    ["Caja minima", "10%"],
    ["Liquidez minima", "1 unidad"],
  ],
  backlog: [
    ["013", "Modelo supervisado calibrado", "En progreso"],
    ["018", "Entorno PettingZoo de mercado", "En progreso"],
    ["025", "Web de recomendaciones de compra", "MVP local"],
    ["017", "Restricciones de riesgo Portfolio", "Realizada"],
  ],
};

let dashboard = fallbackDashboard;

const statusLabels = {
  review: "Revisar",
  observe: "Observar",
  blocked: "Bloqueado",
};

async function loadDashboard() {
  const dataFile = new URLSearchParams(window.location.search).get("data");
  if (!dataFile) {
    dashboard = fallbackDashboard;
    return;
  }
  if (!/^[a-z0-9_.-]+\.json$/i.test(dataFile)) {
    dashboard = fallbackDashboard;
    return;
  }
  dashboard = await readDashboardJson(`./data/${dataFile}`) || fallbackDashboard;
}

function readDashboardJson(path) {
  return new Promise((resolve) => {
    const request = new XMLHttpRequest();
    request.open("GET", path, true);
    request.setRequestHeader("Cache-Control", "no-store");
    request.onload = () => {
      if (request.status !== 200) {
        resolve(null);
        return;
      }
      try {
        resolve(JSON.parse(request.responseText));
      } catch {
        resolve(null);
      }
    };
    request.onerror = () => resolve(null);
    request.send();
  });
}

function renderPipeline() {
  const root = document.querySelector("#pipeline-status");
  root.innerHTML = dashboard.pipeline
    .map(
      ([title, detail]) => `
        <article class="status-item">
          <strong>${escapeHtml(title)}</strong>
          <span>${escapeHtml(detail)}</span>
        </article>
      `,
    )
    .join("");
}

function renderRecommendations() {
  const status = document.querySelector("#status-filter").value;
  const search = document.querySelector("#search-filter").value.trim().toLowerCase();
  const sort = document.querySelector("#sort-select").value;
  const rows = dashboard.recommendations
    .filter((item) => {
      const matchesStatus = status === "all" || item.status === status;
      const haystack = `${item.name} ${item.quality}`.toLowerCase();
      return matchesStatus && haystack.includes(search);
    })
    .sort((left, right) => compareRecommendations(left, right, sort));
  document.querySelector("#recommendation-rows").innerHTML = rows
    .map(
      (item) => `
        <tr>
          <td>
            <span class="item-name">
              <strong>${escapeHtml(item.name)}</strong>
              <small>${escapeHtml(item.quality)}${item.stattrak ? " - StatTrak" : ""}</small>
            </span>
          </td>
          <td><span class="badge ${escapeHtml(item.status)}">${escapeHtml(statusLabels[item.status] || item.status)}</span></td>
          <td>
            <span class="route-cell">
              <strong>${escapeHtml(item.route || "Sin ruta")}</strong>
              <small>${escapeHtml(formatRouteDetail(item))}</small>
            </span>
          </td>
          <td>${escapeHtml(item.steam)}</td>
          <td>${escapeHtml(item.buff)}</td>
          <td>${escapeHtml(item.profit)}</td>
          <td><span class="subtle">${escapeHtml(formatDate(item.scrapedAt))}</span></td>
          <td><span class="subtle">${escapeHtml(item.model)}</span></td>
          <td><span class="subtle">${escapeHtml(item.agents)}</span></td>
          <td>
            <span class="actions">
              <a class="icon-link" href="${escapeAttribute(item.steamUrl)}" target="_blank" rel="noreferrer" title="Abrir Steam">S</a>
              <a class="icon-link" href="${escapeAttribute(item.buffUrl)}" target="_blank" rel="noreferrer" title="Abrir BUFF">B</a>
            </span>
          </td>
        </tr>
      `,
    )
    .join("");
}

function renderSummary() {
  const summary = dashboard.summary || summarizeRecommendations(dashboard.recommendations);
  document.querySelector("#recommendation-summary").innerHTML = [
    ["Total", summary.total],
    ["Revisar", summary.review],
    ["Observar", summary.observe],
    ["Bloqueado", summary.blocked],
  ]
    .map(
      ([label, value]) => `
        <div class="summary-pill">
          <span>${escapeHtml(label)}</span>
          <strong>${escapeHtml(value)}</strong>
        </div>
      `,
    )
    .join("");
}

function renderAgents() {
  document.querySelector("#agent-list").innerHTML = dashboard.agents
    .map(
      ([name, state, action]) => `
        <article class="agent-row">
          <strong>${escapeHtml(name)}</strong>
          <span class="subtle">${escapeHtml(state)}</span>
          <span class="badge review">${escapeHtml(action)}</span>
        </article>
      `,
    )
    .join("");
}

function renderRisk() {
  document.querySelector("#risk-grid").innerHTML = dashboard.risk
    .map(
      ([label, value]) => `
        <div>
          <dt>${escapeHtml(label)}</dt>
          <dd>${escapeHtml(value)}</dd>
        </div>
      `,
    )
    .join("");
}

function renderBacklog() {
  document.querySelector("#backlog-list").innerHTML = dashboard.backlog
    .map(
      ([id, task, state]) => `
        <li>
          <strong>${escapeHtml(id)}</strong>
          <span>${escapeHtml(task)}</span>
          <span class="badge ${state === "Realizada" ? "review" : "observe"}">${escapeHtml(state)}</span>
        </li>
      `,
    )
    .join("");
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => (
    {
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    }[char]
  ));
}

function escapeAttribute(value) {
  const text = String(value ?? "");
  if (!/^https?:\/\//.test(text)) {
    return "#";
  }
  return escapeHtml(text);
}

function renderAll() {
  renderPipeline();
  renderSummary();
  renderRecommendations();
  renderAgents();
  renderRisk();
  renderBacklog();
}

document.querySelector("#status-filter").addEventListener("change", renderRecommendations);
document.querySelector("#search-filter").addEventListener("input", renderRecommendations);
document.querySelector("#sort-select").addEventListener("change", renderRecommendations);

loadDashboard().then(renderAll);

function compareRecommendations(left, right, sort) {
  if (sort === "profit") {
    return numericValue(right.profitEur) - numericValue(left.profitEur);
  }
  if (sort === "scraped") {
    return Date.parse(right.scrapedAt || "") - Date.parse(left.scrapedAt || "");
  }
  if (sort === "steam") {
    return numericValue(right.steamEur) - numericValue(left.steamEur);
  }
  return statusRank(left.status) - statusRank(right.status);
}

function statusRank(status) {
  return { review: 0, observe: 1, blocked: 2 }[status] ?? 3;
}

function numericValue(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return Number.NEGATIVE_INFINITY;
  }
  return Number(value);
}

function summarizeRecommendations(items) {
  return {
    total: items.length,
    review: items.filter((item) => item.status === "review").length,
    observe: items.filter((item) => item.status === "observe").length,
    blocked: items.filter((item) => item.status === "blocked").length,
  };
}

function formatDate(value) {
  const timestamp = Date.parse(value || "");
  if (Number.isNaN(timestamp)) {
    return value || "Sin fecha";
  }
  return new Intl.DateTimeFormat("es-ES", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(new Date(timestamp));
}

function formatRouteDetail(item) {
  if (item.routeDetail) {
    return item.routeDetail;
  }
  if (item.buySide && item.sellSide) {
    return `${item.buySide} -> ${item.sellSide}`;
  }
  return "Ruta pendiente";
}
