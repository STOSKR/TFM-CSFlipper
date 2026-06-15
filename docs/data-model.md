# Modelo de Datos

## Decisión

La persistencia preferente es Supabase/Postgres. El modelo se diseña para trazabilidad, auditoría y análisis temporal.

## Entidades Principales

### assets

Representa un artículo de CS2.

Campos esperados:

- `id`
- `name`
- `category`
- `rarity`
- `float_min`
- `float_max`
- `external_identifiers`
- `created_at`
- `updated_at`

### platforms

Representa mercados como Steam, Skinport o Buff.

Campos esperados:

- `id`
- `name`
- `fee_percentage`
- `withdrawal_rules`
- `metadata`

### market_observations

Registro histórico de mercado para un activo en una plataforma.

Campos esperados:

- `id`
- `asset_id`
- `platform_id`
- `observed_at`
- `price`
- `currency`
- `volume`
- `liquidity_score`
- `spread`
- `float_value`
- `source_type`: `api`, `scraping`, `ocr`, `csv`
- `source_reference`
- `raw_payload`
- `created_at`

### outbox_events

Eventos persistidos para no perder señales entre escritura en BD y procesamiento multiagente.

Campos esperados:

- `event_id`
- `event_type`
- `aggregate_id`
- `payload`
- `status`: `pending`, `processing`, `processed`, `failed`
- `created_at`
- `processed_at`
- `error_message`
- `correlation_id`

### predictions

Resultado de análisis temporal.

Campos esperados:

- `id`
- `asset_id`
- `platform_id`
- `model_name`
- `model_version`
- `prediction_horizon`
- `probability_up`
- `expected_return`
- `confidence`
- `features_snapshot`
- `created_at`
- `correlation_id`

### risk_profiles

Configuración de perfiles votantes.

Campos esperados:

- `id`
- `name`
- `risk_level`
- `min_confidence`
- `min_expected_return`
- `max_capital_exposure`
- `strategy_parameters`
- `enabled`

### votes

Voto emitido por un agente de perfil.

Campos esperados:

- `id`
- `prediction_id`
- `risk_profile_id`
- `agent_jid`
- `vote`: `buy`, `reject`, `observe`, `abstain`
- `confidence`
- `reason`
- `created_at`
- `correlation_id`

### investment_decisions

Decisión final simulada.

Campos esperados:

- `id`
- `asset_id`
- `platform_id`
- `prediction_id`
- `decision`: `COMPRA_SIMULADA`, `RECHAZO`, `MANTENER_OBSERVACION`, `ERROR_DATOS_INSUFICIENTES`
- `consensus_score`
- `allocated_budget`
- `expected_exit_at`
- `reason`
- `created_at`
- `correlation_id`

### simulated_positions

Posiciones abiertas por el simulador.

Campos esperados:

- `id`
- `asset_id`
- `platform_id`
- `entry_decision_id`
- `entry_price`
- `quantity`
- `capital_locked_until`
- `status`: `open`, `locked`, `sellable`, `closed`
- `created_at`
- `closed_at`

## Migraciones

Las migraciones SQL viven en:

```text
supabase/migrations/
```

La migracion inicial es `0001_initial_schema.sql` y crea el esquema canonico del TFM.

La tabla `legacy_scraped_items` existe solo como staging para datos antiguos de `cs-tracker`.
No sustituye a `assets`, `platforms` ni `market_observations`.

## Esquema operativo simple

El scraping Steam/BUFF de fase 1 usa tablas operativas separadas del esquema canonico:

- `market_items`: una fila por variante real de articulo. La identidad natural sigue siendo
  `name + quality + stattrak`, pero la relacion fisica usa `id`. Tambien guarda el estado
  actual de cada plataforma: precio actual y moneda original, precio normalizado a EUR/CNY
  (`steam_price_eur`, `steam_price_cny`, `buff_price_eur`, `buff_price_cny`) y buy orders
  actuales como un JSONB por plataforma (`steam_buy_orders` y `buff_buy_orders`).
- `representation_name`: nombre legible y estable para revision humana, por ejemplo
  `Bowie Knife Freehand_FT_1`.
- `market_history_points`: serie temporal tabular en formato largo por
  `item_id + platform_id + observed_at + metric_name`. Cada fila contiene una unica metrica
  (`metric_name`, `metric_value`, `currency`) conservando el valor y divisa originales. Para
  metricas de precio (`sell_price`, `buy_order_price`) se calculan ademas `price_eur` y
  `price_cny`, equivalente a las columnas `Precio CE/CY` y `Precio VE/VY` del Excel operativo.
  Cualquier detalle especifico de la fuente queda en `raw_payload`. Las listas completas de buy
  orders actuales no se guardan aqui. El historico de BUFF se captura en `CNY`, que es la moneda
  nativa del endpoint.

La conversion inicial replica la simplificacion del Excel operativo: `1 EUR = 8 CNY`. En una
fase posterior debe versionarse por fecha si se incorporan tipos FX historicos. Ese tipo inicial
queda registrado en SQL en `market_currency_rates`, y el backfill de `market_items` y
`market_history_points` lee esa tabla.

Para entrenamiento no se deben mezclar precios originales en EUR y CNY en la misma feature. La
feature canónica recomendada es `price_eur`, porque el Excel y las reglas de profit/capital del
simulador calculan `Precio CE`, `Precio VE`, `realized_profit_eur` y ROI sobre EUR. `price_cny`
se conserva para auditoría, análisis de sensibilidad y modelos alternativos si se decide entrenar
todo en yuanes.

Repetir una clave surrogate (`item_id`) como FK en tablas hijas si tiene sentido en una BD
relacional. Lo que se evita es repetir la identidad natural completa en cada tabla.

Para aplicar la migracion con `psql`:

```bash
psql "$DATABASE_URL" -f supabase/migrations/0001_initial_schema.sql
```

Si `DATABASE_URL` usa el prefijo de SQLAlchemy/asyncpg (`postgresql+asyncpg://`), cambia ese
prefijo por `postgresql://` para usarlo con `psql`.
