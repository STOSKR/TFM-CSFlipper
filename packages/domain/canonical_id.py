"""Deterministic canonical identifiers for CS2 assets."""

from __future__ import annotations

import re

_SEPARATOR_PATTERN = re.compile(r"[\s_\-|\(\)\[\]/:]+")
_STATTRAK_PREFIXES = ("stattrak(tm)", "stattrak™", "stattrak")
_SOUVENIR_PREFIX = "souvenir"


def normalize_identifier_component(value: str) -> str:
    """Normalize one identifier component to a stable slug token."""

    stripped = value.strip().lower()
    replaced = _SEPARATOR_PATTERN.sub("_", stripped)
    sanitized = "".join(char for char in replaced if char.isalnum() or char == "_")
    normalized = re.sub(r"_+", "_", sanitized).strip("_")
    if not normalized:
        raise ValueError("identifier component cannot be empty after normalization")
    return normalized


def build_canonical_asset_id(
    *,
    name: str,
    quality: str | None = None,
    stattrak: bool = False,
    souvenir: bool = False,
) -> str:
    """Build a deterministic asset id from a market name and variant flags."""

    clean_name = _strip_variant_prefixes(name)
    components = [normalize_identifier_component(clean_name)]
    if quality:
        components.append(normalize_identifier_component(quality))
    if stattrak:
        components.append("stattrak")
    if souvenir:
        components.append("souvenir")
    return "__".join(components)


def _strip_variant_prefixes(value: str) -> str:
    stripped = value.strip()
    lowered = stripped.lower()

    for prefix in _STATTRAK_PREFIXES:
        if lowered.startswith(prefix):
            stripped = stripped[len(prefix) :].strip()
            lowered = stripped.lower()
            break

    if lowered.startswith(_SOUVENIR_PREFIX):
        stripped = stripped[len(_SOUVENIR_PREFIX) :].strip()

    return stripped.lstrip("*★ ").strip()
