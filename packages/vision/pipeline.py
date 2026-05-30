"""OCR extraction pipeline."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from packages.vision.ocr import OCRTextResult, run_tesseract
from packages.vision.parser import OCRObservationRecord, parse_ocr_market_observations
from packages.vision.preprocessing import ImageArray, load_image, preprocess_for_ocr

OCRRunner = Callable[[ImageArray], OCRTextResult]


async def extract_ocr_observations(
    path: str | Path,
    *,
    observed_at: datetime | None = None,
    correlation_id: str | None = None,
    default_platform_id: str = "ocr",
    default_currency: str = "EUR",
    min_confidence: float = 0.5,
    ocr_runner: OCRRunner | None = None,
) -> tuple[OCRObservationRecord, ...]:
    source_path = Path(path)
    timestamp = observed_at or datetime.now(tz=UTC)
    correlation = correlation_id or f"ocr:{uuid4()}"

    if source_path.suffix.lower() == ".txt":
        text = await asyncio.to_thread(source_path.read_text, encoding="utf-8")
        confidence = 1.0
    else:
        image = await asyncio.to_thread(load_image, source_path)
        preprocessed = await asyncio.to_thread(preprocess_for_ocr, image)
        runner = ocr_runner or run_tesseract
        result = await asyncio.to_thread(runner, preprocessed)
        text = result.text
        confidence = result.confidence

    return parse_ocr_market_observations(
        text,
        observed_at=timestamp,
        correlation_id=correlation,
        default_platform_id=default_platform_id,
        default_currency=default_currency,
        confidence=confidence,
        min_confidence=min_confidence,
        source_reference=str(source_path),
    )
