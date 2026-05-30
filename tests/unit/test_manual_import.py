import json
from decimal import Decimal
from pathlib import Path

import pytest

from apps.acquisition.manual_import import ManualImportError, load_manual_observations
from packages.domain.enums import SourceType


def test_load_manual_csv_observation(tmp_path: Path) -> None:
    path = tmp_path / "observations.csv"
    path.write_text(
        "\n".join(
            [
                "asset_name,quality,stattrak,platform_id,observed_at,price,currency,volume",
                "AK-47 | Slate,Field-Tested,true,steam,2026-05-30T12:00:00+00:00,12.34,eur,7",
            ]
        ),
        encoding="utf-8",
    )

    records = load_manual_observations(path)

    assert len(records) == 1
    assert records[0].asset_name == "AK-47 | Slate"
    assert records[0].quality == "Field-Tested"
    assert records[0].variant_key == "field-tested_st1"
    assert records[0].observation.asset_id == "ak_47_slate__field_tested__stattrak"
    assert records[0].observation.currency == "EUR"
    assert records[0].observation.volume == 7


def test_load_grouped_cs_scraper_json(tmp_path: Path) -> None:
    path = tmp_path / "ak_slate.json"
    path.write_text(
        json.dumps(
            {
                "item_key": "AK-47 | Slate",
                "variants": {
                    "FT_st1": {
                        "w": "FT",
                        "st": 1,
                        "ccy": "EUR",
                        "series": [{"t": 1780142400, "p": 1234, "vol": 3}],
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    records = load_manual_observations(path)

    assert len(records) == 1
    assert records[0].observation.platform_id == "steam"
    assert records[0].observation.source_type == SourceType.CSV
    assert records[0].observation.price == Decimal("12.34")


def test_invalid_manual_csv_reports_row_number(tmp_path: Path) -> None:
    path = tmp_path / "bad.csv"
    path.write_text("asset_name,price\nAK-47 | Slate,12.34\n", encoding="utf-8")

    with pytest.raises(ManualImportError, match="invalid row 2"):
        load_manual_observations(path)
