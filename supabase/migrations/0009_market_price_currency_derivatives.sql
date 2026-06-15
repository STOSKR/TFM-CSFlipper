begin;

create table if not exists market_currency_rates (
    base_currency char(3) not null,
    quote_currency char(3) not null,
    effective_from timestamptz not null,
    rate numeric(18, 6) not null,
    source text not null,
    created_at timestamptz not null default now(),
    primary key (base_currency, quote_currency, effective_from),
    constraint market_currency_rates_base_currency_chk check (
        base_currency = upper(base_currency)
    ),
    constraint market_currency_rates_quote_currency_chk check (
        quote_currency = upper(quote_currency)
    ),
    constraint market_currency_rates_rate_chk check (rate > 0),
    constraint market_currency_rates_source_chk check (btrim(source) <> '')
);

insert into market_currency_rates (
    base_currency,
    quote_currency,
    effective_from,
    rate,
    source
)
values (
    'EUR',
    'CNY',
    '1970-01-01 00:00:00+00',
    8,
    'excel_operativo_initial'
)
on conflict (base_currency, quote_currency, effective_from) do nothing;

-- Keep the scraped original price/currency, and add the two spreadsheet-style
-- converted prices used for comparisons.
alter table market_items
    add column if not exists steam_price_eur numeric(18, 6),
    add column if not exists steam_price_cny numeric(18, 6),
    add column if not exists buff_price_eur numeric(18, 6),
    add column if not exists buff_price_cny numeric(18, 6);

alter table market_history_points
    add column if not exists price_eur numeric(18, 6),
    add column if not exists price_cny numeric(18, 6);

with latest_eur_cny as (
    select rate as cny_per_eur
    from market_currency_rates
    where base_currency = 'EUR'
      and quote_currency = 'CNY'
    order by effective_from desc
    limit 1
)
update market_items
set
    steam_price_eur = case
        when steam_price is null or steam_currency is null then null
        when upper(steam_currency) = 'EUR' then steam_price
        when upper(steam_currency) = 'CNY' then steam_price / latest_eur_cny.cny_per_eur
        else null
    end,
    steam_price_cny = case
        when steam_price is null or steam_currency is null then null
        when upper(steam_currency) = 'CNY' then steam_price
        when upper(steam_currency) = 'EUR' then steam_price * latest_eur_cny.cny_per_eur
        else null
    end,
    buff_price_eur = case
        when buff_price is null or buff_currency is null then null
        when upper(buff_currency) = 'EUR' then buff_price
        when upper(buff_currency) = 'CNY' then buff_price / latest_eur_cny.cny_per_eur
        else null
    end,
    buff_price_cny = case
        when buff_price is null or buff_currency is null then null
        when upper(buff_currency) = 'CNY' then buff_price
        when upper(buff_currency) = 'EUR' then buff_price * latest_eur_cny.cny_per_eur
        else null
    end
from latest_eur_cny;

with latest_eur_cny as (
    select rate as cny_per_eur
    from market_currency_rates
    where base_currency = 'EUR'
      and quote_currency = 'CNY'
    order by effective_from desc
    limit 1
)
update market_history_points
set
    price_eur = case
        when metric_name not in ('sell_price', 'buy_order_price') then null
        when currency is null then null
        when upper(currency) = 'EUR' then metric_value
        when upper(currency) = 'CNY' then metric_value / latest_eur_cny.cny_per_eur
        else null
    end,
    price_cny = case
        when metric_name not in ('sell_price', 'buy_order_price') then null
        when currency is null then null
        when upper(currency) = 'CNY' then metric_value
        when upper(currency) = 'EUR' then metric_value * latest_eur_cny.cny_per_eur
        else null
    end
from latest_eur_cny;

alter table market_items
    drop constraint if exists market_items_steam_price_eur_chk,
    drop constraint if exists market_items_steam_price_cny_chk,
    drop constraint if exists market_items_buff_price_eur_chk,
    drop constraint if exists market_items_buff_price_cny_chk;

alter table market_items
    add constraint market_items_steam_price_eur_chk check (
        steam_price_eur is null or steam_price_eur > 0
    ),
    add constraint market_items_steam_price_cny_chk check (
        steam_price_cny is null or steam_price_cny > 0
    ),
    add constraint market_items_buff_price_eur_chk check (
        buff_price_eur is null or buff_price_eur > 0
    ),
    add constraint market_items_buff_price_cny_chk check (
        buff_price_cny is null or buff_price_cny > 0
    );

alter table market_history_points
    drop constraint if exists market_history_points_price_eur_chk,
    drop constraint if exists market_history_points_price_cny_chk;

alter table market_history_points
    add constraint market_history_points_price_eur_chk check (
        price_eur is null or price_eur >= 0
    ),
    add constraint market_history_points_price_cny_chk check (
        price_cny is null or price_cny >= 0
    );

commit;
