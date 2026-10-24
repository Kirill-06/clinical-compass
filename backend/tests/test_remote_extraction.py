"""HTTP-адаптер внешнего AI-сервиса: контракт ответа и транспортные поля."""

from datetime import UTC, datetime
from typing import Any

import httpx
import pytest

from clinical_compass.domain.remote_extraction import RemoteExtractionError, RemoteHTTPExtractor

AT = datetime(2026, 10, 21, 9, 0, tzinfo=UTC)
TEXT = "Болит голова"


def _respond(monkeypatch: pytest.MonkeyPatch, status: int, body: Any) -> list[dict[str, Any]]:
    """Подменяет сетевой вызов; возвращает список запросов, отправленных адаптером."""
    sent: list[dict[str, Any]] = []

    def fake_post(
        url: str, *, json: dict[str, Any], headers: dict[str, str], timeout: float
    ) -> httpx.Response:
        sent.append({"url": url, "json": json, "headers": headers, "timeout": timeout})
        return httpx.Response(status, json=body, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)
    return sent


def _extract(extractor: RemoteHTTPExtractor) -> Any:
    return extractor.extract(message_id="msg_1", patient_id="p_a1", timestamp=AT, text=TEXT)


def test_service_cannot_override_transport_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    _respond(
        monkeypatch,
        200,
        {
            "message_id": "msg_other",
            "patient_id": "p_other",
            "timestamp": "2020-01-01T00:00:00Z",
            "original_text": "чужой текст",
            "model_version": "GigaChat-3-Ultra:extractor_prompt_v1.2",
            "entities": [],
        },
    )
    extraction = _extract(RemoteHTTPExtractor(url="http://ai/extract"))
    assert (extraction.message_id, extraction.patient_id, extraction.original_text) == ("msg_1", "p_a1", TEXT)
    assert extraction.timestamp == AT
    # Версию модели сообщает сервис — она нужна для разбора качества.
    assert extraction.model_version == "GigaChat-3-Ultra:extractor_prompt_v1.2"


def test_token_and_timeout_are_sent(monkeypatch: pytest.MonkeyPatch) -> None:
    sent = _respond(monkeypatch, 200, {"extraction": {"entities": []}})
    _extract(RemoteHTTPExtractor(url="http://ai/extract", token="secret", timeout_seconds=7))
    [request] = sent
    assert request["headers"]["Authorization"] == "Bearer secret"
    assert request["timeout"] == 7
    assert request["json"]["patient_id"] == "p_a1"


@pytest.mark.parametrize(
    ("status", "body"), [(502, {"detail": "provider error"}), (200, ["not", "an", "object"])]
)
def test_unusable_answers_raise_extraction_error(
    monkeypatch: pytest.MonkeyPatch, status: int, body: Any
) -> None:
    _respond(monkeypatch, status, body)
    with pytest.raises(RemoteExtractionError):
        _extract(RemoteHTTPExtractor(url="http://ai/extract"))
