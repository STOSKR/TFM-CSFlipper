const fallbackDashboard = {
  pipeline: [
    ["Scraping", "Semanal listo, logs compactos"],
    ["Persistencia", "Historial incremental en market_history_points"],
    ["Modelo", "Direccion experimental, no compra automatica"],
    ["MARL", "RLlib smoke listo, critico central pendiente"],
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
      buff: "buff/sell_price historico escaso",
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
    ["022", "Entrenamiento RLlib MAPPO/CTDE", "En progreso"],
    ["025", "Web de recomendaciones de compra", "MVP local"],
    ["017", "Restricciones de riesgo Portfolio", "Realizada"],
  ],
};

let dashboard = fallbackDashboard;
let visibleRecommendations = [];
let selectedDealIndex = 0;
let localCommands = [];
let scrapeWasRunning = false;

const statusLabels = {
  review: "Revisar",
  observe: "Observar",
  blocked: "Bloqueado",
};

async function loadDashboard() {
  const dataFile = new URLSearchParams(window.location.search).get("data");
  if (!dataFile) {
    dashboard = await readDashboardJson(`./api/dashboard?ts=${Date.now()}`) || fallbackDashboard;
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
  visibleRecommendations = dashboard.recommendations
    .filter((item) => {
      const matchesStatus = status === "all" || item.status === status;
      const haystack = `${item.name} ${item.quality}`.toLowerCase();
      return matchesStatus && haystack.includes(search);
    })
    .sort((left, right) => compareRecommendations(left, right, sort));

  if (selectedDealIndex >= visibleRecommendations.length) {
    selectedDealIndex = 0;
  }

  document.querySelector("#recommendation-rows").innerHTML = visibleRecommendations.length
    ? visibleRecommendations
    .map(
      (item, index) => `
        <button class="deal-card ${index === selectedDealIndex ? "selected" : ""}" type="button" data-deal-index="${index}">
          <span class="deal-main">
            <span class="item-name">
              <strong>${escapeHtml(item.name)}</strong>
              <small>${escapeHtml(item.quality)}${item.stattrak ? " - StatTrak" : ""}</small>
            </span>
            <span class="route-cell">
              <strong>${escapeHtml(item.route || "Sin ruta")}</strong>
              <small>${escapeHtml(formatRouteDetail(item))}</small>
            </span>
          </span>
          <span class="deal-profit">
            <strong>${escapeHtml(item.profit)}</strong>
            <small>${escapeHtml(item.steam)} / ${escapeHtml(item.buff)}</small>
          </span>
          <span class="deal-signal">
            <span class="badge ${escapeHtml(item.status)}">${escapeHtml(statusLabels[item.status] || item.status)}</span>
            <small>${escapeHtml(item.model)}</small>
          </span>
        </button>
      `,
    )
    .join("")
    : `<div class="empty-list"><strong>Sin oportunidades</strong><span>Cambia filtros o lanza scraper.</span></div>`;

  renderDealDetail(visibleRecommendations[selectedDealIndex]);
}

function renderDealDetail(item) {
  const root = document.querySelector("#deal-detail");
  if (!item) {
    root.innerHTML = `
      <div class="empty-detail">
        <p class="eyebrow">Detalle</p>
        <strong>Sin oportunidad seleccionada</strong>
      </div>
    `;
    return;
  }

  root.innerHTML = `
    <div class="detail-header">
      <div>
        <p class="eyebrow">Deal seleccionado</p>
        <h2>${escapeHtml(item.name)}</h2>
        <span>${escapeHtml(item.quality)}${item.stattrak ? " - StatTrak" : ""}</span>
      </div>
      <span class="badge ${escapeHtml(item.status)}">${escapeHtml(statusLabels[item.status] || item.status)}</span>
    </div>
    <div class="detail-profit">
      <span>Profit actual</span>
      <strong>${escapeHtml(item.profit)}</strong>
    </div>
    <dl class="detail-grid">
      <div><dt>Steam</dt><dd>${escapeHtml(item.steam)}</dd></div>
      <div><dt>BUFF</dt><dd>${escapeHtml(item.buff)}</dd></div>
      <div><dt>Ruta</dt><dd>${escapeHtml(item.route || "Sin ruta")}</dd></div>
      <div><dt>Scraping</dt><dd>${escapeHtml(formatDate(item.scrapedAt))}</dd></div>
    </dl>
    <div class="detail-block">
      <span class="ops-label">Modelo</span>
      <strong>${escapeHtml(item.model)}</strong>
    </div>
    <div class="detail-block">
      <span class="ops-label">Agentes</span>
      <strong>${escapeHtml(item.agents)}</strong>
    </div>
    <div class="detail-actions">
      <a class="primary-link" href="${escapeAttribute(item.steamUrl)}" target="_blank" rel="noreferrer">Abrir Steam</a>
      <a class="secondary-link" href="${escapeAttribute(item.buffUrl)}" target="_blank" rel="noreferrer">Abrir BUFF</a>
    </div>
  `;
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
      ([name, state, action], index) => `
        <article class="agent-row">
          <span class="agent-index">0${index + 1}</span>
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
          <span class="limit-meter" aria-hidden="true">
            <span style="width: ${riskMeterWidth(value)}%"></span>
          </span>
        </div>
      `,
    )
    .join("");
}

