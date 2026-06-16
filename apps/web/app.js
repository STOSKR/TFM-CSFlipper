const pipeline = [
  ["Scraping", "Semanal listo, logs compactos"],
  ["Persistencia", "Historial incremental en market_history_points"],
  ["Modelo", "Direccion experimental, no compra automatica"],
  ["MARL", "Entorno minimo iniciado, PettingZoo pendiente"],
];

const recommendations = [
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
    name: "MP9 | Starlight Protector",
    quality: "Minimal Wear",
    stattrak: false,
    status: "review",
    steam: "Pendiente",
    buff: "Pendiente",
    model: "Sin inferencia productiva MARL",
    agents: "Scout: pendiente, Trader: pendiente, Portfolio: riesgo configurable",
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
];

const agents = [
  ["Scout", "Activo en entorno minimo", "Marca oportunidad o ignora"],
  ["Trader", "Activo en entorno minimo", "Compra uno o mantiene"],
  ["Portfolio", "Riesgo conectado", "Aprueba o rechaza por limites"],
];

const risk = [
  ["Max posicion", "20%"],
  ["Max articulo", "30%"],
  ["Max plataforma", "70%"],
  ["Capital bloqueado", "60%"],
  ["Caja minima", "10%"],
  ["Liquidez minima", "1 unidad"],
];

const backlog = [
  ["013", "Modelo supervisado calibrado", "En progreso"],
  ["018", "Entorno PettingZoo de mercado", "En progreso"],
  ["025", "Web de recomendaciones de compra", "MVP local"],
  ["017", "Restricciones de riesgo Portfolio", "Realizada"],
];

const statusLabels = {
  review: "Revisar",
  observe: "Observar",
  blocked: "Bloqueado",
};

function renderPipeline() {
  const root = document.querySelector("#pipeline-status");
  root.innerHTML = pipeline
    .map(
      ([title, detail]) => `
        <article class="status-item">
          <strong>${title}</strong>
          <span>${detail}</span>
        </article>
      `,
    )
    .join("");
}

function renderRecommendations() {
  const status = document.querySelector("#status-filter").value;
  const search = document.querySelector("#search-filter").value.trim().toLowerCase();
  const rows = recommendations.filter((item) => {
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
              <strong>${item.name}</strong>
              <small>${item.quality}${item.stattrak ? " · StatTrak" : ""}</small>
            </span>
          </td>
          <td><span class="badge ${item.status}">${statusLabels[item.status]}</span></td>
          <td>${item.steam}</td>
          <td>${item.buff}</td>
          <td><span class="subtle">${item.model}</span></td>
          <td><span class="subtle">${item.agents}</span></td>
          <td>
            <span class="actions">
              <a class="icon-link" href="${item.steamUrl}" target="_blank" rel="noreferrer" title="Abrir Steam">S</a>
              <a class="icon-link" href="${item.buffUrl}" target="_blank" rel="noreferrer" title="Abrir BUFF">B</a>
            </span>
          </td>
        </tr>
      `,
    )
    .join("");
}

function renderAgents() {
  document.querySelector("#agent-list").innerHTML = agents
    .map(
      ([name, state, action]) => `
        <article class="agent-row">
          <strong>${name}</strong>
          <span class="subtle">${state}</span>
          <span class="badge review">${action}</span>
        </article>
      `,
    )
    .join("");
}

function renderRisk() {
  document.querySelector("#risk-grid").innerHTML = risk
    .map(
      ([label, value]) => `
        <div>
          <dt>${label}</dt>
          <dd>${value}</dd>
        </div>
      `,
    )
    .join("");
}

function renderBacklog() {
  document.querySelector("#backlog-list").innerHTML = backlog
    .map(
      ([id, task, state]) => `
        <li>
          <strong>${id}</strong>
          <span>${task}</span>
          <span class="badge ${state === "Realizada" ? "review" : "observe"}">${state}</span>
        </li>
      `,
    )
    .join("");
}

document.querySelector("#status-filter").addEventListener("change", renderRecommendations);
document.querySelector("#search-filter").addEventListener("input", renderRecommendations);

renderPipeline();
renderRecommendations();
renderAgents();
renderRisk();
renderBacklog();
