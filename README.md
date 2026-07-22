# Comandos utiles

python scrape_flow.py --show-browser --persist

# CS2 Consorcio de Inversión

Sistema multiagente para simular decisiones de inversión en mercados de activos digitales de Counter-Strike 2.

El proyecto observa precios, liquidez y señales de mercado de plataformas como Steam Market y BUFF; consolida histórico en Supabase/Postgres; calcula probabilidades supervisadas calibradas sobre spreads; y entrena agentes MARL cooperativos para decidir operaciones simuladas.

## Estado del Proyecto

Estado actual resumido:

- Base tecnica sana: unit tests y lint pasan; `mypy apps packages` debe mantenerse limpio.
- Modelo supervisado versionado: existe un artefacto experimental para usar como feature MARL, no como regla de compra.
- Dataset real de trading: pipeline listo, pero la senal Steam/BUFF aun es escasa para defender metricas finales.
- MARL: hay smoke PPO/RLlib con checkpoint; MAPPO/CTDE completo queda pendiente.
- Web local: existe dashboard operativo en `apps/web` servido por `python -m apps.cli.web_dashboard_server`.

Antes de empezar cualquier tarea, lee el tablero Kanban físico:

```text
backlog/
├── 0 pendientes/
├── 1 progreso/
└── 2 realizadas/
```

La tarea activa, si existe, está en `backlog/1 progreso/`. Si un documento antiguo menciona
`backlog/en_progreso/`, interprétalo como la carpeta real `backlog/1 progreso/`.

Antes de implementar una tarea, revisa si ya existe código, scripts, notebooks, capturas,
experimentos o documentos externos que puedan integrarse. El objetivo es consolidar material
existente en la arquitectura del monorepo, no rehacerlo sin necesidad.

El material previo pendiente de revisar debe colocarse en `material_a_integrar/`. Los repos
brutos pueden quedar como referencia, pero las piezas útiles deben extraerse a carpetas alineadas
con las tareas del backlog antes de migrarse al módulo correspondiente.

## Estructura

Para una vista rápida del árbol, agentes y flujo funcional, abre [ESTRUCTURA_PROYECTO.md](ESTRUCTURA_PROYECTO.md). Ese archivo actúa como mapa del proyecto; los detalles viven en `docs/`.

## Principios

- Monorepo modular.
- Supabase/Postgres como fuente de verdad.
- Python asíncrono para I/O.
- Agentes extractores para adquisición de datos: scraping, OCR, CSV/API y SteamDT.
- Agentes MARL de decisión: Scout, Trader y Portfolio, entrenados con PettingZoo/RLlib.
- Contratos compartidos con Pydantic V2.
- Decisiones siempre simuladas hasta nueva orden.
- Código no repetido: lógica común en `packages/`, no duplicada en `apps/`.
- Reutilización primero: inventariar material existente antes de crear una implementación nueva.

## Documentación Principal

- [Mapa rápido del proyecto](ESTRUCTURA_PROYECTO.md)
- [Arquitectura](docs/architecture.md)
- [Resumen del TFM](docs/tfm-proposal-summary.md)
- [Modelo de datos](docs/data-model.md)
- [Flujo operativo](docs/operational-flow.md)
- [Protocolos de agentes](docs/agent-protocols.md)
- [Analisis del Excel operativo](docs/excel-operativo-analysis.md)
- [Pipeline OCR](docs/ocr-pipeline.md)
- [Simulación y evaluación](docs/simulation-model.md)
