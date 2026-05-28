# CS2 Consorcio de Inversión

Sistema multiagente para simular decisiones de inversión en mercados de activos digitales de Counter-Strike 2.

El proyecto observa precios, liquidez y señales de mercado de plataformas como Steam, Skinport y Buff; consolida histórico en Supabase/Postgres; calcula predicciones temporales; y decide operaciones simuladas mediante consenso entre agentes con perfiles de riesgo.

## Estado del Proyecto

Antes de empezar cualquier tarea, lee el tablero Kanban físico:

```text
backlog/
├── pendientes/
├── en_progreso/
└── realizadas/
```

La tarea activa, si existe, está en `backlog/en_progreso/`.

## Estructura

Para una vista rápida del árbol, agentes y flujo funcional, abre [ESTRUCTURA_PROYECTO.md](ESTRUCTURA_PROYECTO.md). Ese archivo actúa como mapa del proyecto; los detalles viven en `docs/`.

## Principios

- Monorepo modular.
- Supabase/Postgres como fuente de verdad.
- Python asíncrono para I/O.
- Agentes SPADE como coordinadores, no como contenedores de lógica de negocio.
- Contratos compartidos con Pydantic V2.
- Decisiones siempre simuladas hasta nueva orden.
- Código no repetido: lógica común en `packages/`, no duplicada en `apps/`.

## Documentación Principal

- [Mapa rápido del proyecto](ESTRUCTURA_PROYECTO.md)
- [Arquitectura](docs/architecture.md)
- [Resumen del TFM](docs/tfm-proposal-summary.md)
- [Modelo de datos](docs/data-model.md)
- [Protocolos de agentes](docs/agent-protocols.md)
- [Pipeline OCR](docs/ocr-pipeline.md)
- [Simulación y evaluación](docs/simulation-model.md)
