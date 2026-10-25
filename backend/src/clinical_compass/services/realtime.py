"""Доставка событий в открытые окна в реальном времени (Centrifugo).

Centrifugo только сообщает клиенту «в этом канале что-то изменилось»; сами данные
клиент берёт через API, где доступ проверяется как обычно. Поэтому:

- каналы выдаются сервером в подписанном токене подключения, клиент не может
  подписаться на чужой канал сам;
- события публикуются после коммита транзакции (`api/deps.py`), чтобы клиент
  не получил весть о сообщении, которого ещё нет в базе;
- сбой Centrifugo не ломает запрос: клиенты продолжают обновляться опросом.
"""

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

import httpx
import jwt

logger = logging.getLogger(__name__)

Json = dict[str, Any]


def chat_channel(patient_id: str) -> str:
    """Переписка пациента с его врачом."""
    return f"chat:{patient_id}"


def queue_channel(doctor_id: str) -> str:
    """Рабочая очередь врача: новые события по его пациентам."""
    return f"queue:{doctor_id}"


@dataclass(frozen=True)
class RealtimeEvent:
    channel: str
    data: Json


class Realtime(Protocol):
    @property
    def enabled(self) -> bool: ...

    @property
    def public_url(self) -> str | None: ...

    def publish(self, events: Sequence[RealtimeEvent]) -> None: ...

    def connection_token(self, user_id: str, channels: Sequence[str], ttl: timedelta) -> str: ...


class DisabledRealtime:
    """Centrifugo не настроен: события никуда не уходят, клиенты обновляются опросом."""

    enabled = False
    public_url = None

    def publish(self, events: Sequence[RealtimeEvent]) -> None:  # noqa: ARG002 — нечего публиковать
        return None

    def connection_token(self, user_id: str, channels: Sequence[str], ttl: timedelta) -> str:  # noqa: ARG002
        raise RuntimeError("Centrifugo не настроен")


@dataclass(frozen=True)
class CentrifugoRealtime:
    api_url: str
    """Серверный HTTP API Centrifugo, например `http://centrifugo:8000/api`."""
    api_key: str
    token_secret: str
    """HMAC-ключ токенов подключения (тот же, что `client.token.hmac_secret_key` в Centrifugo)."""
    public_url: str
    """WebSocket-адрес для браузера и приложения, например `wss://onco-core.ru/connection/websocket`."""
    timeout_seconds: float = 3.0

    @property
    def enabled(self) -> bool:
        return True

    def publish(self, events: Sequence[RealtimeEvent]) -> None:
        if not events:
            return
        commands = [{"publish": {"channel": e.channel, "data": e.data}} for e in events]
        try:
            response = httpx.post(
                f"{self.api_url.rstrip('/')}/batch",
                json={"commands": commands},
                headers={"X-API-Key": self.api_key},
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("Centrifugo недоступен, %d событий не доставлено: %s", len(events), exc)

    def connection_token(self, user_id: str, channels: Sequence[str], ttl: timedelta) -> str:
        now = datetime.now(UTC)
        claims = {"sub": user_id, "channels": list(channels), "iat": now, "exp": now + ttl}
        return jwt.encode(claims, self.token_secret, algorithm="HS256")
