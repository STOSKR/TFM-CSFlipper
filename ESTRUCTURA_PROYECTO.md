# Estructura del Proyecto

Vista rápida del monorepo `CS2 Consorcio de Inversión`.

```text
TFM-CSFlipper/
├── apps/
│   ├── agents/              # Agentes SPADE y coordinación multiagente
│   ├── acquisition/         # Ingesta por API, scraping, CSV/JSON y OCR
│   └── cli/                 # Comandos manuales de desarrollo y diagnóstico
├── packages/
│   ├── contracts/           # Contratos Pydantic V2 compartidos
│   ├── decision/            # Perfiles de riesgo, votos y consenso
│   ├── domain/              # Entidades y reglas puras del negocio
│   ├── persistence/         # Supabase/Postgres, repositorios y outbox
│   ├── prediction/          # Features, datasets e inferencia temporal
│   ├── simulation/          # Trade hold, cartera, comisiones y backtesting
│   └── vision/              # OpenCV, Tesseract, OCR y parsing visual
├── docs/
│   ├── architecture.md      # Arquitectura general y flujo del sistema
│   ├── agent-protocols.md   # Agentes, mensajes y protocolo FIPA
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

El sistema se organiza como un consorcio de agentes que no compran ni venden de verdad: observan el mercado, predicen, votan y registran decisiones simuladas.

```text
Adquisición de datos
  -> Observaciones en Supabase/Postgres
  -> Evento MarketObservationCaptured
  -> Agente Analista
  -> Predicción
  -> Agente Jefe/Broker
  -> Votación de perfiles
  -> Decisión simulada
  -> Simulador y evaluación
```

## Agentes

La definición detallada de agentes, mensajes y protocolo FIPA está en [docs/agent-protocols.md](docs/agent-protocols.md). Resumen rápido:

| Agente | Función |
| --- | --- |
| Analista | Convierte histórico de mercado en predicciones. |
| Jefe/Broker | Convoca votación, calcula consenso y registra la decisión simulada. |
| Conservador | Prioriza confianza alta, liquidez y baja exposición. |
| Moderado | Equilibra riesgo, retorno esperado y calidad de datos. |
| Arriesgado | Acepta más incertidumbre si el retorno esperado compensa. |
| Liquidez | Evalúa si el activo podrá venderse razonablemente. |
| Tendencia | Revisa momentum y consistencia temporal. |
| Arbitrajista | Busca diferencias netas entre plataformas. |
| Risk Manager | Supervisa capital, exposición y trade hold global. |

---

## Servicios que No Son Agentes

| Servicio | Ubicación | Detalle |
| --- | --- | --- |
| Adquisición | `apps/acquisition/` | Ver [docs/architecture.md](docs/architecture.md). |
| OCR | `packages/vision/` | Ver [docs/ocr-pipeline.md](docs/ocr-pipeline.md). |
| Predicción | `packages/prediction/` | Ver [docs/architecture.md](docs/architecture.md). |
| Simulación | `packages/simulation/` | Ver [docs/simulation-model.md](docs/simulation-model.md). |

Los scrapers, importadores CSV y procesos OCR se tratan como automatizaciones de adquisición, no como agentes SPADE. Solo tendría sentido crear un agente coordinador de adquisición si más adelante necesita negociar prioridades, horarios o fuentes con otros agentes.

---

## Flujo de Comunicación entre Agentes

```text
1. Acquisition Service
   guarda market_observations
   crea MarketObservationCaptured

2. Analyst Agent
   recibe/lee evento
   genera PredictionCompleted

3. Broker Agent
   recibe PredictionCompleted
   envía VoteRequested a perfiles

4. Risk Profile Agents
   responden VoteSubmitted

5. Broker Agent
   calcula consenso
   guarda InvestmentDecisionMade

6. Simulation Service
   evalúa impacto de la decisión simulada
```

## Contratos Compartidos

Todos los mensajes entre agentes deben definirse en `packages/contracts/`. La lista y payload mínimo están en [docs/agent-protocols.md](docs/agent-protocols.md).

## Orden de Implementación Recomendado

1. Crear modelos de dominio y contratos Pydantic.
2. Crear modelo de datos y migraciones Supabase/Postgres.
3. Implementar persistencia y outbox.
4. Implementar adquisición mínima con datos manuales o CSV.
5. Implementar OCR como segunda fuente de adquisición.
6. Implementar predictor baseline.
7. Implementar Agente Analista.
8. Implementar reglas de perfiles de riesgo.
9. Implementar Agente Jefe y votación.
10. Implementar simulador con trade hold.
11. Añadir evaluación y métricas.
