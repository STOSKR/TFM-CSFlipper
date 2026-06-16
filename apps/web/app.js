const fallbackDashboard = {
  pipeline: [
    ["Scraping", "Semanal listo, logs compactos"],
    ["Persistencia", "Historial incremental en market_history_points"],
    ["Modelo", "Direccion experimental, no compra automatica"],
    ["MARL", "Entorno minimo iniciado, PettingZoo pendiente"],
  ],
  recommendations: [
    {
      name: "AK-47 | Asiimov",
      quality: "Minimal Wear",
      stattrak: false,
      status: "observe",
      steam: "CNY 591.10",
      buff: "CNY 384",
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
      steam: "steam/sell_price ok",
      buff: "buff/sell_price falta",
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
  const rows = dashboard.recommendations.filter((item) => {
    const matchesStatus = status === "all" || item.status === status;
    const haystack = `${item.name} ${item.quality}`.toLowerCase();
    return matchesStatus && haystack.includes(search);
  });
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
          <td>${escapeHtml(item.steam)}</td>
          <td>${escapeHtml(item.buff)}</td>
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
  renderRecommendations();
  renderAgents();
  renderRisk();
  renderBacklog();
}

document.querySelector("#status-filter").addEventListener("change", renderRecommendations);
document.querySelector("#search-filter").addEventListener("input", renderRecommendations);

loadDashboard().then(renderAll);
