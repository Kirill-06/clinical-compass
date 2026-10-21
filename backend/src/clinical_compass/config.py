"""Настройки из переменных окружения (префикс `CC_`) и файла `.env`."""

from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT = Path(__file__).resolve().parents[3]
DEV_INTERNAL_TOKEN = "dev-internal-token"
DEV_INTEGRATION_KEYS = {"emias": "dev-emias-key", "onec": "dev-onec-key"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CC_", env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./data/clinical_compass.db"
    """PostgreSQL в production: `postgresql+psycopg://user:pass@host:5432/db`."""

    contracts_dir: Path = _REPO_ROOT / "contracts"
    storage_dir: Path = Path("./data/files")
    """Каталог вложений (локальное хранилище; для production — объектное хранилище)."""

    web_dir: Path | None = None
    """Если задан — backend отдаёт собранное Flutter Web приложение с того же адреса."""

    demo_auth: bool = True
    """Демо-вход по id без пароля. В production — False."""

    seed_demo_data: bool = True
    """Заполнить пустую базу вымышленными демо-данными при старте."""

    internal_token: str = Field(default=DEV_INTERNAL_TOKEN, min_length=8)
    """Ключ внутренних эндпоинтов AI-слоя (заголовок X-Internal-Token)."""

    integration_keys: dict[str, str] = Field(default_factory=lambda: dict(DEV_INTEGRATION_KEYS))
    """Ключи МИС для серверных вызовов `/integrations/{system}/…` (заголовок X-Integration-Key).
    Формат переменной: `CC_INTEGRATION_KEYS='{"emias": "…", "onec": "…"}'`."""

    frame_ancestors: list[str] = ["'self'"]
    """Кому разрешено встраивать окно (CSP frame-ancestors): адреса веб-клиентов МИС."""

    launch_code_seconds: int = 120
    embed_session_minutes: int = 30

    cors_origins: list[str] = ["*"]
    clinic_utc_offset_hours: int = 3
    session_ttl_hours: int = 12
    max_upload_bytes: int = 10 * 1024 * 1024
    max_files_per_message: int = 5

    fixed_now: datetime | None = None
    """Только для тестов: фиксированное «сейчас»."""

    @model_validator(mode="after")
    def _no_dev_secrets_outside_demo(self) -> Self:
        if not self.demo_auth and self.internal_token == DEV_INTERNAL_TOKEN:
            raise ValueError(
                "CC_INTERNAL_TOKEN должен быть задан, когда демо-режим выключен (CC_DEMO_AUTH=false)"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
