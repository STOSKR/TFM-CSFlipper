"""Image loading and conservative OCR preprocessing."""

from __future__ import annotations

from pathlib import Path
from typing import Any

ImageArray = Any


class VisionInputError(ValueError):
    """Raised when an image cannot be loaded or preprocessed."""


def load_image(path: str | Path) -> ImageArray:
    import cv2  # type: ignore[import-not-found]

    image_path = Path(path)
    image = cv2.imread(str(image_path))
    if image is None:
        raise VisionInputError(f"could not load image: {image_path}")
    return image


def preprocess_for_ocr(image: ImageArray, *, scale: int = 2) -> ImageArray:
    import cv2

    if scale < 1:
        raise VisionInputError("scale must be >= 1")

    resized = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    denoised = cv2.fastNlMeansDenoising(enhanced, None, h=7)
    thresholded = cv2.adaptiveThreshold(
        denoised,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        11,
    )
    return cv2.cvtColor(thresholded, cv2.COLOR_GRAY2BGR)
