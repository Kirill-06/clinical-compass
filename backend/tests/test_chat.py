"""Чат врача с пациентом: переписка, права, непрочитанные и доставка через Centrifugo."""

from collections.abc import Sequence
from datetime import timedelta
from typing import Any

import jwt

from clinical_compass.services.realtime import CentrifugoRealtime, RealtimeEvent
from conftest import Api, ApiFactory

SECRET = "test-centrifugo-token-secret-32-bytes!"


class RecordingRealtime:
    """Вместо Centrifugo: запоминает, что и когда было бы опубликовано."""

    enabled = True
    public_url = "wss://example.test/connection/websocket"

    def __init__(self) -> None:
        self.published: list[RealtimeEvent] = []

    def publish(self, events: Sequence[RealtimeEvent]) -> None:
        self.published.extend(events)

    def connection_token(self, user_id: str, channels: Sequence[str], ttl: timedelta) -> str:
        return f"token-for-{user_id}"


def _chat(api: Api, patient_id: str, as_: str) -> list[dict[str, Any]]:
    status, body = api.call("GET", f"/patients/{patient_id}/chat", as_=as_)
    assert status == 200, body
    return list(body["messages"])


def _open_chat(api: Api, patient_id: str, as_: str) -> int:
    """Как клиент: прочитать ленту и отметить сообщения собеседника прочитанными."""
    _chat(api, patient_id, as_)
    status, body = api.call("POST", f"/patients/{patient_id}/chat/read", as_=as_)
    assert status == 200, body
    return int(body["marked"])


def test_doctor_and_patient_exchange_messages_in_one_thread(api: Api) -> None:
    api.call("POST", "/patients/p_a1/messages", as_="p_a1", body={"text": "Стала хуже спать"})
    status, reply = api.call(
        "POST",
        "/doctor/patients/p_a1/messages",
        as_="doc_a",
        body={"text": "Давайте обсудим на приёме в четверг"},
    )
    assert status == 201
    assert reply["message"]["sender"] == "doctor"

    thread = _chat(api, "p_a1", as_="p_a1")
    assert [(m["sender"], m["text"]) for m in thread] == [
        ("patient", "Стала хуже спать"),
        ("doctor", "Давайте обсудим на приёме в четверг"),
    ]
    assert [m["text"] for m in _chat(api, "p_a1", as_="doc_a")][-1] == "Давайте обсудим на приёме в четверг"


def test_only_the_linked_doctor_can_reply(api: Api) -> None:
    body = {"text": "Здравствуйте"}
    assert api.call("POST", "/doctor/patients/p_a1/messages", as_="doc_b", body=body)[0] == 403
    assert api.call("POST", "/doctor/patients/p_a1/messages", as_="p_a1", body=body)[0] == 403
    assert api.call("GET", "/patients/p_a1/chat", as_="doc_b")[0] == 403
    assert api.call("GET", "/patients/p_a2/chat", as_="p_a1")[0] == 403
    assert api.call("POST", "/patients/p_a1/chat/read", as_="doc_b")[0] == 403
    assert api.call("POST", "/doctor/patients/p_a1/messages", as_="doc_a", body={"text": "  "})[0] == 400


def test_unread_counters_clear_when_the_chat_is_opened(api: Api) -> None:
    api.call("POST", "/doctor/patients/p_a1/messages", as_="doc_a", body={"text": "Как самочувствие?"})
    # Чтение ленты ничего не меняет: отметку ставит только явный запрос.
    _chat(api, "p_a1", as_="p_a1")
    assert api.call("GET", "/patients/p_a1/dashboard", as_="p_a1")[1]["unread_messages"] == 1
    assert _open_chat(api, "p_a1", as_="p_a1") == 1
    assert api.call("GET", "/patients/p_a1/dashboard", as_="p_a1")[1]["unread_messages"] == 0

    api.call("POST", "/patients/p_a1/messages", as_="p_a1", body={"text": "Лучше, спасибо"})
    rows = {r["patient"]["id"]: r for r in api.call("GET", "/doctor/patients", as_="doc_a")[1]}
    assert rows["p_a1"]["unread_messages"] == 1
    _open_chat(api, "p_a1", as_="doc_a")
    rows = {r["patient"]["id"]: r for r in api.call("GET", "/doctor/patients", as_="doc_a")[1]}
    assert rows["p_a1"]["unread_messages"] == 0


def test_new_messages_and_alerts_are_published_after_commit(make_api: ApiFactory) -> None:
    realtime = RecordingRealtime()
    api = make_api(realtime=realtime)
    api.call("POST", "/doctor/patients/p_a1/messages", as_="doc_a", body={"text": "Как вы?"})
    assert [e.channel for e in realtime.published] == ["chat:p_a1"]

    realtime.published.clear()
    api.call("POST", "/patients/p_a1/messages", as_="p_a1", body={"text": "Последние дни не хочу жить"})
    channels = [e.channel for e in realtime.published]
    # Новое сообщение в чате пациента и новое срочное событие в очереди его врача.
    assert channels == ["chat:p_a1", "queue:doc_a"]


def test_failed_request_publishes_nothing(make_api: ApiFactory) -> None:
    realtime = RecordingRealtime()
    api = make_api(realtime=realtime)
    assert api.call("POST", "/doctor/patients/p_a1/messages", as_="doc_b", body={"text": "x"})[0] == 403
    assert realtime.published == []


def test_realtime_is_reported_disabled_without_centrifugo(api: Api) -> None:
    assert api.call("GET", "/realtime/connection", as_="p_a1")[1] == {"enabled": False}


def test_connection_token_lists_only_allowed_channels(make_api: ApiFactory) -> None:
    centrifugo = CentrifugoRealtime(
        api_url="http://centrifugo:8000/api",
        api_key="api-key",
        token_secret=SECRET,
        public_url="wss://onco-core.ru/connection/websocket",
    )
    api = make_api(realtime=centrifugo)

    _, patient = api.call("GET", "/realtime/connection", as_="p_a1")
    claims = jwt.decode(patient["token"], SECRET, algorithms=["HS256"])
    assert patient["url"] == "wss://onco-core.ru/connection/websocket"
    assert (claims["sub"], claims["channels"]) == ("p_a1", ["chat:p_a1"])

    _, doctor = api.call("GET", "/realtime/connection", as_="doc_a")
    channels = jwt.decode(doctor["token"], SECRET, algorithms=["HS256"])["channels"]
    assert "queue:doc_a" in channels
    assert {c for c in channels if c.startswith("chat:")} == {f"chat:p_a{i}" for i in range(1, 7)}

    assert api.call("GET", "/realtime/connection", as_="adm_1")[0] == 403
