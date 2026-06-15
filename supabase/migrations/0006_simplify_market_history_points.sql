begin;

-- Keep orderbook snapshots only on market_items as JSONB arrays.
-- market_history_points stores scalar time-series prices keyed by item + observed_at.
alter table market_history_points
    drop constraint if exists market_history_points_steam_sales_count_chk,
    drop constraint if exists market_history_points_buff_listing_count_chk,
    drop constraint if exists market_history_points_steam_currency_chk,
    drop constraint if exists market_history_points_buff_currency_chk;

alter table market_history_points
    drop column if exists steam_sales_count,
    drop column if exists steam_currency,
    drop column if exists buff_listing_count,
    drop column if exists buff_currency,
    drop column if exists source_payload;

commit;
