begin;

-- Convert market_history_points from platform-specific columns into a long table.
-- Safe to run more than once: if platform_id already exists, the table is already long.
do $$
declare
    has_platform_id boolean;
    has_steam_sell_price boolean;
    has_buff_sell_price boolean;
    has_buff_buy_order_price boolean;
begin
    if to_regclass('public.market_history_points') is null then
        create table market_history_points (
            item_id uuid not null references market_items(id) on update cascade on delete restrict,
            platform_id text not null,
            observed_at timestamptz not null,
            sell_price numeric(18, 6),
            buy_order_price numeric(18, 6),
            sales_count integer,
            listing_count integer,
            currency char(3),
            raw_payload jsonb not null default '{}'::jsonb,
            created_at timestamptz not null default now(),
            updated_at timestamptz not null default now(),
            constraint market_history_points_pkey primary key (
                item_id,
                platform_id,
                observed_at
            ),
            constraint market_history_points_platform_id_chk check (btrim(platform_id) <> ''),
            constraint market_history_points_sell_price_chk check (
                sell_price is null or sell_price > 0
            ),
            constraint market_history_points_buy_order_price_chk check (
                buy_order_price is null or buy_order_price > 0
            ),
            constraint market_history_points_sales_count_chk check (
                sales_count is null or sales_count >= 0
            ),
            constraint market_history_points_listing_count_chk check (
                listing_count is null or listing_count >= 0
            ),
            constraint market_history_points_currency_chk check (
                currency is null or currency = upper(currency)
            ),
            constraint market_history_points_metric_chk check (
                sell_price is not null
                or buy_order_price is not null
                or sales_count is not null
                or listing_count is not null
            )
        );
        return;
    end if;

    select exists (
        select 1
        from information_schema.columns
        where table_schema = 'public'
          and table_name = 'market_history_points'
          and column_name = 'platform_id'
    )
    into has_platform_id;

    if has_platform_id then
        return;
    end if;

    select exists (
        select 1
        from information_schema.columns
        where table_schema = 'public'
          and table_name = 'market_history_points'
          and column_name = 'steam_sell_price'
    )
    into has_steam_sell_price;

    select exists (
        select 1
        from information_schema.columns
        where table_schema = 'public'
          and table_name = 'market_history_points'
          and column_name = 'buff_sell_price'
    )
    into has_buff_sell_price;

    select exists (
        select 1
        from information_schema.columns
        where table_schema = 'public'
          and table_name = 'market_history_points'
          and column_name = 'buff_buy_order_price'
    )
    into has_buff_buy_order_price;

    drop table if exists market_history_points_long;

    create table market_history_points_long (
        item_id uuid not null references market_items(id) on update cascade on delete restrict,
        platform_id text not null,
        observed_at timestamptz not null,
        sell_price numeric(18, 6),
        buy_order_price numeric(18, 6),
        sales_count integer,
        listing_count integer,
        currency char(3),
        raw_payload jsonb not null default '{}'::jsonb,
        created_at timestamptz not null default now(),
        updated_at timestamptz not null default now(),
        constraint market_history_points_long_pkey primary key (
            item_id,
            platform_id,
            observed_at
        ),
        constraint market_history_points_long_platform_id_chk check (btrim(platform_id) <> ''),
        constraint market_history_points_long_sell_price_chk check (
            sell_price is null or sell_price > 0
        ),
        constraint market_history_points_long_buy_order_price_chk check (
            buy_order_price is null or buy_order_price > 0
        ),
        constraint market_history_points_long_sales_count_chk check (
            sales_count is null or sales_count >= 0
        ),
        constraint market_history_points_long_listing_count_chk check (
            listing_count is null or listing_count >= 0
        ),
        constraint market_history_points_long_currency_chk check (
            currency is null or currency = upper(currency)
        ),
        constraint market_history_points_long_metric_chk check (
            sell_price is not null
            or buy_order_price is not null
            or sales_count is not null
            or listing_count is not null
        )
    );

    if has_steam_sell_price then
        execute $sql$
            insert into market_history_points_long (
                item_id,
                platform_id,
                observed_at,
                sell_price,
                created_at,
                updated_at
            )
            select
                item_id,
                'steam',
                observed_at,
                steam_sell_price,
                created_at,
                updated_at
            from market_history_points
            where steam_sell_price is not null
        $sql$;
    end if;

    if has_buff_sell_price or has_buff_buy_order_price then
        execute format(
            $sql$
                insert into market_history_points_long (
                    item_id,
                    platform_id,
                    observed_at,
                    sell_price,
                    buy_order_price,
                    created_at,
                    updated_at
                )
                select
                    item_id,
                    'buff',
                    observed_at,
                    %s,
                    %s,
                    created_at,
                    updated_at
                from market_history_points
                where %s is not null
                   or %s is not null
            $sql$,
            case when has_buff_sell_price then 'buff_sell_price' else 'null::numeric' end,
            case
                when has_buff_buy_order_price then 'buff_buy_order_price'
                else 'null::numeric'
            end,
            case when has_buff_sell_price then 'buff_sell_price' else 'null::numeric' end,
            case
                when has_buff_buy_order_price then 'buff_buy_order_price'
                else 'null::numeric'
            end
        );
    end if;

    drop table market_history_points;

    alter table market_history_points_long rename to market_history_points;
    alter table market_history_points rename constraint market_history_points_long_pkey
        to market_history_points_pkey;
    alter table market_history_points rename constraint market_history_points_long_platform_id_chk
        to market_history_points_platform_id_chk;
    alter table market_history_points rename constraint market_history_points_long_sell_price_chk
        to market_history_points_sell_price_chk;
    alter table market_history_points rename constraint market_history_points_long_buy_order_price_chk
        to market_history_points_buy_order_price_chk;
    alter table market_history_points rename constraint market_history_points_long_sales_count_chk
        to market_history_points_sales_count_chk;
    alter table market_history_points rename constraint market_history_points_long_listing_count_chk
        to market_history_points_listing_count_chk;
    alter table market_history_points rename constraint market_history_points_long_currency_chk
        to market_history_points_currency_chk;
    alter table market_history_points rename constraint market_history_points_long_metric_chk
        to market_history_points_metric_chk;
end $$;

create index if not exists idx_market_history_points_item_platform_time
    on market_history_points (item_id, platform_id, observed_at desc);

create index if not exists idx_market_history_points_platform_time
    on market_history_points (platform_id, observed_at desc);

commit;
