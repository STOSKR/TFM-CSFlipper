# Definir modelo de datos y migraciones Supabase/Postgres

## Objetivo

Crear el esquema SQL inicial para activos, observaciones, eventos, predicciones, votos, decisiones y simulación.

## Contexto

El documento `docs/data-model.md` define la propuesta conceptual. Esta tarea la convierte en migraciones reales.

## Alcance

- Decidir ubicación de migraciones.
- Crear migración inicial.
- Añadir índices para consultas temporales.
- Definir estrategia append-only para observaciones históricas.
- Definir clave natural o fingerprint para evitar duplicados.
- Preparar datos semilla mínimos si aporta valor.
- Documentar cómo aplicar migraciones.

## Criterios de aceptación

- El esquema cubre las tablas mínimas.
- Las claves foráneas y campos temporales están definidos.
- Hay índices para `asset_id`, `platform_id`, `observed_at` y `correlation_id`.
- Las observaciones nuevas se insertan como filas históricas, no sobrescriben el histórico.
- Existe una estrategia clara para deduplicar observaciones por activo, plataforma, variante, fecha y fuente.
- La migración puede aplicarse en Postgres local.

## Decisiones técnicas

- Supabase/Postgres como fuente de verdad.
- JSONB para payloads/eventos/metadatos donde tenga sentido.

## Pasos realizados

Pendiente.

## Pruebas ejecutadas

Pendiente.

## Bloqueos o riesgos

- Confirmar si se usará Supabase CLI local o migraciones SQL propias.
