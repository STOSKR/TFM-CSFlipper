-- Supabase Table Editor cannot reliably navigate the composite relationship
-- (name, quality, stattrak) because it maps the boolean stattrak column to
-- market_items.name in the referencing-row popup. Keep the explicit view join,
-- but remove the database-level composite FK that drives those broken links.

begin;

do $$
declare
    fk_name text;
begin
    for fk_name in
        select conname
        from pg_constraint
        where conrelid = 'public.market_snapshots'::regclass
            and confrelid = 'public.market_items'::regclass
            and contype = 'f'
    loop
        execute format(
            'alter table public.market_snapshots drop constraint if exists %I',
            fk_name
        );
    end loop;
end $$;

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
