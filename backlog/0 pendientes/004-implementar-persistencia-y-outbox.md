# Implementar persistencia y outbox

## Objetivo

Crear repositorios asíncronos y patrón outbox para registrar eventos de dominio de forma trazable.

## Contexto

La adquisición, predicción, votación y decisión deben persistir datos y eventos sin duplicar queries.

## Alcance

- Configuración de conexión async a Postgres.
- Repositorios iniciales en `packages/persistence/`.
- Escritura y lectura de `outbox_events`.
- Dispatcher básico para eventos pendientes.
- Tests de integración con Postgres local si está disponible.

## Criterios de aceptación

- Las queries viven en `packages/persistence/`.
- Los eventos críticos se pueden guardar y marcar como procesados.
- Hay manejo de errores y logging.
- No se bloquea el event loop.

## Decisiones técnicas

- `asyncpg` o SQLAlchemy async.
- Outbox persistente en Postgres.

## Pasos realizados

Pendiente.

## Pruebas ejecutadas

Pendiente.

## Bloqueos o riesgos

- Depende del esquema de datos.
