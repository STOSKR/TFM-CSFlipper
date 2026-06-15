begin;

-- Convert market_history_points from one row per platform timestamp into
-- one row per platform timestamp metric.
do $$
declare
    has_metric_name boolean;
    has_sell_price boolean;
    has_buy_order_price boolean;
    has_sales_count boolean;
    has_listing_count boolean;
begin
    if to_regclass('public.market_history_points') is null then
        create table market_history_points (
            item_id uuid not null references market_items(id) on update cascade on delete restrict,
            platform_id text not null,
            observed_at timestamptz not null,
            metric_name text not null,
            metric_value numeric(18, 6) not null,
            currency char(3),
            raw_payload jsonb not null default '{}'::jsonb,
            created_at timestamptz not null default now(),
            updated_at timestamptz not null default now(),
            constraint market_history_points_pkey primary key (
                item_id,
                platform_id,
                observed_at,
                metric_name
            ),
            constraint market_history_points_platform_id_chk check (btrim(platform_id) <> ''),
            constraint market_history_points_metric_name_chk check (btrim(metric_name) <> ''),
            constraint market_history_points_metric_value_chk check (metric_value >= 0),
            constraint market_history_points_currency_chk check (
                currency is null or currency = upper(currency)
            )
        );
        return;
    end if;

    select exists (
        select 1
        from information_schema.columns
        where table_schema = 'public'
          and table_name = 'market_history_points'
          and column_name = 'metric_name'
    )
    into has_metric_name;

    if has_metric_name then
        return;
    end if;

    select exists (
        select 1
        from information_schema.columns
        where table_schema = 'public'
          and table_name = 'market_history_points'
          and column_name = 'sell_price'
    )
    into has_sell_price;

    select exists (
        select 1
        from information_schema.columns
        where table_schema = 'public'
          and table_name = 'market_history_points'
          and column_name = 'buy_order_price'
    )
    into has_buy_order_price;

    select exists (
        select 1
        from information_schema.columns
        where table_schema = 'public'
          and table_name = 'market_history_points'
          and column_name = 'sales_count'
    )
    into has_sales_count;

    select exists (
        select 1
        from information_schema.columns
        where table_schema = 'public'
          and table_name = 'market_history_points'
          and column_name = 'listing_count'
    )
    into has_listing_count;

    drop table if exists market_history_points_metrics;

    create table market_history_points_metrics (
        item_id uuid not null references market_items(id) on update cascade on delete restrict,
        platform_id text not null,
        observed_at timestamptz not null,
        metric_name text not null,
        metric_value numeric(18, 6) not null,
        currency char(3),
        raw_payload jsonb not null default '{}'::jsonb,
        created_at timestamptz not null default now(),
        updated_at timestamptz not null default now(),
        constraint market_history_points_metrics_pkey primary key (
            item_id,
            platform_id,
            observed_at,
            metric_name
        ),
        constraint market_history_points_metrics_platform_id_chk check (
            btrim(platform_id) <> ''
        ),
        constraint market_history_points_metrics_metric_name_chk check (
            btrim(metric_name) <> ''
        ),
        constraint market_history_points_metrics_metric_value_chk check (
            metric_value >= 0
        ),
        constraint market_history_points_metrics_currency_chk check (
            currency is null or currency = upper(currency)
        )
    );

    if has_sell_price then
        execute $sql$
            insert into market_history_points_metrics (
                item_id,
                platform_id,
                observed_at,
                metric_name,
                metric_value,
                currency,
                raw_payload,
                created_at,
                updated_at
            )
            select
                item_id,
                platform_id,
                observed_at,
                'sell_price',
                sell_price,
                currency,
                raw_payload,
                created_at,
                updated_at
            from market_history_points
            where sell_price is not null
        $sql$;
    end if;

    if has_buy_order_price then
        execute $sql$
            insert into market_history_points_metrics (
                item_id,
                platform_id,
                observed_at,
                metric_name,
                metric_value,
                currency,
                raw_payload,
                created_at,
                updated_at
            )
            select
                item_id,
                platform_id,
                observed_at,
                'buy_order_price',
                buy_order_price,
                currency,
                raw_payload,
                created_at,
                updated_at
            from market_history_points
            where buy_order_price is not null
        $sql$;
    end if;

    if has_sales_count then
        execute $sql$
            insert into market_history_points_metrics (
                item_id,
                platform_id,
                observed_at,
                metric_name,
                metric_value,
                raw_payload,
                created_at,
                updated_at
            )
            select
                item_id,
                platform_id,
                observed_at,
                'sales_count',
                sales_count::numeric,
                raw_payload,
                created_at,
                updated_at
            from market_history_points
            where sales_count is not null
        $sql$;
    end if;

    if has_listing_count then
        execute $sql$
            insert into market_history_points_metrics (
                item_id,
                platform_id,
                observed_at,
                metric_name,
                metric_value,
                raw_payload,
                created_at,
                updated_at
            )
            select
                item_id,
                platform_id,
                observed_at,
                'listing_count',
                listing_count::numeric,
                raw_payload,
                created_at,
                updated_at
            from market_history_points
            where listing_count is not null
        $sql$;
    end if;

    drop table market_history_points;

    alter table market_history_points_metrics rename to market_history_points;
    alter table market_history_points rename constraint market_history_points_metrics_pkey
        to market_history_points_pkey;
    alter table market_history_points rename constraint market_history_points_metrics_platform_id_chk
        to market_history_points_platform_id_chk;
    alter table market_history_points rename constraint market_history_points_metrics_metric_name_chk
        to market_history_points_metric_name_chk;
    alter table market_history_points rename constraint market_history_points_metrics_metric_value_chk
        to market_history_points_metric_value_chk;
    alter table market_history_points rename constraint market_history_points_metrics_currency_chk
        to market_history_points_currency_chk;
end $$;

create index if not exists idx_market_history_points_item_platform_metric_time
    on market_history_points (item_id, platform_id, metric_name, observed_at desc);

create index if not exists idx_market_history_points_platform_metric_time
    on market_history_points (platform_id, metric_name, observed_at desc);

commit;
