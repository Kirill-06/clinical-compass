"""Сбои AI-слоя не теряют сообщение пациента и не скрывают красные флаги (§21)."""

from datetime import datetime

import pytest

from clinical_compass.domain.extraction import FreeTextExtraction
from clinical_compass.domain.remote_extraction import RemoteExtractionError
from clinical_compass.services.patients import PatientService
from conftest import ApiFactory, find_alert, rule_ids

RED_FLAG = "Последние дни не хочу жить"


class UnavailableExtractor:
    """Удалённый AI недоступен: таймаут, обрыв, лимиты провайдера."""

    def extract(
        self, *, message_id: str, patient_id: str, timestamp: datetime, text: str
    ) -> FreeTextExtraction:
        raise RemoteExtractionError("AI extractor request failed: connection refused")


class MalformedDoseExtractor:
    """Ответ проходит схему FreeTextExtraction, но доза пришла строкой."""

    def extract(
        self, *, message_id: str, patient_id: str, timestamp: datetime, text: str
    ) -> FreeTextExtraction:
        return FreeTextExtraction.model_validate(
            {
                "message_id": message_id,
                "patient_id": patient_id,
                "timestamp": timestamp.isoformat(),
                "channel": "chat",
                "original_text": text,
                "model_version": "test-llm",
                "entities": [
                    {
                        "type": "medication",
                        "polarity": "present",
                        "experiencer": "patient",
                        "temporality": "recent_past",
                        "value": {
                            "slot": "morning",
                            "status": "missed",
                            "slot_date": "2026-10-21",
                            "dose_mg": "50 мг",
                        },
                        "evidence_span": {"start": 0, "end": len(text), "text": text},
                    }
                ],
            }
        )


def _messages(api_messages: list[dict[str, object]], text: str) -> list[dict[str, object]]:
    return [m for m in api_messages if m["text"] == text]


def test_malformed_ai_value_keeps_the_message_and_the_valid_fact(make_api: ApiFactory) -> None:
    api = make_api(extractor=MalformedDoseExtractor())
    text = "сегодня утром не выпил таблетку 50 мг"
    status, body = api.call("POST", "/patients/p_a1/messages", as_="p_a1", body={"text": text})
    assert status == 201
    assert body["message"]["extraction_status"] == "extracted"
    _, dossier = api.call("GET", "/doctor/patients/p_a1/timeline", as_="doc_a")
    assert _messages(dossier["messages"], text)
    _, state = api.call("GET", "/patients/p_a1/state", as_="doc_a")
    extracted = [i for i in state["patient_state"]["medication_intakes"] if i["source"] == "text_llm"]
    assert [(i["slot_date"], i["status"], i.get("dose_mg")) for i in extracted] == [
        ("2026-10-21", "missed", None)
    ]


def test_failure_while_saving_extracted_facts_keeps_the_message(
    make_api: ApiFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken_ingest(*_args: object, **_kwargs: object) -> None:
        raise ValueError("unexpected extraction shape")

    monkeypatch.setattr(PatientService, "ingest_extraction", broken_ingest)
    api = make_api()
    text = "Немного кружится голова"
    status, body = api.call("POST", "/patients/p_a1/messages", as_="p_a1", body={"text": text})
    assert status == 201
    assert body["message"]["extraction_status"] == "failed"
    _, dossier = api.call("GET", "/doctor/patients/p_a1/timeline", as_="doc_a")
    assert _messages(dossier["messages"], text)


def test_ai_outage_still_raises_red_flags_through_the_safety_lexicon(make_api: ApiFactory) -> None:
    api = make_api(extractor=UnavailableExtractor())
    status, body = api.call("POST", "/patients/p_a1/messages", as_="p_a1", body={"text": RED_FLAG})
    assert status == 201
    # Врач видит, что ИИ не обработал сообщение, но красный флаг не теряется.
    assert body["message"]["extraction_status"] == "failed"
    assert "recommend_ambulance" in [n["patient_action"] for n in body["patient_notices"]]
    alert = find_alert(api.queue("doc_a"), "R_SELF_HARM", "p_a1")
    assert alert["alert"]["doctor_priority"] == "urgent"


def test_ai_outage_without_red_flags_creates_no_alerts(make_api: ApiFactory) -> None:
    api = make_api(extractor=UnavailableExtractor())
    before = rule_ids(api.queue("doc_a"), "p_a1")
    status, body = api.call(
        "POST", "/patients/p_a1/messages", as_="p_a1", body={"text": "Сплю лучше, спасибо"}
    )
    assert status == 201
    assert body["message"]["extraction_status"] == "failed"
    assert body["patient_notices"] == []
    assert rule_ids(api.queue("doc_a"), "p_a1") == before
