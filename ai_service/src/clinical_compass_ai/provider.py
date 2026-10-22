from typing import Protocol

import httpx

from clinical_compass_ai.config import Settings
from clinical_compass_ai.prompts import SYSTEM_PROMPT


class ProviderError(RuntimeError):
    pass


class Provider(Protocol):
    def complete(self, text: str, repair_error: str | None = None) -> str: ...


class OpenAICompatibleProvider:
    """OpenAI-compatible chat completions transport; domain logic lives elsewhere."""

    def __init__(self, settings: Settings):
        settings.require_provider()
        self.settings = settings

    def complete(self, text: str, repair_error: str | None = None) -> str:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": text}]
        if repair_error:
            from clinical_compass_ai.prompts import REPAIR_PROMPT
            messages.append({"role": "user", "content": REPAIR_PROMPT + repair_error})
        try:
            response = httpx.post(
                self.settings.base_url.rstrip("/") + "/chat/completions",
                headers={"Authorization": f"Bearer {self.settings.api_key}"},
                json={"model": self.settings.model, "messages": messages, "temperature": 0, "response_format": {"type": "json_object"}},
                timeout=self.settings.timeout_seconds,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            if not isinstance(content, str):
                raise TypeError("non-text completion")
            return content
        except (httpx.HTTPError, KeyError, IndexError, ValueError, TypeError) as exc:
            raise ProviderError(f"provider request failed: {exc}") from exc
