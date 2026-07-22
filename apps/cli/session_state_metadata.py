"""Tiny metadata sidecar for Playwright session state files."""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

SESSION_TTL_DAYS = 9


def session_metadata_path(state_path: Path) -> Path:
    return state_path.with_suffix(f"{state_path.suffix}.meta.json")


def write_session_metadata(
    *,
    platform: str,
    state_path: Path,
    captured_at: datetime | None = None,
) -> dict[str, Any]:
    captured = captured_at or datetime.now(tz=UTC)
    expires = captured + timedelta(days=SESSION_TTL_DAYS)
    payload = {
        "platform": platform,
        "state_path": str(state_path),
        "captured_at": captured.isoformat(),
        "expires_at": expires.isoformat(),
        "ttl_days": SESSION_TTL_DAYS,
    }
    metadata_path = session_metadata_path(state_path)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def read_session_metadata(
    *,
    platform: str,
    state_path: Path,
    now: datetime | None = None,
) -> dict[str, Any]:
    current_time = now or datetime.now(tz=UTC)
    metadata_path = session_metadata_path(state_path)
    exists = state_path.exists()
    payload: dict[str, Any] = {
        "platform": platform,
        "exists": exists,
        "state_path": str(state_path),
        "metadata_path": str(metadata_path),
        "captured_at": None,
        "expires_at": None,
        "days_remaining": None,
        "expired": None,
    }
    if not metadata_path.exists():
        return payload
    try:
        raw = json.loads(metadata_path.read_text(encoding="utf-8"))
        captured_at = _datetime(raw.get("captured_at"))
        expires_at = _datetime(raw.get("expires_at"))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return payload
    payload["captured_at"] = captured_at.isoformat() if captured_at else None
    payload["expires_at"] = expires_at.isoformat() if expires_at else None
    if expires_at is not None:
        remaining = (expires_at - current_time).total_seconds()
        payload["days_remaining"] = max(0, math.ceil(remaining / 86400))
        payload["expired"] = remaining <= 0
    return payload


def _datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
