# Persistence Package

Acceso async a Supabase/Postgres, repositorios, transacciones y outbox.

Piezas principales:

- `connection.py`: carga `DATABASE_URL`, normaliza URLs `postgresql+asyncpg://` y crea pools.
- `repositories.py`: repositorios para assets, plataformas, observaciones y outbox.
- `MarketObservationIngestionRepository`: guarda observacion y evento `MarketObservationCaptured` en una transaccion.
- `OutboxDispatcher`: procesa eventos pendientes con handlers async.

El modelo de datos esta en [../../docs/data-model.md](../../docs/data-model.md).
