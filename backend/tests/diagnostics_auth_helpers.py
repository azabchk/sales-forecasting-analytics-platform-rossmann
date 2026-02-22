from __future__ import annotations

from pathlib import Path

from src.etl.diagnostics_api_key_registry import create_api_client_key


def configure_auth_database(monkeypatch, tmp_path: Path, *, db_name: str = "diagnostics_auth.db") -> str:
    """Configure an isolated SQLite database URL for diagnostics auth tests."""
    database_path = (tmp_path / db_name).resolve()
    database_url = f"sqlite+pysqlite:///{database_path}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("DIAGNOSTICS_AUTH_ENABLED", "1")
    monkeypatch.delenv("DIAGNOSTICS_AUTH_ALLOW_LEGACY_ACTOR", raising=False)
    return database_url


def create_auth_headers(
    *,
    database_url: str,
    scopes: list[str],
    name: str = "pytest-client",
) -> tuple[dict[str, str], dict[str, object], str]:
    """Create a diagnostics API key and return request headers + record + raw key."""
    record, raw_key = create_api_client_key(
        name=name,
        scopes=scopes,
        created_by="pytest",
        database_url=database_url,
    )
    return {"X-API-Key": raw_key}, record, raw_key
