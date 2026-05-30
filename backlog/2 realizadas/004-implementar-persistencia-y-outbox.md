# Implementar persistencia y outbox

## Objetivo

Crear repositorios asincronos y patron outbox para registrar eventos de dominio de forma trazable.

## Contexto

La adquisicion, prediccion, votacion y decision deben persistir datos y eventos sin duplicar queries.

## Alcance

- Configuracion de conexion async a Postgres.
- Repositorios iniciales en `packages/persistence/`.
- Escritura y lectura de `outbox_events`.
- Dispatcher basico para eventos pendientes.
- Tests de integracion con Postgres local o Supabase remoto si esta disponible.

## Criterios de aceptacion

- Las queries viven en `packages/persistence/`.
- Los eventos criticos se pueden guardar y marcar como procesados.
- Hay manejo de errores y logging.
- No se bloquea el event loop.

## Decisiones tecnicas

- Usar `asyncpg` directamente para I/O async contra Postgres/Supabase.
- Mantener queries centralizadas en `packages/persistence/repositories.py`.
- Usar `MarketObservationIngestionRepository` como entrada transaccional para observacion + evento outbox.
- El contrato usa `asset_id` como ID canonico y `platform_id` como codigo logico; persistencia resuelve ambos a UUID internos.
- `OutboxDispatcher` recibe handlers async por tipo de evento y marca eventos como `processing`, `processed` o `failed`.

## Pasos realizados

- Movida la tarea al carril activo del backlog fisico (`backlog/1 progreso/`).
- Implementado `packages/persistence/connection.py` para cargar `DATABASE_URL`, normalizar DSN y crear pools async.
- Implementados repositorios para assets, plataformas, observaciones, outbox e ingestion transaccional.
- Implementado dispatcher basico de outbox.
- Exportadas las piezas publicas desde `packages/persistence/__init__.py`.
- Actualizado `packages/persistence/README.md`.
- Aniadidos tests unitarios de configuracion de conexion.
- Aniadidos tests de integracion contra Supabase remoto con rollback para no dejar datos de prueba persistidos.
- Ajustado `pyproject.toml` para ignorar imports sin stubs de `asyncpg` en mypy.

## Pruebas ejecutadas

- `python -m pytest`: OK (`15 passed`).
- `python -m ruff check .`: OK.
- `python -m mypy packages tests`: OK.
- Test de integracion real: escritura de observacion + evento outbox en transaccion con rollback: OK.
- Test de integracion real: lectura de eventos pendientes y marcado como procesado con rollback: OK.

## Bloqueos o riesgos

- No quedan bloqueos para esta tarea.
- La disponibilidad de la integracion remota depende de que `.env` tenga `DATABASE_URL` valida.
