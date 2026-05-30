"""Tesseract OCR adapter."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from packages.vision.preprocessing import ImageArray


class OCREngineError(RuntimeError):
    """Raised when the OCR engine is unavailable or fails."""


@dataclass(frozen=True, slots=True)
class OCRTextResult:
    text: str
    confidence: float
    engine: str = "tesseract"


def run_tesseract(
    image: ImageArray,
    *,
    lang: str = "eng",
    config: str = "--psm 6",
) -> OCRTextResult:
    try:
        import pytesseract  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise OCREngineError(
            "pytesseract is not installed. Install project dependencies and Tesseract OCR."
        ) from exc

    try:
        data = pytesseract.image_to_data(
            image,
            lang=lang,
            config=config,
            output_type=pytesseract.Output.DICT,
        )
    except Exception as exc:  # pragma: no cover - depends on local tesseract binary
        raise OCREngineError("Tesseract OCR failed") from exc

    words: list[str] = []
    confidences: list[float] = []
    for text, confidence in zip(data.get("text", []), data.get("conf", []), strict=False):
        cleaned = str(text).strip()
        if not cleaned:
            continue
        words.append(cleaned)
        parsed_confidence = _parse_confidence(confidence)
        if parsed_confidence is not None:
            confidences.append(parsed_confidence)

    average_confidence = sum(confidences) / len(confidences) if confidences else 0.0
    return OCRTextResult(
        text=" ".join(words),
        confidence=average_confidence / 100,
    )


async def run_tesseract_async(
    image: ImageArray,
    *,
    lang: str = "eng",
    config: str = "--psm 6",
) -> OCRTextResult:
    return await asyncio.to_thread(run_tesseract, image, lang=lang, config=config)


def _parse_confidence(value: object) -> float | None:
    try:
        confidence = float(str(value))
    except (TypeError, ValueError):
        return None
    if confidence < 0:
        return None
    return confidence
