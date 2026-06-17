from decimal import Decimal
from pathlib import Path

from packages.runtime_config import load_runtime_config


def test_load_runtime_config_reads_root_numeric_values(tmp_path: Path) -> None:
    config_path = tmp_path / "csflipper_config.toml"
    config_path.write_text(
        """
        [discovery]
        candidates_limit = 25
        min_price = 100
        min_volume = 8
        currency = "EUR"

        [fees]
        steam_sale_percent = 13
        withdrawal_percent = 20

        [fees.withdrawal_percent_by_balance]
        steam_balance = 0
        platform_balance = 20

        [steamdt]
        default_profile = "platform_arbitrage_safe"

        [steamdt.profiles.platform_arbitrage_safe]
        balance_type = "Platform Balance"
        sell_mode = "Sell at Platform Lowest Price"
        buy_mode = "Buy via STEAM Buy Order"

        [workers]
        steam_concurrency = 2
        buff_concurrency = 1
        batch_size = 4

        [delays]
        steam_min_seconds = 1.0
        steam_max_seconds = 3.0
        buff_min_seconds = 2.0
        buff_max_seconds = 5.0

        [risk]
        max_position_fraction = 0.15
        max_item_fraction = 0.25
        max_platform_fraction = 0.65
        max_blocked_fraction = 0.55
        min_cash_fraction = 0.12
        min_liquidity_quantity = 3
        max_volatility = 0.30
        warning_usage_ratio = 0.75
        """,
        encoding="utf-8",
    )

    config = load_runtime_config(config_path)

    assert config.discovery.candidates_limit == 25
    assert config.discovery.min_price == Decimal("100")
    assert config.discovery.min_volume == 8
    assert config.fees.steam_sale_rate == Decimal("0.13")
    assert config.fees.withdrawal_rate == Decimal("0.2")
    assert config.fees.withdrawal_percent_for_balance("STEAM Balance") == Decimal("0")
    assert config.fees.withdrawal_percent_for_balance("Platform Balance") == Decimal("20")
    assert config.steamdt.default_profile == "platform_arbitrage_safe"
    assert config.steamdt.run_all_profiles is False
    assert (
        config.steamdt.profiles["platform_arbitrage_safe"].buy_mode
        == "Buy via STEAM Buy Order"
    )
    assert config.workers.steam_concurrency == 2
    assert config.workers.batch_size == 4
    assert config.delays.buff_max_seconds == 5.0
    assert config.risk.max_position_fraction == Decimal("0.15")
    assert config.risk.max_item_fraction == Decimal("0.25")
    assert config.risk.max_platform_fraction == Decimal("0.65")
    assert config.risk.max_blocked_fraction == Decimal("0.55")
    assert config.risk.min_cash_fraction == Decimal("0.12")
    assert config.risk.min_liquidity_quantity == 3
    assert config.risk.max_volatility == Decimal("0.30")
    assert config.risk.warning_usage_ratio == Decimal("0.75")


def test_load_runtime_config_reads_all_profile_mode_and_multiple_profiles(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "csflipper_config.toml"
    config_path.write_text(
        """
        [steamdt]
        default_profile = "steam_sell_fast"
        run_all_profiles = true
        enabled_profiles = ["steam_sell_fast"]

        [steamdt.profiles.steam_sell_fast]
        balance_type = "STEAM Balance"
        sell_mode = "Sell to STEAM Highest Buy Order"
        buy_mode = ""

        [steamdt.profiles.platform_buy_order_to_platform_highest]
        balance_type = "Platform Balance"
        sell_mode = "Sell to Platform Highest Buy Order"
        buy_mode = "Buy via STEAM Buy Order"
        """,
        encoding="utf-8",
    )

    config = load_runtime_config(config_path)

    assert config.steamdt.run_all_profiles is True
    assert config.steamdt.enabled_profiles == ("steam_sell_fast",)
    assert tuple(config.steamdt.profiles) == (
        "steam_sell_fast",
        "platform_buy_order_to_platform_highest",
    )
    assert config.steamdt.profiles["steam_sell_fast"].buy_mode is None
