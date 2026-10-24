"""Настройки сервиса (переменные окружения с префиксом `AI_`)."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AI_", extra="ignore")

    model: str | None = None
    api_key: str | None = None
    base_url: str = "https://api.openai.com/v1"
    timeout_seconds: float = Field(default=15.0, gt=0, le=120)
    service_token: str | None = Field(default=None, min_length=16)
    """Если задан, `/extract` требует `Authorization: Bearer <token>`.

    Тот же токен backend передаёт из `CC_EXTRACTOR_TOKEN`."""

    def require_provider(self) -> None:
        if not self.model or not self.api_key:
            raise ValueError("AI_MODEL and AI_API_KEY must be configured")
