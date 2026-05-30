from pathlib import Path

import pytest

from packages.persistence.connection import load_database_url, normalize_asyncpg_dsn


def test_normalize_asyncpg_dsn_removes_sqlalchemy_driver() -> None:
    assert (
        normalize_asyncpg_dsn("postgresql+asyncpg://user:pass@localhost:5432/db")
        == "postgresql://user:pass@localhost:5432/db"
    )


def test_load_database_url_reads_env_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    env_path = tmp_path / ".env"
    env_path.write_text("DATABASE_URL=postgresql://user:pass@localhost/db\n", encoding="utf-8")

    assert load_database_url(env_path) == "postgresql://user:pass@localhost/db"
