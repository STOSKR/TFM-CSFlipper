from datetime import UTC, datetime
from decimal import Decimal

from packages.datasets.history_archive import (
    load_history_archive,
    write_snapshot_history_archive,
)
from packages.persistence.simple_market import SimpleMarketSnapshot


def test_history_archive_writes_deduplicated_parquet_and_verified_backup(tmp_path) -> None:
    snapshot = SimpleMarketSnapshot(
        name="AK-47 | Slate",
        quality="Field-Tested",
        stattrak=False,
        scraped_at=datetime(2026, 8, 21, 10, 0, tzinfo=UTC),
        steam_price=Decimal("12.50"),
        steam_currency="EUR",
        buff_price=Decimal("80"),
        buff_currency="CNY",
    )
    archive_dir = tmp_path / "archive"
    backup_dir = tmp_path / "backup"

    first = write_snapshot_history_archive(
        (snapshot,),
        archive_dir=archive_dir,
        backup_dir=backup_dir,
        cny_per_eur=Decimal("8"),
    )
    second = write_snapshot_history_archive(
        (snapshot,),
        archive_dir=archive_dir,
        backup_dir=backup_dir,
        cny_per_eur=Decimal("8"),
    )

    assert first.rows == 2
    assert len(first.files) == 1
    assert first.files[0].exists()
    assert first.backup_files[0].exists()
    assert second.files == first.files
    assert len(list(archive_dir.rglob("*.parquet"))) == 1

    frame = load_history_archive(archive_dir)

    assert len(frame) == 2
    assert set(frame["platform_id"]) == {"steam", "buff"}
    assert set(frame["price_eur"].round(2)) == {10.0, 12.5}
    assert set(frame["item_id"]) == {"AK-47 | Slate_FT_0"}
