from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from packages.datasets.historical_parquet import (
    inspect_direction_parquet,
    iter_snapshots_from_direction_parquet,
    snapshots_from_direction_parquet,
)


def test_inspect_direction_parquet_reports_shape_and_dates(tmp_path: Path) -> None:
    path = tmp_path / "history.parquet"
    _write_sample_parquet(path)

    report = inspect_direction_parquet(path)

    assert report.valid is True
    assert report.rows == 2
    assert report.variants == 1
    assert report.date_column == "ds"
    assert report.min_observed_at == datetime(2026, 1, 1, tzinfo=UTC)
    assert report.max_observed_at == datetime(2026, 1, 2, tzinfo=UTC)


def test_snapshots_from_direction_parquet_maps_rows_to_steam_history(tmp_path: Path) -> None:
    path = tmp_path / "history.parquet"
    _write_sample_parquet(path)

    snapshots = snapshots_from_direction_parquet(path, currency="EUR")

    assert len(snapshots) == 1
    snapshot = snapshots[0]
    assert snapshot.name == "M249 | Aztec"
    assert snapshot.quality == "Factory New"
    assert snapshot.stattrak is False
    assert snapshot.scraped_at == datetime(2026, 1, 2, tzinfo=UTC)
    assert snapshot.steam_price == Decimal("8.25")
    assert snapshot.steam_currency == "EUR"
    assert snapshot.steam_recent_sales == (
        {
            "source": "direction_dataset_model_sample",
            "observed_at": "2026-01-01T00:00:00+00:00",
            "price": "8.16",
            "sales_count": 61,
            "variant_id": "heavy_m249_aztec__FN_st0",
            "future_return": -0.1,
            "direction": "down",
            "is_up": 0,
        },
        {
            "source": "direction_dataset_model_sample",
            "observed_at": "2026-01-02T00:00:00+00:00",
            "price": "8.25",
            "sales_count": 70,
            "variant_id": "heavy_m249_aztec__FN_st0",
            "future_return": 0.2,
            "direction": "up",
            "is_up": 1,
        },
    )


def test_iter_snapshots_keeps_variant_rows_across_parquet_row_groups(tmp_path: Path) -> None:
    path = tmp_path / "history.parquet"
    _write_sample_parquet(path, row_group_size=1)

    snapshots = tuple(iter_snapshots_from_direction_parquet(path, currency="EUR"))

    assert len(snapshots) == 1
    assert len(snapshots[0].steam_recent_sales) == 2
    assert snapshots[0].scraped_at == datetime(2026, 1, 2, tzinfo=UTC)


def _write_sample_parquet(path: Path, *, row_group_size: int | None = None) -> None:
    table = pa.table(
        {
            "variant_id": ["heavy_m249_aztec__FN_st0", "heavy_m249_aztec__FN_st0"],
            "weapon_key": ["m249", "m249"],
            "skin_key": ["aztec", "aztec"],
            "w": ["FN", "FN"],
            "st": [0, 0],
            "ds": [
                datetime(2026, 1, 1),
                datetime(2026, 1, 2),
            ],
            "sales": [61, 70],
            "price_cents": [816, 825],
            "future_return": [-0.1, 0.2],
            "direction": ["down", "up"],
            "is_up": [0, 1],
        }
    )
    pq.write_table(table, path, row_group_size=row_group_size)  # type: ignore[no-untyped-call]
