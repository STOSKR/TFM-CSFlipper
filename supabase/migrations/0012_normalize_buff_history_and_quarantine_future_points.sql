begin;

-- Preserve invalid temporal observations outside the training history instead
-- of deleting them. The primary key matches the operational history table so
-- each quarantined point remains traceable to its original identity.
create table if not exists market_history_quarantine (
    item_id uuid not null references market_items(id) on update cascade on delete restrict,
    platform_id text not null,
    observed_at timestamptz not null,
    metric_name text not null,
    metric_value numeric(18, 6) not null,
    currency char(3),
    price_eur numeric(18, 6),
    price_cny numeric(18, 6),
    raw_payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null,
    updated_at timestamptz not null,
    quarantined_at timestamptz not null default now(),
    quarantine_reason text not null,
    primary key (item_id, platform_id, observed_at, metric_name),
    constraint market_history_quarantine_reason_chk check (btrim(quarantine_reason) <> '')
);

create index if not exists idx_market_history_quarantine_reason_time
    on market_history_quarantine (quarantine_reason, observed_at desc);

-- `buff163` is the legacy identifier for the same BUFF marketplace. Merge
-- the raw payload for colliding rows first, then insert non-conflicting rows
-- before removing the duplicate legacy identifiers.
update market_history_points canonical
set
    raw_payload = canonical.raw_payload || jsonb_build_object(
        'legacy_buff163', legacy.raw_payload
    ),
    updated_at = now()
from market_history_points legacy
where canonical.platform_id = 'buff'
  and legacy.platform_id = 'buff163'
  and canonical.item_id = legacy.item_id
  and canonical.observed_at = legacy.observed_at
  and canonical.metric_name = legacy.metric_name;

insert into market_history_points (
    item_id,
    platform_id,
    observed_at,
    metric_name,
    metric_value,
    currency,
    price_eur,
    price_cny,
    raw_payload,
    created_at,
    updated_at
)
select
    item_id,
    'buff',
    observed_at,
    metric_name,
    metric_value,
    currency,
    price_eur,
    price_cny,
    raw_payload,
    created_at,
    updated_at
from market_history_points
where platform_id = 'buff163'
on conflict (item_id, platform_id, observed_at, metric_name) do nothing;

delete from market_history_points
where platform_id = 'buff163';

-- These Steam points are dated after the validated collection period ending
-- on 2026-08-21. Keep them for audit, but exclude them from live queries and
-- temporal training data until their timestamps can be validated.
insert into market_history_quarantine (
    item_id,
    platform_id,
    observed_at,
    metric_name,
    metric_value,
    currency,
    price_eur,
    price_cny,
    raw_payload,
    created_at,
    updated_at,
    quarantine_reason
)
select
    item_id,
    platform_id,
    observed_at,
    metric_name,
    metric_value,
    currency,
    price_eur,
    price_cny,
    raw_payload,
    created_at,
    updated_at,
    'future_observed_at_after_2026_08_21'
from market_history_points
where platform_id = 'steam'
  and observed_at >= timestamptz '2026-08-22 00:00:00+00'
on conflict (item_id, platform_id, observed_at, metric_name) do update set
    raw_payload = excluded.raw_payload,
    updated_at = excluded.updated_at,
    quarantined_at = now(),
    quarantine_reason = excluded.quarantine_reason;

delete from market_history_points
where platform_id = 'steam'
  and observed_at >= timestamptz '2026-08-22 00:00:00+00';

create or replace view market_platform_freshness as
select
    platform_id,
    count(distinct item_id) as tracked_items,
    count(*) as history_points,
    max(observed_at) as latest_observed_at,
    min(observed_at) as earliest_observed_at
from market_history_points
group by platform_id;

commit;
