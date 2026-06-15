from pathlib import Path

MIGRATION = Path("supabase/migrations/0001_initial_schema.sql")
SIMPLE_MARKET_MIGRATION = Path("supabase/migrations/0002_simple_market_snapshots.sql")
CURRENT_MARKET_SNAPSHOT_MIGRATION = Path(
    "supabase/migrations/0003_market_snapshots_current_state.sql"
)
DROP_MARKET_SNAPSHOT_COMPOSITE_FK_MIGRATION = Path(
    "supabase/migrations/0004_drop_market_snapshots_composite_fk.sql"
)
NORMALIZE_MARKET_ITEMS_MIGRATION = Path(
    "supabase/migrations/0005_normalize_market_items_and_history.sql"
)
SIMPLIFY_MARKET_HISTORY_POINTS_MIGRATION = Path(
    "supabase/migrations/0006_simplify_market_history_points.sql"
)
LONG_MARKET_HISTORY_POINTS_MIGRATION = Path(
    "supabase/migrations/0007_long_market_history_points.sql"
)
METRIC_MARKET_HISTORY_POINTS_MIGRATION = Path(
    "supabase/migrations/0008_metric_market_history_points.sql"
)


def test_initial_migration_defines_required_tables() -> None:
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    for table_name in (
        "assets",
        "platforms",
        "market_observations",
        "outbox_events",
        "predictions",
        "risk_profiles",
        "votes",
        "investment_decisions",
        "simulated_positions",
        "legacy_scraped_items",
    ):
        assert f"create table if not exists {table_name}" in sql


def test_market_observations_are_append_only_and_deduplicated() -> None:
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    assert "market_observations_dedupe_uk unique" in sql
    assert "asset_id" in sql
    assert "platform_id" in sql
    assert "observed_at" in sql
    assert "variant_key" in sql
    assert "source_type" in sql
    assert "source_reference" in sql


def test_initial_migration_defines_operational_indexes() -> None:
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    for index_name in (
        "idx_market_observations_asset_time",
        "idx_market_observations_platform_time",
        "idx_market_observations_correlation_id",
        "idx_outbox_events_status_created",
        "idx_predictions_correlation_id",
        "idx_votes_correlation_id",
        "idx_investment_decisions_correlation_id",
    ):
        assert index_name in sql


def test_initial_migration_seeds_platforms_and_risk_profiles() -> None:
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    assert "insert into platforms" in sql
    assert "insert into risk_profiles" in sql
    assert "steam community market" in sql
    assert "risk manager" in sql


def test_simple_market_migration_defines_snapshot_tables_and_view() -> None:
    sql = SIMPLE_MARKET_MIGRATION.read_text(encoding="utf-8").lower()

    assert "create table if not exists market_items" in sql
    assert "create table if not exists market_snapshots" in sql
    assert "create or replace view market_snapshot_view" in sql
    assert "primary key (name, quality, stattrak)" in sql
    assert "primary key (name, quality, stattrak, scraped_at)" in sql


def test_simple_market_migration_keeps_platform_currencies_separate() -> None:
    sql = SIMPLE_MARKET_MIGRATION.read_text(encoding="utf-8").lower()

    assert "steam_currency char(3)" in sql
    assert "buff_currency char(3)" in sql
    assert "steam_recent_sales jsonb" in sql
    assert "steam_buy_orders jsonb" in sql
    assert "buff_recent_sales jsonb" in sql
    assert "buff_buy_orders jsonb" in sql


def test_current_market_snapshot_migration_keeps_latest_row_per_item() -> None:
    sql = CURRENT_MARKET_SNAPSHOT_MIGRATION.read_text(encoding="utf-8").lower()

    assert "row_number() over" in sql
    assert "partition by name, quality, stattrak" in sql
    assert "delete from market_snapshots" in sql
    assert "drop constraint if exists market_snapshots_pkey" in sql
    assert "primary key (name, quality, stattrak)" in sql
    assert "primary key (name, quality, stattrak, scraped_at)" not in sql
    assert "create or replace view market_snapshot_view" in sql


def test_drop_market_snapshot_composite_fk_migration_keeps_view_join() -> None:
    sql = DROP_MARKET_SNAPSHOT_COMPOSITE_FK_MIGRATION.read_text(
        encoding="utf-8"
    ).lower()

    assert "drop constraint if exists" in sql
    assert "public.market_snapshots" in sql
    assert "public.market_items" in sql
    assert "contype = 'f'" in sql
    assert "create or replace view market_snapshot_view" in sql
    assert "and i.stattrak = s.stattrak" in sql


def test_normalized_market_migration_uses_item_id_and_history_points() -> None:
    sql = NORMALIZE_MARKET_ITEMS_MIGRATION.read_text(encoding="utf-8").lower()

    assert "add column if not exists id uuid" in sql
    assert "representation_name" in sql
    assert "steam_price numeric" in sql
    assert "steam_buy_orders jsonb" in sql
    assert "buff_price numeric" in sql
    assert "buff_buy_orders jsonb" in sql
    assert "primary key (id)" in sql
    assert "market_items_id_uk" in sql
    assert "to_regclass('public.market_history_points') is not null" in sql
    assert "on market_items (name, quality, stattrak)" in sql
    assert "drop table if exists market_snapshots" in sql
    assert "create table if not exists market_history_points" in sql
    assert "buff_sell_price numeric" in sql
    assert "buff_buy_order_price numeric" in sql
    assert "buff_listing_count integer" in sql
    assert "steam_sell_price numeric" in sql
    assert "create or replace view market_snapshot_view" not in sql


def test_simplify_market_history_points_drops_redundant_columns() -> None:
    sql = SIMPLIFY_MARKET_HISTORY_POINTS_MIGRATION.read_text(encoding="utf-8").lower()

    assert "drop column if exists steam_sales_count" in sql
    assert "drop column if exists steam_currency" in sql
    assert "drop column if exists buff_listing_count" in sql
    assert "drop column if exists buff_currency" in sql
    assert "drop column if exists source_payload" in sql
    assert "market_items as jsonb arrays" in sql


def test_long_market_history_points_migration_uses_platform_rows() -> None:
    sql = LONG_MARKET_HISTORY_POINTS_MIGRATION.read_text(encoding="utf-8").lower()

    assert "platform_id text not null" in sql
    assert "sell_price numeric" in sql
    assert "buy_order_price numeric" in sql
    assert "raw_payload jsonb" in sql
    assert "primary key (" in sql
    assert "item_id," in sql
    assert "platform_id," in sql
    assert "observed_at" in sql
    assert "'steam'" in sql
    assert "'buff163'" in sql
    assert "drop table market_history_points" in sql


def test_metric_market_history_points_migration_uses_metric_rows() -> None:
    sql = METRIC_MARKET_HISTORY_POINTS_MIGRATION.read_text(encoding="utf-8").lower()

    assert "metric_name text not null" in sql
    assert "metric_value numeric" in sql
    assert "primary key (" in sql
    assert "metric_name" in sql
    assert "'sell_price'" in sql
    assert "'buy_order_price'" in sql
    assert "'sales_count'" in sql
    assert "'listing_count'" in sql
    assert "drop table market_history_points" in sql
