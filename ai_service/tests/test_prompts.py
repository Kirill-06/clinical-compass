import json

import pytest

from clinical_compass_ai.extractor import extract
from clinical_compass_ai.prompts import PROMPT_VERSION, SYSTEM_PROMPT
from clinical_compass_ai.schemas import ExtractRequest, ModelOutput


class FakeProvider:
    def __init__(self, entities):
        self.payload = json.dumps({"entities": entities, "unknown_fields": []}, ensure_ascii=False)
        self.calls = 0

    def complete(self, text, repair_error=None):
        self.calls += 1
        return self.payload


def entity(kind, text, evidence, **fields):
    start = text.index(evidence)
    return {
        "entity_type": kind,
        "evidence_span": {"text": evidence, "start": start, "end": start + len(evidence)},
        **fields,
    }


def extract_with_fake(text, *entities):
    provider = FakeProvider(entities)
    request = ExtractRequest(
        message_id="prompt-case", patient_id="patient-1", timestamp="2026-10-22T12:00:00Z", text=text
    )
    output = extract(request, provider, "fake")
    assert provider.calls == 1
    assert output.model_version == "fake:extractor_prompt_v1.2"
    return output


def test_prompt_contract_and_safety_instructions():
    prompt = SYSTEM_PROMPT.lower()
    assert PROMPT_VERSION == "extractor_prompt_v1.2"
    assert "one json object" in prompt
    assert '"entities"' in prompt and '"unknown_fields"' in prompt
    assert "annotation_v0.2" in prompt
    assert "possible_allergic_reaction" in prompt
    assert "swollen lips" in prompt and "breathing difficulty" in prompt
    assert "need not call it an allergy" in prompt
    assert "not apply this type to every medication side effect" in prompt
    assert "risk_signal even when symptom or medication entities are also present" in prompt
    assert "do not diagnose" in prompt


def test_prompt_medication_symptom_and_duplicate_instructions():
    prompt = SYSTEM_PROMPT.lower()
    for reason in ("adverse_event", "felt_unwell", "forgot", "decided_to_stop", "unknown"):
        assert reason in prompt
    assert "do not infer a reason" in prompt
    assert 'drug="unknown"' in prompt
    assert 'word "tablet" as a drug name' in prompt
    assert "most specific canonical normalized_type" in prompt
    assert "explicit negation" in prompt and "other-person experiencer" in prompt
    assert "recent_past/earlier" in prompt and "hypothetical wording" in prompt
    assert "overlapping evidence spans" in prompt
    assert "genuinely different facts" in prompt


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("Не выпил таблетку: от неё вчера кружилась голова.", "adverse_event"),
        ("Пропустил таблетку, потому что плохо себя чувствовал.", "felt_unwell"),
    ],
)
def test_fake_provider_missed_reason_without_optional_drug(text, reason):
    item = entity("medication", text, text, status="missed", slot="unknown", missed_reason=reason)
    assert "drug" not in item and "dose_mg" not in item
    ModelOutput.model_validate_json(json.dumps({"entities": [item], "unknown_fields": []}))
    extracted = extract_with_fake(text, item).entities[0]
    assert extracted.value["missed_reason"] == reason
    assert "drug" not in extracted.value and "dose_mg" not in extracted.value


def test_fake_provider_allergy_risk_and_distinct_symptom_survive_json_contract():
    text = "После таблетки отекли губы и стало трудно дышать."
    risk = entity("risk_signal", text, "отекли губы и стало трудно дышать", type="possible_allergic_reaction")
    symptom = entity(
        "symptom",
        text,
        "стало трудно дышать",
        normalized_type="other_unlisted",
        polarity="present",
        experiencer="patient",
        temporality="current",
    )
    output = extract_with_fake(text, risk, symptom)
    assert [item.type for item in output.entities] == ["risk_signal", "symptom"]
    assert output.entities[0].value["type"] == "possible_allergic_reaction"
    assert output.entities[1].value["normalized_type"] == "other_unlisted"


def test_fake_provider_one_symptom_fact_and_distinct_second_fact():
    text = "Болит голова и тошнит."
    headache = entity(
        "symptom",
        text,
        "Болит голова",
        normalized_type="headache",
        polarity="present",
        experiencer="patient",
        temporality="current",
    )
    nausea = entity(
        "symptom",
        text,
        "тошнит",
        normalized_type="nausea",
        polarity="present",
        experiencer="patient",
        temporality="current",
    )
    output = extract_with_fake(text, headache, nausea)
    assert [item.value["normalized_type"] for item in output.entities] == ["headache", "nausea"]
