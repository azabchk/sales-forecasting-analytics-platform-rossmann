from app.config import Settings


def test_production_cors_uses_only_explicit_allowlist() -> None:
    settings = Settings(
        database_url="postgresql+psycopg2://u:p@localhost:5432/db",
        environment="production",
        cors_origins="https://app.example.com,https://stg-app.example.com",
        frontend_port=5173,
    )

    assert settings.cors_list == [
        "https://app.example.com",
        "https://stg-app.example.com",
    ]


def test_development_cors_adds_localhost_origins() -> None:
    settings = Settings(
        database_url="postgresql+psycopg2://u:p@localhost:5432/db",
        environment="development",
        cors_origins="https://app.example.com",
        frontend_port=5179,
    )

    assert "https://app.example.com" in settings.cors_list
    assert "http://localhost:5179" in settings.cors_list
    assert "http://127.0.0.1:5179" in settings.cors_list
