# Supabase Migrations

Las migraciones SQL versionadas viven en `supabase/migrations/`.

Para aplicar la migracion inicial en una base local o remota:

```bash
psql "$DATABASE_URL" -f supabase/migrations/0001_initial_schema.sql
```

Si se usa la URL de runtime con `asyncpg`, cambia temporalmente el prefijo
`postgresql+asyncpg://` por `postgresql://` al ejecutar `psql`.

El esquema canonico usa `assets`, `platforms`, `market_observations`, `outbox_events`,
`predictions`, `risk_profiles`, `votes`, `investment_decisions` y `simulated_positions`.
La tabla `legacy_scraped_items` es solo staging para datos antiguos de `cs-tracker`.

El flujo operativo actual de scraping y datasets usa principalmente `market_items` y
`market_history_points`, añadidas en migraciones posteriores. Ese esquema simple es la fuente
practica para Steam/BUFF hasta que haga falta consolidarlo con el esquema canonico.
