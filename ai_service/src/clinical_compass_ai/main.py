import secrets
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException

from clinical_compass.domain.extraction import FreeTextExtraction
from clinical_compass_ai.config import Settings
from clinical_compass_ai.extractor import ExtractionError, extract
from clinical_compass_ai.provider import (
    OpenAICompatibleProvider,
    Provider,
    ProviderError,
)
from clinical_compass_ai.schemas import ExtractRequest


def create_app(provider: Provider | None = None, settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    app = FastAPI(title="Clinical Compass AI extraction")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    def require_token(authorization: Annotated[str | None, Header()] = None) -> None:
        expected = settings.service_token
        if expected is None:
            return
        provided = authorization.removeprefix("Bearer ").strip() if authorization else ""
        if not secrets.compare_digest(provided, expected):
            raise HTTPException(status_code=401, detail="invalid service token")

    # Обычный def: вызов провайдера синхронный, FastAPI выполнит его в пуле потоков
    # и не заблокирует цикл событий для других запросов.
    @app.post("/extract", response_model=FreeTextExtraction, dependencies=[Depends(require_token)])
    def extract_endpoint(request: ExtractRequest) -> FreeTextExtraction:
        try:
            configured = provider or OpenAICompatibleProvider(settings)
            return extract(request, configured, settings.model or "fake-provider")
        except ValueError as exc:
            raise HTTPException(status_code=503, detail=f"configuration error: {exc}") from exc
        except (ExtractionError, ProviderError) as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    return app


app = create_app()
