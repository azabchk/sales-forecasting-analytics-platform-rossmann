from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    cors_origins: str = "http://localhost:5173"
    cors_allow_origins: str | None = None
    environment: str = "development"
    frontend_port: int = 5173
    model_path: str = "ml/artifacts/model.joblib"
    model_metadata_path: str = "ml/artifacts/model_metadata.json"
    chat_model_path: str = "ml/artifacts/chat_intent_model.joblib"
    chat_min_confidence: float = 0.45

    backend_host: str = "0.0.0.0"
    backend_port: int = 8000

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parents[2] / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_list(self) -> list[str]:
        raw_origins = self.cors_allow_origins if self.cors_allow_origins else self.cors_origins
        origins = [item.strip() for item in raw_origins.split(",") if item.strip()]
        if self.environment.lower() != "production":
            dev_origins = [
                f"http://localhost:{self.frontend_port}",
                f"http://127.0.0.1:{self.frontend_port}",
                "http://localhost:5173",
                "http://127.0.0.1:5173",
            ]
            origins = list(dict.fromkeys([*origins, *dev_origins]))
        return origins


@lru_cache
def get_settings() -> Settings:
    return Settings()
