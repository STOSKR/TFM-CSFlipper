# Definir modelo de datos y migraciones Supabase/Postgres

## Objetivo

Crear el esquema SQL inicial para activos, observaciones, eventos, predicciones, votos, decisiones y simulacion.

## Contexto

El documento `docs/data-model.md` define la propuesta conceptual. Esta tarea la convierte en migraciones reales.

Se ha creado una base Supabase nueva desde cero. La tabla existente `scraped_items` de `cs-tracker` queda como referencia legacy/staging para importar datos, no como tabla principal del nuevo modelo.

## Alcance

- Decidir ubicacion de migraciones.
- Crear migracion inicial.
- Anadir indices para consultas temporales.
- Definir estrategia append-only para observaciones historicas.
- Definir clave natural o fingerprint para evitar duplicados.
- Preparar datos semilla minimos si aporta valor.
- Documentar como aplicar migraciones.

## Criterios de aceptacion

- El esquema cubre las tablas minimas.
- Las claves foraneas y campos temporales estan definidos.
- Hay indices para `asset_id`, `platform_id`, `observed_at` y `correlation_id`.
- Las observaciones nuevas se insertan como filas historicas, no sobrescriben el historico.
- Existe una estrategia clara para deduplicar observaciones por activo, plataforma, variante, fecha y fuente.
- La migracion puede aplicarse en Postgres local o Supabase remoto.

## Decisiones tecnicas

- Supabase/Postgres como fuente de verdad.
- JSONB para payloads/eventos/metadatos donde tenga sentido.
- Migraciones en `supabase/migrations/`.
- Crear una base Supabase nueva desde cero con esquema canonico del TFM.
- Mantener `scraped_items` de `cs-tracker` como referencia legacy/staging mediante `legacy_scraped_items`, no como tabla principal nueva.
- Deduplicar `market_observations` con clave natural: `asset_id`, `platform_id`, `observed_at`, `variant_key`, `source_type` y `source_reference`.

## Pasos realizados

- Movida la tarea al carril activo del backlog fisico (`backlog/1 progreso/`) tras cerrar y commitear `002`.
- Identificada la informacion necesaria para configurar Supabase nuevo antes de aplicar migraciones.
- Recibida conexion directa del nuevo proyecto Supabase: host `db.cpnbuxlfvahplmzmjdxj.supabase.co`, puerto `5432`, base `postgres`, usuario `postgres`.
- Actualizado `.env` local con `SUPABASE_PROJECT_ID`, `SUPABASE_URL` y `DATABASE_URL` remota.
- Creada migracion `supabase/migrations/0001_initial_schema.sql`.
- Creado `supabase/README.md` con instrucciones de aplicacion.
- Actualizado `docs/data-model.md` con la ubicacion real de migraciones y la nota de staging legacy.
- Creados tests unitarios para validar tablas, indices, deduplicacion append-only y seeds iniciales.
- Aplicada la migracion contra Supabase remoto.

## Pruebas ejecutadas

- `python -m pytest`: OK (`11 passed`).
- `python -m ruff check .`: OK.
- `python -m mypy packages tests`: OK.
- Aplicacion real de `supabase/migrations/0001_initial_schema.sql` contra Supabase remoto: OK.
- Verificacion remota de tablas creadas: `assets`, `platforms`, `market_observations`, `outbox_events`, `predictions`, `risk_profiles`, `votes`, `investment_decisions`, `simulated_positions`, `legacy_scraped_items`.

## Bloqueos o riesgos

- Si la conexion directa falla en otro entorno por IPv4, usar la connection string de Session Pooler de Supabase.
- Las claves Supabase no deben versionarse; viven solo en `.env`.
