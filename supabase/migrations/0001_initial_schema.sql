-- Initial canonical schema for CS2 investment simulation.
-- This migration is append-only for market data and keeps legacy scraped data
-- outside the core model.

create extension if not exists pgcrypto;

create table if not exists assets (
    id uuid primary key default gen_random_uuid(),
    canonical_id text not null unique,
    name text not null,
    category text,
    quality text,
    rarity text,
    stattrak boolean not null default false,
    souvenir boolean not null default false,
    float_min numeric(8, 7),
    float_max numeric(8, 7),
    external_identifiers jsonb not null default '{}'::jsonb,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint assets_float_range_chk check (
        float_min is null
        or float_max is null
        or float_min <= float_max
    )
);

create table if not exists platforms (
    id uuid primary key default gen_random_uuid(),
    code text not null unique,
    name text not null,
    fee_percentage numeric(7, 4),
    withdrawal_rules jsonb not null default '{}'::jsonb,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create table if not exists market_observations (
    id uuid primary key default gen_random_uuid(),
    asset_id uuid not null references assets(id),
    platform_id uuid not null references platforms(id),
    observed_at timestamptz not null,
    price numeric(18, 6) not null,
    currency char(3) not null,
    volume integer,
    liquidity_score numeric(6, 5),
    spread numeric(18, 6),
    float_value numeric(8, 7),
    variant_key text not null default 'default',
    source_type text not null,
    source_reference text not null default '',
    raw_payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    correlation_id text not null,
    constraint market_observations_price_chk check (price > 0),
    constraint market_observations_volume_chk check (volume is null or volume >= 0),
    constraint market_observations_currency_chk check (currency = upper(currency)),
    constraint market_observations_liquidity_chk check (
        liquidity_score is null or (liquidity_score >= 0 and liquidity_score <= 1)
    ),
    constraint market_observations_source_type_chk check (
        source_type in ('api', 'scraping', 'ocr', 'csv', 'legacy_supabase')
    ),
    constraint market_observations_dedupe_uk unique (
        asset_id,
        platform_id,
        observed_at,
        variant_key,
        source_type,
        source_reference
    )
);

create table if not exists outbox_events (
    event_id uuid primary key default gen_random_uuid(),
    event_type text not null,
    aggregate_id text not null,
    payload jsonb not null default '{}'::jsonb,
    status text not null default 'pending',
    created_at timestamptz not null default now(),
    processed_at timestamptz,
    error_message text,
    correlation_id text not null,
    constraint outbox_events_status_chk check (
        status in ('pending', 'processing', 'processed', 'failed')
    ),
    constraint outbox_events_event_type_chk check (
        event_type in (
            'MarketObservationCaptured',
            'PredictionRequested',
            'PredictionCompleted',
            'VoteRequested',
            'VoteSubmitted',
            'InvestmentDecisionMade'
        )
    )
);

create table if not exists predictions (
    id uuid primary key default gen_random_uuid(),
    asset_id uuid not null references assets(id),
    platform_id uuid not null references platforms(id),
    model_name text not null,
    model_version text not null,
    prediction_horizon text not null,
    probability_up numeric(6, 5) not null,
    expected_return numeric(12, 8) not null,
    confidence numeric(6, 5) not null,
    features_snapshot jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    correlation_id text not null,
    constraint predictions_probability_chk check (probability_up >= 0 and probability_up <= 1),
    constraint predictions_confidence_chk check (confidence >= 0 and confidence <= 1)
);

create table if not exists risk_profiles (
    id uuid primary key default gen_random_uuid(),
    code text not null unique,
    name text not null,
    risk_level text not null,
    min_confidence numeric(6, 5) not null default 0,
    min_expected_return numeric(12, 8) not null default 0,
    max_capital_exposure numeric(18, 6),
    strategy_parameters jsonb not null default '{}'::jsonb,
    enabled boolean not null default true,
    created_at timestamptz not null default now()
);

create table if not exists votes (
    id uuid primary key default gen_random_uuid(),
    prediction_id uuid not null references predictions(id),
    risk_profile_id uuid not null references risk_profiles(id),
    agent_jid text not null,
    vote text not null,
    confidence numeric(6, 5) not null,
    reason text not null,
    created_at timestamptz not null default now(),
    correlation_id text not null,
    constraint votes_vote_chk check (vote in ('buy', 'reject', 'observe', 'abstain')),
    constraint votes_confidence_chk check (confidence >= 0 and confidence <= 1),
    constraint votes_one_per_profile_uk unique (prediction_id, risk_profile_id)
);

create table if not exists investment_decisions (
    id uuid primary key default gen_random_uuid(),
    asset_id uuid not null references assets(id),
    platform_id uuid not null references platforms(id),
    prediction_id uuid references predictions(id),
    decision text not null,
    consensus_score numeric(6, 5) not null,
    allocated_budget numeric(18, 6),
    expected_exit_at timestamptz,
    reason text not null,
    created_at timestamptz not null default now(),
    correlation_id text not null,
    constraint investment_decisions_decision_chk check (
        decision in (
            'COMPRA_SIMULADA',
            'RECHAZO',
            'MANTENER_OBSERVACION',
            'ERROR_DATOS_INSUFICIENTES'
        )
    ),
    constraint investment_decisions_consensus_chk check (
        consensus_score >= 0 and consensus_score <= 1
    )
);

create table if not exists simulated_positions (
    id uuid primary key default gen_random_uuid(),
    asset_id uuid not null references assets(id),
    platform_id uuid not null references platforms(id),
    entry_decision_id uuid not null references investment_decisions(id),
    entry_price numeric(18, 6) not null,
    quantity numeric(18, 6) not null default 1,
    capital_locked_until timestamptz not null,
    status text not null default 'locked',
    created_at timestamptz not null default now(),
    closed_at timestamptz,
    metadata jsonb not null default '{}'::jsonb,
    constraint simulated_positions_entry_price_chk check (entry_price > 0),
    constraint simulated_positions_quantity_chk check (quantity > 0),
    constraint simulated_positions_status_chk check (
        status in ('open', 'locked', 'sellable', 'closed')
    )
);

create table if not exists legacy_scraped_items (
    id bigint primary key,
    item_name text not null,
    quality text,
    stattrak boolean not null default false,
    profitability numeric(10, 2),
    profit_eur numeric(10, 2),
    buff_url text,
    buff_price_eur numeric(18, 6),
    steam_url text,
    steam_price_eur numeric(18, 6),
    scraped_at timestamptz not null,
    source text not null default 'steamdt_hanging',
    created_at timestamptz,
    imported_at timestamptz not null default now()
);

create index if not exists idx_assets_canonical_id on assets(canonical_id);
create index if not exists idx_market_observations_asset_time
    on market_observations(asset_id, observed_at desc);
create index if not exists idx_market_observations_platform_time
    on market_observations(platform_id, observed_at desc);
create index if not exists idx_market_observations_correlation_id
    on market_observations(correlation_id);
create index if not exists idx_market_observations_source
    on market_observations(source_type, source_reference);
create index if not exists idx_outbox_events_status_created
    on outbox_events(status, created_at);
create index if not exists idx_outbox_events_correlation_id
    on outbox_events(correlation_id);
create index if not exists idx_predictions_asset_platform_created
    on predictions(asset_id, platform_id, created_at desc);
create index if not exists idx_predictions_correlation_id
    on predictions(correlation_id);
create index if not exists idx_votes_prediction_id on votes(prediction_id);
create index if not exists idx_votes_correlation_id on votes(correlation_id);
create index if not exists idx_investment_decisions_prediction_id
    on investment_decisions(prediction_id);
create index if not exists idx_investment_decisions_correlation_id
    on investment_decisions(correlation_id);
create index if not exists idx_simulated_positions_status
    on simulated_positions(status, capital_locked_until);

insert into platforms (code, name, fee_percentage, metadata)
values
    ('steam', 'Steam Community Market', null, '{"kind": "market"}'::jsonb),
    ('buff', 'BUFF', null, '{"kind": "market"}'::jsonb),
    ('csfloat', 'CSFloat', null, '{"kind": "market"}'::jsonb),
    ('manual', 'Manual Import', null, '{"kind": "internal"}'::jsonb)
on conflict (code) do nothing;

insert into risk_profiles (
    code,
    name,
    risk_level,
    min_confidence,
    min_expected_return,
    strategy_parameters
)
values
    ('conservative', 'Conservador', 'low', 0.75, 0.02, '{}'::jsonb),
    ('moderate', 'Moderado', 'medium', 0.60, 0.03, '{}'::jsonb),
    ('aggressive', 'Arriesgado', 'high', 0.45, 0.05, '{}'::jsonb),
    ('liquidity', 'Liquidez', 'medium', 0.55, 0.02, '{}'::jsonb),
    ('trend', 'Tendencia', 'medium', 0.55, 0.03, '{}'::jsonb),
    ('risk_manager', 'Risk Manager', 'control', 0.00, 0.00, '{}'::jsonb)
on conflict (code) do nothing;
