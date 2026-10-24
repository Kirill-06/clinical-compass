"""HTTP adapter for the AI extraction layer.

The application intentionally does not know which model/provider sits behind this
endpoint.  The remote service receives the same metadata as :class:`Extractor`
and must return ``FreeTextExtraction`` v0.2 (either directly or under the
``extraction`` key).

This keeps the clinical application stable while the NLP team iterates on
prompts/models independently.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx

from clinical_compass.domain.extraction import FreeTextExtraction


class RemoteExtractionError(RuntimeError):
    """Remote extractor was unavailable or returned an invalid contract."""


@dataclass(frozen=True)
class RemoteHTTPExtractor:
    url: str
    token: str | None = None
    timeout_seconds: float = 20.0
    version: str = "remote-http-0.1"

    def extract(
        self, *, message_id: str, patient_id: str, timestamp: datetime, text: str
    ) -> FreeTextExtraction:
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        payload = {
            "message_id": message_id,
            "patient_id": patient_id,
            "timestamp": timestamp.isoformat(),
            "text": text,
            "schema_version": "0.2.0",
        }
        try:
            response = httpx.post(self.url, json=payload, headers=headers, timeout=self.timeout_seconds)
            response.raise_for_status()
            document: Any = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise RemoteExtractionError(f"AI extractor request failed: {exc}") from exc

        if isinstance(document, dict) and "extraction" in document:
            document = document["extraction"]
        if not isinstance(document, dict):
            raise RemoteExtractionError("AI extractor response must be a JSON object")

        # Транспортные поля знает backend, и ответ сервиса их не переопределяет:
        # иначе ошибка модели могла бы привязать факты к чужому пациенту или сообщению.
        # Версию модели и сущности сообщает сервис.
        merged = {
            "channel": "chat",
            "model_version": self.version,
            "schema_version": "0.2.0",
            **document,
            "message_id": message_id,
            "patient_id": patient_id,
            "timestamp": timestamp.isoformat(),
            "original_text": text,
        }
        try:
            return FreeTextExtraction.model_validate(merged)
        except ValueError as exc:
            raise RemoteExtractionError(f"AI extractor returned invalid FreeTextExtraction: {exc}") from exc
