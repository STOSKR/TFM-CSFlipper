from pathlib import Path

MIGRATION = Path("supabase/migrations/0001_initial_schema.sql")
SIMPLE_MARKET_MIGRATION = Path("supabase/migrations/0002_simple_market_snapshots.sql")


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
