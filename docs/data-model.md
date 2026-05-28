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

Las migraciones SQL deben vivir en una carpeta versionada en una fase posterior, por ejemplo:

```text
supabase/migrations/
```

o:

```text
packages/persistence/migrations/
```

La decisión final dependerá de si se usa Supabase CLI local o solo una instancia remota.

