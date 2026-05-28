# Inicializar arquitectura monorepo y base Supabase

## Objetivo

Crear la estructura base del proyecto como monorepo modular, preparada para servicios Python asíncronos, agentes SPADE, contratos compartidos y persistencia en Supabase/Postgres.

## Contexto

El prompt maestro define el proyecto `CS2 Consorcio de Inversión` como un sistema distribuido inteligente con adquisición de datos, análisis temporal mediante LSTM y decisión por consenso entre agentes de riesgo.

## Alcance

- Crear estructura de carpetas `apps/`, `packages/`, `tests/` y `docs/`.
- Crear `pyproject.toml` con dependencias base de desarrollo.
- Añadir configuración inicial para tests, linting y tipado.
- Crear `.env.example` con variables esperadas para Supabase y agentes.
- Documentar la arquitectura inicial en `docs/architecture.md`.
- Definir una primera propuesta de tablas Supabase/Postgres en `docs/data-model.md`.

## Criterios de aceptación

- El proyecto tiene estructura monorepo clara.
- Las capas principales están separadas.
- Existe documentación mínima para que un nuevo chat entienda cómo continuar.
- No hay lógica duplicada ni contratos repetidos.
- Se puede ejecutar al menos un test mínimo de comprobación del entorno.

## Decisiones técnicas

- Repositorio monorepo modular.
- Persistencia preferente: Supabase/Postgres.
- Contratos compartidos: `packages/contracts/`.
- Dominio desacoplado de SPADE e infraestructura.

## Pasos realizados

Pendiente.

## Pruebas ejecutadas

Pendiente.

## Bloqueos o riesgos

- Confirmar si se usará Supabase local mediante CLI/Docker o solo proyecto remoto.
- Confirmar versión exacta de Python objetivo.
