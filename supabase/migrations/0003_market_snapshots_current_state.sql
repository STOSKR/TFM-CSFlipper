-- Convert market_snapshots from append-only observations to the current
-- reviewable state per item variant. Historical datasets should be built from
-- the canonical market_observations tables or a dedicated history table.

begin;

drop view if exists market_snapshot_view;

with ranked_market_snapshots as (
    select
        ctid as row_id,
        row_number() over (
            partition by name, quality, stattrak
            order by scraped_at desc, created_at desc, ctid desc
        ) as row_rank
    from market_snapshots
)
delete from market_snapshots s
using ranked_market_snapshots r
where s.ctid = r.row_id
    and r.row_rank > 1;

alter table market_snapshots
    drop constraint if exists market_snapshots_pkey;

alter table market_snapshots
    add constraint market_snapshots_pkey
    primary key (name, quality, stattrak);

drop index if exists idx_market_snapshots_item_time;

create index if not exists idx_market_snapshots_scraped_at
    on market_snapshots (scraped_at desc);

create index if not exists idx_market_snapshots_item
    on market_snapshots (name, quality, stattrak);

create or replace view market_snapshot_view as
select
    s.name,
    s.quality,
    s.stattrak,
    s.scraped_at,
    i.steam_url,
    s.steam_price,
    s.steam_currency,
    s.steam_recent_sales,
    s.steam_buy_orders,
    i.buff_url,
    s.buff_price,
    s.buff_currency,
    s.buff_recent_sales,
    s.buff_buy_orders,
    s.created_at
from market_snapshots s
join market_items i
    on i.name = s.name
    and i.quality = s.quality
    and i.stattrak = s.stattrak;

commit;
