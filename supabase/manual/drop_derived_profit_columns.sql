alter table market_snapshots
    drop column if exists steam_fee_percent,
    drop column if exists withdrawal_fee_percent,
    drop column if exists net_profit,
    drop column if exists net_roi_percent,
    drop column if exists break_even_steam_price;

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
