"""Regression coverage for free form 'other' symptoms."""

from datetime import datetime

import pytest

from clinical_compass.domain.extraction import ExtractedEntity, FreeTextExtraction
from clinical_compass.domain.remote_extraction import RemoteExtractionError
from clinical_compass.domain.state import EvidenceSpan
from conftest import Api, ApiFactory, find_alert, rule_ids

SELF_HARM = "Последние дни не хочу жить"
MIXED = "Я выпила всю пачку таблеток, забеременела, и меня посещают суицидальные мысли"


def report(api: Api, phrase: str) -> dict:
    status, body = api.call("POST", "/patients/p_a1/symptoms", as_="p_a1", body={
        "normalized_type": "other_unlisted", "patient_phrase": phrase,
    })
    assert status == 201
    assert body["symptom"]["normalized_type"] == "other_unlisted"
    return body


def state(api: Api) -> dict:
    status, body = api.call("GET", "/patients/p_a1/state", as_="doc_a")
    assert status == 200
    return body["patient_state"]


def test_benign_other_text_stays_out_of_scope(api: Api) -> None:
    body = report(api, "У меня странное ощущение в руках")
    assert [n["template"]["id"] for n in body["patient_notices"]] == ["out_of_scope_v1"]
    assert state(api)["risk_signals"] == []
    assert "R_OUT_OF_SCOPE" in rule_ids(api.queue("doc_a"), "p_a1")


def test_other_text_self_harm_is_urgent(api: Api) -> None:
    body = report(api, SELF_HARM)
    assert {r["type"] for r in state(api)["risk_signals"]} == {"self_harm_or_suicidal"}
    assert find_alert(api.queue("doc_a"), "R_SELF_HARM", "p_a1")["alert"]["doctor_priority"] == "urgent"
    assert "recommend_ambulance" in {n["patient_action"] for n in body["patient_notices"]}
    assert "R_OUT_OF_SCOPE" in rule_ids(api.queue("doc_a"), "p_a1")


def test_mixed_critical_text_extracts_all_risks(api: Api) -> None:
    body = report(api, MIXED)
    assert {r["type"] for r in state(api)["risk_signals"]} == {
        "possible_overdose", "pregnancy_or_lactation", "self_harm_or_suicidal",
    }
    assert find_alert(api.queue("doc_a"), "R_SELF_HARM", "p_a1")["alert"]["doctor_priority"] == "urgent"
    assert find_alert(api.queue("doc_a"), "R_OVERDOSE", "p_a1")["alert"]["doctor_priority"] == "urgent"
    assert "recommend_ambulance" in {n["patient_action"] for n in body["patient_notices"]}


@pytest.mark.parametrize(
    ("phrase", "risk_type"),
    [
        ("Я не беременна", "pregnancy_or_lactation"),
        ("Я не выпила всю пачку таблеток", "possible_overdose"),
    ],
)
def test_negated_other_text_has_no_risk_signal(api: Api, phrase: str, risk_type: str) -> None:
    body = report(api, phrase)
    patient_state = state(api)
    assert any(s["patient_phrase"] == phrase for s in patient_state["symptoms"])
    assert risk_type not in {r["type"] for r in patient_state["risk_signals"]}
    assert "recommend_ambulance" not in {n["patient_action"] for n in body["patient_notices"]}


class UnavailableExtractor:
    def extract(
        self, *, message_id: str, patient_id: str, timestamp: datetime, text: str
    ) -> FreeTextExtraction:
        raise RemoteExtractionError("AI unavailable")


def test_remote_failure_keeps_other_symptom_and_uses_safety_net(make_api: ApiFactory) -> None:
    api = make_api(extractor=UnavailableExtractor())
    body = report(api, SELF_HARM)
    assert any(s["patient_phrase"] == SELF_HARM for s in state(api)["symptoms"])
    assert {r["type"] for r in state(api)["risk_signals"]} == {"self_harm_or_suicidal"}
    assert find_alert(api.queue("doc_a"), "R_SELF_HARM", "p_a1")["alert"]["doctor_priority"] == "urgent"
    assert "recommend_ambulance" in {n["patient_action"] for n in body["patient_notices"]}


class MixedEntityExtractor:
    def extract(
        self, *, message_id: str, patient_id: str, timestamp: datetime, text: str
    ) -> FreeTextExtraction:
        def entity(kind: str, value: dict[str, str]) -> ExtractedEntity:
            return ExtractedEntity.model_validate({
                "type": kind, "value": value,
                "evidence_span": EvidenceSpan(start=0, end=len(text), text=text),
                "polarity": "present", "experiencer": "patient", "temporality": "current",
            })

        return FreeTextExtraction(
            message_id=message_id, patient_id=patient_id, timestamp=timestamp,
            original_text=text, model_version="test-llm", entities=(
                entity("risk_signal", {"type": "self_harm_or_suicidal"}),
                entity("symptom", {"normalized_type": "dizziness"}),
                entity("medication", {"slot": "morning", "status": "missed", "slot_date": "2026-10-21"}),
                entity("lab_mention", {"analyte": "hemoglobin"}),
            ),
        )


def test_other_text_ignores_non_risk_ai_entities(make_api: ApiFactory) -> None:
    api = make_api(extractor=MixedEntityExtractor())
    report(api, SELF_HARM)
    patient_state = state(api)
    assert {s["normalized_type"] for s in patient_state["symptoms"]} == {"other_unlisted"}
    assert not any(i["source"] == "text_llm" for i in patient_state["medication_intakes"])
    assert not any(lab["source"] == "text_llm" for lab in patient_state["labs"])
    assert {r["type"] for r in patient_state["risk_signals"]} == {"self_harm_or_suicidal"}