function riskMeterWidth(value) {
  const match = String(value ?? "").match(/(\d+(?:[.,]\d+)?)%/);
  if (!match) {
    return 100;
  }
  const numeric = Number(match[1].replace(",", "."));
  if (Number.isNaN(numeric)) {
    return 100;
  }
  return Math.min(Math.max(numeric, 4), 100);
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

function renderModel() {
  const model = dashboard.recommendations.find((item) => item.model)?.model;
  if (model) {
    document.querySelector("#model-version").textContent = model;
  }
}

function renderScrapeStatus(payload) {
  const job = payload?.job || {};
  const running = Boolean(job.running);
  const startedAt = formatDate(job.last_started_at);
  const finishedAt = formatDate(job.last_finished_at);
  const returnCode = job.last_return_code;
  const progressPercent = clampPercent(job.progress_percent);
  const progressText = job.progress_text || (running ? "Ejecutando" : "Esperando ejecucion");

  document.querySelector("#scrape-running-state").textContent = running ? "Ejecutando" : "Parado";
  document.querySelector("#scrape-last-run").textContent = job.last_started_at
    ? `Inicio: ${startedAt}`
    : "Sin ejecuciones en esta sesion";
  document.querySelector("#scrape-return-code").textContent =
    returnCode === null || returnCode === undefined ? "Pendiente" : String(returnCode);
  document.querySelector("#scrape-finished-at").textContent = job.last_finished_at
    ? `Fin: ${finishedAt}`
    : "Esperando finalizacion";
  document.querySelector("#scrape-progress-text").textContent = progressText;
  document.querySelector("#scrape-progress-percent").textContent = `${progressPercent}%`;
  document.querySelector("#scrape-progress-bar").style.width = `${progressPercent}%`;
  renderScrapeLog(job.log_tail);
  document.querySelector("#scrape-start-button").disabled = running;
  updateCommandButtons(running);
  if (scrapeWasRunning && !running && returnCode === 0) {
    refreshDashboardView();
  }
  scrapeWasRunning = running;
}

function renderScrapeLog(lines) {
  const root = document.querySelector("#scrape-log");
  const visibleLines = Array.isArray(lines) ? lines.slice(-8) : [];
  root.innerHTML = visibleLines.length
    ? visibleLines
      .map((line) => `<li>${escapeHtml(line)}</li>`)
      .join("")
    : `<li class="muted">Sin eventos de ejecucion todavia.</li>`;
}

async function loadScrapeStatus() {
  const response = await requestJson("./api/scrape/status");
  if (!response.ok) {
    document.querySelector("#scrape-action-status").textContent =
      "No se pudo consultar el estado del scraper.";
    return;
  }
  renderScrapeStatus(response.payload);
}

async function loadCommands() {
  const response = await requestJson("./api/commands");
  if (!response.ok) {
    document.querySelector("#command-list").innerHTML =
      `<div class="empty-list"><strong>No disponible</strong><span>Arranca con python -m apps.cli.web_dashboard_server.</span></div>`;
    return;
  }
  localCommands = response.payload?.commands || [];
  renderCommands(localCommands);
  updateCommandButtons(Boolean(response.payload?.job?.running));
}

function renderCommands(commands) {
  document.querySelector("#command-list").innerHTML = commands.length
    ? commands
      .map((command) => `
        <article class="command-row">
          <div>
            <strong>${escapeHtml(command.label)}</strong>
            <span>${escapeHtml(command.description)}</span>
          </div>
          <button
            class="secondary-action"
            type="button"
            data-command-id="${escapeAttributeText(command.id)}"
          >
            Ejecutar
          </button>
        </article>
      `)
      .join("")
    : `<div class="empty-list"><strong>Sin comandos</strong><span>No hay comandos configurados.</span></div>`;
}

function updateCommandButtons(running) {
  document
    .querySelectorAll("[data-command-id]")
    .forEach((button) => {
      button.disabled = running;
    });
}

async function startScrape() {
  const button = document.querySelector("#scrape-start-button");
  const status = document.querySelector("#scrape-action-status");
  button.disabled = true;
  status.textContent = "Lanzando scraper...";
  const response = await requestJson("./api/scrape/start", { method: "POST" });
  if (response.payload) {
    renderScrapeStatus(response.payload);
  }
  if (response.ok) {
    status.textContent = "Scraper lanzado.";
    return;
  }
  status.textContent =
    response.status === 409 ? "Ya hay un scraper ejecutandose." : "No se pudo lanzar el scraper.";
}

async function runLocalCommand(commandId) {
  const status = document.querySelector("#scrape-action-status");
  const command = localCommands.find((item) => item.id === commandId);
  status.textContent = command ? `Lanzando ${command.label}...` : "Lanzando comando...";
  updateCommandButtons(true);
  const response = await requestJson("./api/commands/run", {
    method: "POST",
    body: { id: commandId },
  });
  if (response.payload?.job) {
    renderScrapeStatus(response.payload);
  }
  if (response.ok) {
    status.textContent = command ? `${command.label} lanzado.` : "Comando lanzado.";
    return;
  }
  status.textContent =
    response.status === 409 ? "Ya hay un comando ejecutandose." : "No se pudo lanzar el comando.";
  updateCommandButtons(false);
}

async function refreshDashboardView() {
  await loadDashboard();
  selectedDealIndex = 0;
  renderAll();
  document.querySelector("#scrape-action-status").textContent =
    "Datos actualizados desde la base de datos.";
}

function requestJson(path, options = {}) {
  return new Promise((resolve) => {
    const request = new XMLHttpRequest();
    request.open(options.method || "GET", path, true);
    request.setRequestHeader("Cache-Control", "no-store");
    if (options.body) {
      request.setRequestHeader("Content-Type", "application/json; charset=utf-8");
    }
    request.onload = () => {
      let payload = null;
      try {
        payload = JSON.parse(request.responseText);
      } catch {
        payload = null;
      }
      resolve({
        ok: request.status >= 200 && request.status < 300,
        status: request.status,
        payload,
      });
    };
    request.onerror = () => resolve({ ok: false, status: 0, payload: null });
    request.send(options.body ? JSON.stringify(options.body) : undefined);
  });
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

function escapeAttributeText(value) {
  return escapeHtml(String(value ?? ""));
}

function clampPercent(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) {
    return 0;
  }
  return Math.min(100, Math.max(0, Math.round(number)));
}

function renderAll() {
  renderPipeline();
  renderSummary();
  renderRecommendations();
  renderAgents();
  renderRisk();
  renderBacklog();
  renderModel();
}

document.querySelector("#status-filter").addEventListener("change", () => {
  selectedDealIndex = 0;
  renderRecommendations();
});
document.querySelector("#search-filter").addEventListener("input", () => {
  selectedDealIndex = 0;
  renderRecommendations();
});
document.querySelector("#sort-select").addEventListener("change", () => {
  selectedDealIndex = 0;
  renderRecommendations();
});
document.querySelector("#recommendation-rows").addEventListener("click", (event) => {
  const card = event.target.closest("[data-deal-index]");
  if (!card) {
    return;
  }
  selectedDealIndex = Number(card.dataset.dealIndex || 0);
  renderRecommendations();
});
document.querySelector("#scrape-start-button").addEventListener("click", startScrape);
document.querySelector("#command-list").addEventListener("click", (event) => {
  const button = event.target.closest("[data-command-id]");
  if (!button) {
    return;
  }
  runLocalCommand(button.dataset.commandId);
});

setupNavigation();
loadDashboard().then(renderAll);
loadScrapeStatus();
loadCommands();

function setupNavigation() {
  const links = Array.from(document.querySelectorAll(".nav-list a"));
  const openers = Array.from(document.querySelectorAll("[data-open-view]"));
  const views = links
    .map((link) => document.querySelector(link.getAttribute("href")))
    .filter(Boolean);
  const defaultId = "recommendations";
  const titles = {
    recommendations: "Deals",
    scraper: "Scraper",
    model: "Modelo",
    agents: "Agentes",
    portfolio: "Riesgo",
    backlog: "Roadmap",
  };

  function activate(id) {
    const selected = views.some((view) => view.id === id) ? id : defaultId;
    links.forEach((link) => {
      link.classList.toggle("active", link.getAttribute("href") === `#${selected}`);
    });
    views.forEach((view) => {
      view.hidden = view.id !== selected;
    });
    if (window.location.hash !== `#${selected}`) {
      window.history.replaceState(null, "", `#${selected}`);
    }
    window.scrollTo({ top: 0, left: 0 });
    document.querySelector("#view-title").textContent = titles[selected] || "Mesa local";
  }

  openers.forEach((button) => {
    button.addEventListener("click", () => activate(button.dataset.openView));
  });
  window.addEventListener("hashchange", () => activate(window.location.hash.slice(1)));
  activate(window.location.hash.slice(1));
}

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
