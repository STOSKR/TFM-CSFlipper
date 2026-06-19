begin;

alter table market_items
    add column if not exists last_checked_at timestamptz;

update market_items
set last_checked_at = coalesce(last_checked_at, updated_at, scraped_at, created_at)
where last_checked_at is null;

create index if not exists idx_market_items_last_checked_at
    on market_items (last_checked_at desc nulls last);

commit;
