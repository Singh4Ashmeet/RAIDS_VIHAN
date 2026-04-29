"""Database URL normalization tests."""

from database import _database_sslmode, _normalize_async_database_url, _postgres_connect_args


def test_render_postgres_sslmode_is_converted_for_asyncpg() -> None:
    raw_url = "postgresql://user:pass@example.render.com/raid?sslmode=require"

    normalized = _normalize_async_database_url(raw_url)

    assert normalized == "postgresql+asyncpg://user:pass@example.render.com/raid"
    assert _database_sslmode(raw_url) == "require"
    assert _postgres_connect_args(str(normalized), "require") == {"ssl": "require"}

