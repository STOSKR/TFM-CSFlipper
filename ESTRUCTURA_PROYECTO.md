# Estructura del Proyecto

Vista rápida del monorepo `CS2 Consorcio de Inversión`.

```text
TFM-CSFlipper/
├── apps/
│   ├── agents/              # Entrada futura para agentes MARL/coordinadores
│   ├── acquisition/         # Agentes extractores: API, scraping, CSV/JSON, SteamDT y OCR
│   └── cli/                 # Comandos manuales de desarrollo y diagnóstico
├── packages/
│   ├── contracts/           # Contratos Pydantic V2 compartidos
│   ├── decision/            # Restricciones de riesgo y traducción de acciones simuladas
│   ├── domain/              # Entidades y reglas puras del negocio
│   ├── persistence/         # Supabase/Postgres, repositorios y outbox
│   ├── prediction/          # Features, datasets e inferencia temporal
│   ├── simulation/          # Trade hold, cartera, comisiones y backtesting
│   └── vision/              # OpenCV, Tesseract, OCR y parsing visual
├── docs/
│   ├── architecture.md      # Arquitectura general y flujo del sistema
│   ├── agent-protocols.md   # Agentes extractores, agentes MARL y contratos
│   ├── data-model.md        # Modelo inicial de datos Supabase/Postgres
│   ├── operational-flow.md  # Flujo operativo de adquisición, predicción y decisión
│   ├── ocr-pipeline.md      # Flujo OCR añadido al alcance del TFM
│   ├── simulation-model.md  # Simulación, trade hold y evaluación
│   ├── tfm-proposal-summary.md
│   └── decisions/           # ADRs: decisiones arquitectónicas
├── tests/
│   ├── unit/                # Tests unitarios
│   ├── integration/         # Tests con BD/agentes/servicios
│   └── e2e/                 # Flujos completos
├── material_a_integrar/     # Material local a revisar, organizado por tareas del backlog
├── backlog/
│   ├── 0 pendientes/        # Tareas por hacer
│   ├── 1 progreso/          # Tarea activa
│   └── 2 realizadas/        # Tareas aprobadas y cerradas
├── .env.example             # Variables de entorno esperadas
├── docker-compose.yml       # Postgres local para desarrollo
├── pyproject.toml           # Dependencias y configuración Python
├── prompt_maestro.md        # Instrucciones principales para chats futuros
└── README.md                # Visión general del proyecto
```

## Lectura Recomendada para un Chat Nuevo

1. `prompt_maestro.md`
2. `backlog/1 progreso/` y `backlog/0 pendientes/`
3. `ESTRUCTURA_PROYECTO.md`
4. `README.md`
5. `docs/architecture.md`
6. `docs/tfm-proposal-summary.md`

Si aparece material previo fuera del flujo actual, primero hay que inventariarlo y decidir
dónde encaja dentro de `apps/`, `packages/`, `docs/` o `tests/` antes de escribir una versión nueva.

## Regla Rápida

Si necesitas saber **qué hacer**, mira `backlog/`.

Si necesitas saber **dónde tocar código**, mira `apps/` y `packages/`.

Si necesitas saber **por qué existe algo**, mira `docs/` y `docs/decisions/`.

Si necesitas saber **si algo ya existe**, busca primero en el repositorio y en el material aportado
por el Scrum Master; integrar tiene prioridad sobre reinventar.

El material previo que todavía no esté adaptado al monorepo debe entrar primero en
`material_a_integrar/`. Los repos brutos pueden quedarse como referencia, pero las piezas
reutilizables deben agruparse por tarea del backlog antes de migrarlas al código final.

---

## Mapa Funcional

El sistema se organiza en dos familias de agentes. Los agentes extractores observan el mercado y producen datos. Los agentes MARL Scout, Trader y Portfolio aprenden politicas cooperativas para tomar decisiones simuladas.

```text
Agentes extractores
  -> Historico Steam Market / Buff163
  -> Dataset supervisado
  -> Modelo calibrado de spread rentable a 7 dias
  -> Entorno PettingZoo
  -> Scout / Trader / Portfolio
  -> Acciones y decisión simulada
  -> Simulador y evaluación
```

## Agentes

La definición detallada de agentes y contratos está en [docs/agent-protocols.md](docs/agent-protocols.md). Resumen rápido:

| Agente | Función |
| --- | --- |
| Steam/Buff extractor | Extrae precios, volumen, buy orders e historico. |
| SteamDT extractor | Descubre candidatos de arbitraje para scraping profundo. |
| OCR/CSV extractor | Incorpora datos visuales o manuales al historico. |
| Scout | Detecta y marca oportunidades. |
| Trader | Decide accion y tamaño de posicion. |
| Portfolio | Gestiona riesgo, exposicion y capital bloqueado. |

---

## Servicios de Soporte

| Servicio | Ubicación | Detalle |
| --- | --- | --- |
| Adquisición | `apps/acquisition/` | Ver [docs/architecture.md](docs/architecture.md). |
| OCR | `packages/vision/` | Ver [docs/ocr-pipeline.md](docs/ocr-pipeline.md). |
| Predicción | `packages/prediction/` | Ver [docs/architecture.md](docs/architecture.md). |
| Simulación | `packages/simulation/` | Ver [docs/simulation-model.md](docs/simulation-model.md). |

Los scrapers, importadores CSV y procesos OCR pueden describirse como agentes extractores, pero no como agentes MARL. Su objetivo es alimentar datasets, inferencia y simulacion.

---

## Flujo de Comunicación

```text
1. Extractores
   guardan snapshots/historico
   trazan fuente, timestamp y calidad de dato

2. Modelo supervisado
   genera probabilidad calibrada de spread rentable a 7 dias

3. Entorno PettingZoo
   construye observaciones locales para cada agente

4. Scout / Trader / Portfolio
   emiten acciones cooperativas

5. Simulador
   aplica trade hold, comisiones, liquidez y recompensa
```

## Contratos Compartidos

Todos los mensajes entre agentes deben definirse en `packages/contracts/`. La lista y payload mínimo están en [docs/agent-protocols.md](docs/agent-protocols.md).

## Orden de Implementación Recomendado

El orden vivo está en `backlog/0 pendientes/`. Resumen:

1. Validar formulas, datos historicos y scraping Steam-Buff.
2. Construir dataset supervisado con target de spread rentable a 7 dias.
3. Experimentar, calibrar y serializar el modelo supervisado.
4. Implementar simulador de cartera, trade hold y restricciones de riesgo.
5. Implementar entorno PettingZoo con Scout, Trader y Portfolio.
6. Integrar la probabilidad supervisada en observaciones.
7. Diseñar recompensa cooperativa y entrenar MAPPO con RLlib bajo CTDE.
8. Validar contra baseline single-agent y ablations.
9. Implementar inferencia productiva y visualizacion.
