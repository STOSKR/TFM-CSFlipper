"""OCR-based market observation acquisition."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from packages.vision.parser import OCRObservationRecord
from packages.vision.pipeline import extract_ocr_observations


async def load_ocr_observations(
    path: str | Path,
    *,
    observed_at: datetime | None = None,
    correlation_id: str | None = None,
    default_platform_id: str = "ocr",
    default_currency: str = "EUR",
    min_confidence: float = 0.5,
) -> tuple[OCRObservationRecord, ...]:
    return await extract_ocr_observations(
        path,
        observed_at=observed_at,
        correlation_id=correlation_id,
        default_platform_id=default_platform_id,
        default_currency=default_currency,
        min_confidence=min_confidence,
    )
