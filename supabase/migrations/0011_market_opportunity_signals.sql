begin;

create table if not exists market_opportunity_signals (
    id uuid primary key default gen_random_uuid(),
    item_id uuid not null references market_items(id) on update cascade on delete restrict,
    observed_at timestamptz,
    scored_at timestamptz not null default now(),
    correlation_id text,
    model_name text not null,
    model_version text not null,
    prediction_horizon text not null default '8d',
    route_label text not null,
    buy_platform text not null,
    buy_price_type text not null,
    sell_platform text not null,
    sell_price_type text not null,
    buy_price_eur numeric(18, 6),
    exit_value_eur numeric(18, 6),
    expected_profit_eur numeric(18, 6),
    expected_return numeric(18, 8),
    probability_profitable numeric(10, 5),
    decision_threshold numeric(10, 5),
    is_signal boolean not null default false,
    status text not null,
    reason text not null,
    data_quality_status text not null,
    missing_fields text[] not null default '{}',
    feature_snapshot jsonb not null default '{}'::jsonb,
    model_output jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    constraint market_opportunity_signals_model_name_chk check (btrim(model_name) <> ''),
    constraint market_opportunity_signals_model_version_chk check (btrim(model_version) <> ''),
    constraint market_opportunity_signals_route_label_chk check (btrim(route_label) <> ''),
    constraint market_opportunity_signals_buy_platform_chk check (btrim(buy_platform) <> ''),
    constraint market_opportunity_signals_sell_platform_chk check (btrim(sell_platform) <> ''),
    constraint market_opportunity_signals_status_chk check (
        status in ('review', 'observe', 'blocked')
    ),
    constraint market_opportunity_signals_quality_chk check (btrim(data_quality_status) <> ''),
    constraint market_opportunity_signals_probability_chk check (
        probability_profitable is null
        or probability_profitable between 0 and 1
    ),
    constraint market_opportunity_signals_threshold_chk check (
        decision_threshold is null
        or decision_threshold between 0 and 1
    )
);

create index if not exists idx_market_opportunity_signals_item_scored
    on market_opportunity_signals (item_id, scored_at desc);

create index if not exists idx_market_opportunity_signals_status_scored
    on market_opportunity_signals (status, scored_at desc);

create index if not exists idx_market_opportunity_signals_correlation_id
    on market_opportunity_signals (correlation_id);

commit;
