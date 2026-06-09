-- Simple phase-1 market snapshot storage.
-- The canonical TFM schema remains available, but these tables keep the
-- scraping dataset compact and easy to inspect in Supabase.

create table if not exists market_items (
    name text not null,
    quality text not null,
    stattrak boolean not null default false,
    steam_url text,
    buff_url text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    primary key (name, quality, stattrak),
    constraint market_items_name_chk check (btrim(name) <> ''),
    constraint market_items_quality_chk check (btrim(quality) <> '')
);

create table if not exists market_snapshots (
    name text not null,
    quality text not null,
    stattrak boolean not null default false,
    scraped_at timestamptz not null,
    currency char(3) not null default 'EUR',
    steam_price numeric(18, 6),
    steam_recent_sales jsonb not null default '[]'::jsonb,
    steam_buy_orders jsonb not null default '[]'::jsonb,
    buff_price numeric(18, 6),
    buff_recent_sales jsonb not null default '[]'::jsonb,
    buff_buy_orders jsonb not null default '[]'::jsonb,
    created_at timestamptz not null default now(),
    primary key (name, quality, stattrak, scraped_at),
    foreign key (name, quality, stattrak)
        references market_items (name, quality, stattrak)
        on update cascade
        on delete restrict,
    constraint market_snapshots_currency_chk check (currency = upper(currency)),
    constraint market_snapshots_steam_price_chk check (
        steam_price is null or steam_price > 0
    ),
    constraint market_snapshots_buff_price_chk check (
        buff_price is null or buff_price > 0
    ),
    constraint market_snapshots_steam_recent_sales_chk check (
        jsonb_typeof(steam_recent_sales) = 'array'
    ),
    constraint market_snapshots_steam_buy_orders_chk check (
        jsonb_typeof(steam_buy_orders) = 'array'
    ),
    constraint market_snapshots_buff_recent_sales_chk check (
        jsonb_typeof(buff_recent_sales) = 'array'
    ),
    constraint market_snapshots_buff_buy_orders_chk check (
        jsonb_typeof(buff_buy_orders) = 'array'
    )
);

create index if not exists idx_market_snapshots_scraped_at
    on market_snapshots (scraped_at desc);

create index if not exists idx_market_snapshots_item_time
    on market_snapshots (name, quality, stattrak, scraped_at desc);

create or replace view market_snapshot_view as
select
    s.name,
    s.quality,
    s.stattrak,
    s.scraped_at,
    s.currency,
    i.steam_url,
    s.steam_price,
    s.steam_recent_sales,
    s.steam_buy_orders,
    i.buff_url,
    s.buff_price,
    s.buff_recent_sales,
    s.buff_buy_orders,
    s.created_at
from market_snapshots s
join market_items i
    on i.name = s.name
    and i.quality = s.quality
    and i.stattrak = s.stattrak;
