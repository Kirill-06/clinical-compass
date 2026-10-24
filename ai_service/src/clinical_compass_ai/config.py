from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AI_", extra="ignore")

    model: str | None = None
    api_key: str | None = None
    base_url: str = "https://api.openai.com/v1"
    timeout_seconds: float = Field(default=15.0, gt=0, le=120)

    def require_provider(self) -> None:
        if not self.model or not self.api_key:
            raise ValueError("AI_MODEL and AI_API_KEY must be configured")
