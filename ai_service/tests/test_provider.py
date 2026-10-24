import httpx
import pytest

from clinical_compass_ai.config import Settings
from clinical_compass_ai.provider import OpenAICompatibleProvider, ProviderError
from clinical_compass_ai.schemas import ModelOutput


def test_gigachat_json_schema_payload_and_content(monkeypatch):
    captured = {}

    def fake_post(url, *, headers, json, timeout):
        captured.update(url=url, headers=headers, payload=json, timeout=timeout)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"entities": [], "unknown_fields": []}'}}]},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    provider = OpenAICompatibleProvider(
        Settings(model="GigaChat-3-Ultra", api_key="test-secret", base_url="https://example.test/v1")
    )
    assert provider.complete("text") == '{"entities": [], "unknown_fields": []}'
    assert captured["url"] == "https://example.test/v1/chat/completions"
    assert captured["payload"]["response_format"] == {
        "type": "json_schema",
        "schema": ModelOutput.model_json_schema(),
        "strict": True,
    }
    assert captured["headers"]["Authorization"] == "Bearer test-secret"


def test_upstream_400_reports_bounded_body_without_secret(monkeypatch):
    secret = "test-secret"
    body = "invalid schema: " + secret + " " + "x" * 3000

    def fake_post(url, *, headers, json, timeout):
        return httpx.Response(400, text=body, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)
    provider = OpenAICompatibleProvider(
        Settings(model="GigaChat-3-Ultra", api_key=secret, base_url="https://example.test/v1")
    )
    with pytest.raises(ProviderError) as error:
        provider.complete("text")
    message = str(error.value)
    assert "HTTP 400" in message
    assert "invalid schema:" in message
    assert "[REDACTED]" in message
    assert secret not in message
    assert "Authorization" not in message
    assert len(message) < 2100
