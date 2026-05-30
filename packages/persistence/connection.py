"""Database connection helpers."""

from __future__ import annotations

import os
from pathlib import Path

import asyncpg


def normalize_asyncpg_dsn(database_url: str) -> str:
    """Convert SQLAlchemy-style async URLs to asyncpg-compatible DSNs."""

    if database_url.startswith("postgresql+asyncpg://"):
        return database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return database_url


def load_database_url(env_path: Path | str = ".env") -> str:
    """Load DATABASE_URL from environment or a local .env file."""

    value = os.getenv("DATABASE_URL")
    if value:
        return value

    path = Path(env_path)
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("DATABASE_URL="):
                return stripped.split("=", 1)[1].strip()

    raise RuntimeError("DATABASE_URL is not configured")


async def create_pool(
    database_url: str | None = None,
    *,
    min_size: int = 1,
    max_size: int = 5,
) -> asyncpg.Pool:
    """Create an asyncpg pool using SSL for Supabase-compatible connections."""

    dsn = normalize_asyncpg_dsn(database_url or load_database_url())
    return await asyncpg.create_pool(dsn=dsn, min_size=min_size, max_size=max_size, ssl="require")
