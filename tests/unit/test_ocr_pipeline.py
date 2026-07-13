from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from packages.domain.enums import SourceType
from packages.vision.ocr import OCRTextResult
from packages.vision.parser import parse_ocr_market_observations
from packages.vision.pipeline import extract_ocr_observations


def test_parse_ocr_market_observations_returns_contracts() -> None:
    records = parse_ocr_market_observations(
        "AK-47 | Slate (Field-Tested) | Steam | 12,34 EUR volume 42",
        observed_at=datetime(2026, 5, 30, tzinfo=UTC),
        correlation_id="ocr:test",
    )

    assert len(records) == 1
    assert records[0].asset_name == "AK-47 | Slate"
    assert records[0].quality == "Field-Tested"
    assert records[0].variant_key == "field-tested_st0"
    assert records[0].observation.asset_id == "ak_47_slate__field_tested"
    assert records[0].observation.platform_id == "steam"
    assert records[0].observation.price == Decimal("12.34")
    assert records[0].observation.currency == "EUR"
    assert records[0].observation.volume == 42
    assert records[0].observation.source_type == SourceType.OCR


def test_parse_ocr_market_observations_rejects_low_confidence() -> None:
    records = parse_ocr_market_observations(
        "AK-47 | Slate (Field-Tested) | Steam | 12,34 EUR",
        confidence=0.2,
        min_confidence=0.5,
    )

    assert records == ()


@pytest.mark.asyncio
async def test_extract_ocr_observations_from_text_fixture() -> None:
    records = await extract_ocr_observations(
        "tests/fixtures/ocr_observations.txt",
        correlation_id="ocr:test",
    )

    assert len(records) == 2
    assert records[1].observation.platform_id == "buff"


@pytest.mark.asyncio
async def test_extract_ocr_observations_from_image_uses_injected_runner(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    image_path = tmp_path / "capture.png"
    image_path.write_bytes(b"fake-image")
    calls: list[str] = []

    def fake_load_image(_path: object) -> object:
        calls.append("load")
        return object()

    def fake_preprocess_for_ocr(_image: object) -> object:
        calls.append("preprocess")
        return object()

    def fake_runner(_image: object) -> OCRTextResult:
        calls.append("ocr")
        return OCRTextResult(
            text="P250 | Whiteout (Minimal Wear) | Steam | 90,-- EUR",
            confidence=0.91,
        )

    monkeypatch.setattr("packages.vision.pipeline.load_image", fake_load_image)
    monkeypatch.setattr("packages.vision.pipeline.preprocess_for_ocr", fake_preprocess_for_ocr)

    records = await extract_ocr_observations(
        image_path,
        correlation_id="ocr:test",
        ocr_runner=fake_runner,
    )

    assert len(records) == 1
    assert records[0].observation.price == Decimal("90.00")
    assert records[0].confidence == 0.91
    assert calls == ["load", "preprocess", "ocr"]
