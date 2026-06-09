from decimal import Decimal

from packages.runtime_config import load_runtime_config


def test_load_runtime_config_reads_root_numeric_values(tmp_path) -> None:
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

        [workers]
        steam_concurrency = 2
        buff_concurrency = 1
        batch_size = 4

        [delays]
        steam_min_seconds = 1.0
        steam_max_seconds = 3.0
        buff_min_seconds = 2.0
        buff_max_seconds = 5.0
        """,
        encoding="utf-8",
    )

    config = load_runtime_config(config_path)

    assert config.discovery.candidates_limit == 25
    assert config.discovery.min_price == Decimal("100")
    assert config.discovery.min_volume == 8
    assert config.fees.steam_sale_rate == Decimal("0.13")
    assert config.fees.withdrawal_rate == Decimal("0.2")
    assert config.workers.steam_concurrency == 2
    assert config.workers.batch_size == 4
    assert config.delays.buff_max_seconds == 5.0
