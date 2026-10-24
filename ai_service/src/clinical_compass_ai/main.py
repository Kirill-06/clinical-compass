from clinical_compass.domain.extraction import FreeTextExtraction
from fastapi import FastAPI, HTTPException

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

    @app.post("/extract", response_model=FreeTextExtraction)
    async def extract_endpoint(request: ExtractRequest) -> FreeTextExtraction:
        try:
            configured = provider or OpenAICompatibleProvider(settings)
            return extract(request, configured, settings.model or "fake-provider")
        except ValueError as exc:
            raise HTTPException(status_code=503, detail=f"configuration error: {exc}") from exc
        except (ExtractionError, ProviderError) as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    return app


app = create_app()
