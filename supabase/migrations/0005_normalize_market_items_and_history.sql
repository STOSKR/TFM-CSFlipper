-- Consolidate the phase-1 market schema:
-- - market_items keeps one current state row per item variant.
-- - market_history_points keeps the time series used for datasets/backtests.
-- - market_snapshots is removed after its current-state data is migrated.

begin;

create extension if not exists pgcrypto;

drop view if exists market_snapshot_view;

alter table market_items
    add column if not exists id uuid default gen_random_uuid();

update market_items
set id = gen_random_uuid()
where id is null;

alter table market_items
    alter column id set not null;

alter table market_items
    add column if not exists representation_name text,
    add column if not exists scraped_at timestamptz,
    add column if not exists steam_price numeric(18, 6),
    add column if not exists steam_currency char(3),
    add column if not exists steam_buy_orders jsonb not null default '[]'::jsonb,
    add column if not exists buff_price numeric(18, 6),
    add column if not exists buff_currency char(3),
    add column if not exists buff_buy_orders jsonb not null default '[]'::jsonb;

update market_items
set representation_name = concat_ws(
    '_',
    name,
    case quality
        when 'Factory New' then 'FN'
        when 'Minimal Wear' then 'MW'
        when 'Field-Tested' then 'FT'
        when 'Well-Worn' then 'WW'
        when 'Battle-Scarred' then 'BS'
        else replace(upper(quality), ' ', '_')
    end,
    case when stattrak then '1' else '0' end
)
where representation_name is null or btrim(representation_name) = '';

alter table market_items
    alter column representation_name set not null;

update market_items i
set
    scraped_at = s.scraped_at,
    steam_price = s.steam_price,
    steam_currency = s.steam_currency,
    steam_buy_orders = s.steam_buy_orders,
    buff_price = s.buff_price,
    buff_currency = s.buff_currency,
    buff_buy_orders = s.buff_buy_orders
from market_snapshots s
where i.name = s.name
  and i.quality = s.quality
  and i.stattrak = s.stattrak
  and (
    i.scraped_at is null
    or s.scraped_at >= i.scraped_at
  );

alter table market_items
    drop constraint if exists market_items_pkey;

alter table market_items
    add constraint market_items_pkey primary key (id);

create unique index if not exists market_items_variant_uk
    on market_items (name, quality, stattrak);

create unique index if not exists market_items_representation_name_uk
    on market_items (representation_name);

alter table market_items
    add constraint market_items_steam_currency_chk check (
        steam_currency is null or steam_currency = upper(steam_currency)
    ),
    add constraint market_items_buff_currency_chk check (
        buff_currency is null or buff_currency = upper(buff_currency)
    ),
    add constraint market_items_steam_price_chk check (
        steam_price is null or steam_price > 0
    ),
    add constraint market_items_buff_price_chk check (
        buff_price is null or buff_price > 0
    ),
    add constraint market_items_steam_buy_orders_chk check (
        jsonb_typeof(steam_buy_orders) = 'array'
    ),
    add constraint market_items_buff_buy_orders_chk check (
        jsonb_typeof(buff_buy_orders) = 'array'
    );

create table if not exists market_history_points (
    item_id uuid not null references market_items(id) on update cascade on delete restrict,
    observed_at timestamptz not null,
    steam_sell_price numeric(18, 6),
    steam_sales_count integer,
    steam_currency char(3),
    buff_sell_price numeric(18, 6),
    buff_buy_order_price numeric(18, 6),
    buff_listing_count integer,
    buff_currency char(3),
    source_payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    primary key (item_id, observed_at),
    constraint market_history_points_steam_price_chk check (
        steam_sell_price is null or steam_sell_price > 0
    ),
    constraint market_history_points_buff_sell_price_chk check (
        buff_sell_price is null or buff_sell_price > 0
    ),
    constraint market_history_points_buff_buy_order_price_chk check (
        buff_buy_order_price is null or buff_buy_order_price > 0
    ),
    constraint market_history_points_steam_sales_count_chk check (
        steam_sales_count is null or steam_sales_count >= 0
    ),
    constraint market_history_points_buff_listing_count_chk check (
        buff_listing_count is null or buff_listing_count >= 0
    ),
    constraint market_history_points_steam_currency_chk check (
        steam_currency is null or steam_currency = upper(steam_currency)
    ),
    constraint market_history_points_buff_currency_chk check (
        buff_currency is null or buff_currency = upper(buff_currency)
    )
);

create index if not exists idx_market_history_points_item_time
    on market_history_points (item_id, observed_at desc);

drop table if exists market_snapshots;

create or replace view market_snapshot_view as
select
    i.id as item_id,
    i.representation_name,
    i.name,
    i.quality,
    i.stattrak,
    i.scraped_at,
    i.steam_url,
    i.steam_price,
    i.steam_currency,
    i.steam_buy_orders,
    i.buff_url,
    i.buff_price,
    i.buff_currency,
    i.buff_buy_orders,
    i.created_at,
    i.updated_at
from market_items i;

commit;
