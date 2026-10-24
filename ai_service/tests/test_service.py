import asyncio
import json
from datetime import UTC, datetime

import httpx
import pytest

from clinical_compass.domain.remote_extraction import RemoteHTTPExtractor
from clinical_compass.evaluation import evaluate_extractor, write_eval_outputs
from clinical_compass_ai.config import Settings
from clinical_compass_ai.main import create_app


class FakeProvider:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = 0

    def complete(self, text, repair_error=None):
        self.calls += 1
        return next(self.responses)


def post(app, path, body=None):
    async def call():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            if body is None:
                return await client.get(path)
            return await client.post(path, json=body)

    return asyncio.run(call())


def request(text):
    return {
        "message_id": "gen_001",
        "patient_id": "patient-1",
        "timestamp": "2026-10-22T12:00:00Z",
        "text": text,
    }


def entity(kind, text, evidence, **fields):
    start = text.index(evidence)
    return {
        "entity_type": kind,
        "evidence_span": {"text": evidence, "start": start, "end": start + len(evidence)},
        **fields,
    }


def result(text, *entities):
    provider = FakeProvider([json.dumps({"entities": entities, "unknown_fields": []})])
    response = post(create_app(provider=provider, settings=Settings(model="test")), "/extract", request(text))
    assert response.status_code == 200, response.text
    assert provider.calls == 1
    return response.json()["entities"]


@pytest.mark.parametrize(
    ("text", "evidence", "polarity", "experiencer", "temporality", "normalized"),
    [
        ("Болит голова", "Болит голова", "present", "patient", "current", "headache"),
        ("Голова не болит", "Голова не болит", "absent", "patient", "current", "headache"),
        ("Кажется, болит голова", "Кажется, болит голова", "uncertain", "patient", "current", "headache"),
        ("У мамы болит голова", "У мамы болит голова", "present", "other", "current", "headache"),
        ("Если заболит голова", "Если заболит голова", "present", "patient", "hypothetical", "headache"),
        ("Болит колено", "Болит колено", "present", "patient", "current", "other_unlisted"),
    ],
)
def test_symptom(text, evidence, polarity, experiencer, temporality, normalized):
    items = result(
        text,
        entity(
            "symptom",
            text,
            evidence,
            normalized_type=normalized,
            polarity=polarity,
            experiencer=experiencer,
            temporality=temporality,
        ),
    )
    assert items[0]["value"]["normalized_type"] == normalized
    assert items[0]["polarity"] == polarity
    assert items[0]["experiencer"] == experiencer
    assert items[0]["temporality"] == temporality


def test_medication_evening_and_adverse_event():
    text = "Вечером пропустила таблетку из-за тошноты"
    items = result(
        text,
        entity("medication", text, text, status="missed", slot="evening", missed_reason="adverse_event"),
        entity(
            "symptom",
            text,
            "тошноты",
            normalized_type="nausea",
            polarity="present",
            experiencer="patient",
            temporality="current",
        ),
    )
    assert items[0]["value"]["slot"] == "evening"
    assert items[1]["type"] == "symptom"


def test_unknown_slot():
    text = "Пропустила таблетку"
    assert (
        result(text, entity("medication", text, text, status="missed", slot="unknown"))[0]["value"]["slot"]
        == "unknown"
    )


@pytest.mark.parametrize(
    ("signal", "text"),
    [
        ("self_harm_or_suicidal", "Хочу умереть"),
        ("pregnancy_or_lactation", "Я беременна"),
        ("concomitant_drug_mention", "Принимаю ещё аспирин"),
        ("alcohol_use_mention", "Пила алкоголь"),
    ],
)
def test_risk(signal, text):
    assert result(text, entity("risk_signal", text, text, type=signal))[0]["value"]["type"] == signal


def test_lab():
    text = "Гемоглобин 120 г/л"
    assert (
        result(text, entity("lab_mention", text, text, analyte="hemoglobin", value=120, unit="г/л"))[0][
            "value"
        ]["value"]
        == 120
    )


def test_malformed_and_invalid_evidence():
    for response in [
        "not json",
        json.dumps(
            {"entities": [entity("risk_signal", "abc", "abc", type="other_concern")], "unknown_fields": []}
        ),
    ]:
        provider = FakeProvider([response, response])
        r = post(create_app(provider=provider, settings=Settings(model="test")), "/extract", request("xyz"))
        assert r.status_code == 502
        assert provider.calls == 2


def test_offset_recovery_unique():
    text = "Голова болит"
    item = entity(
        "symptom",
        text,
        text,
        normalized_type="headache",
        polarity="present",
        experiencer="patient",
        temporality="current",
    )
    item["evidence_span"]["start"] = 1
    provider = FakeProvider([json.dumps({"entities": [item]})])
    r = post(create_app(provider=provider, settings=Settings(model="test")), "/extract", request(text))
    assert r.status_code == 200
    assert r.json()["entities"][0]["evidence_span"]["start"] == 0


def test_health_and_configuration():
    app = create_app(settings=Settings(model=None, api_key=None))
    assert post(app, "/health").json() == {"status": "ok"}
    assert post(app, "/extract", request("Болит голова")).status_code == 503


def test_existing_remote_http_extractor(monkeypatch):
    app = create_app(
        provider=FakeProvider(
            [
                json.dumps(
                    {
                        "entities": [
                            entity(
                                "symptom",
                                "Болит голова",
                                "Болит голова",
                                normalized_type="headache",
                                polarity="present",
                                experiencer="patient",
                                temporality="current",
                            )
                        ]
                    }
                )
            ]
        ),
        settings=Settings(model="test"),
    )

    def local_post(url, *, json, headers, timeout):
        return post(app, "/extract", json)

    monkeypatch.setattr(httpx, "post", local_post)
    extraction = RemoteHTTPExtractor("http://test/extract").extract(
        message_id="gen_001",
        patient_id="patient-1",
        timestamp=datetime(2026, 10, 22, tzinfo=UTC),
        text="Болит голова",
    )
    assert extraction.entities[0].value["normalized_type"] == "headache"


def test_existing_evaluator_through_remote_adapter(monkeypatch, tmp_path):
    text = "Болит голова"
    gold = entity(
        "symptom",
        text,
        text,
        normalized_type="headache",
        polarity="present",
        experiencer="patient",
        temporality="current",
    )
    dataset = tmp_path / "annotations.jsonl"
    dataset.write_text(
        json.dumps(
            {"message_id": "gen_001", "text": text, "gold_entities": [gold], "unknown_fields": []},
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    app = create_app(
        provider=FakeProvider([json.dumps({"entities": [gold]})]), settings=Settings(model="test")
    )
    monkeypatch.setattr(httpx, "post", lambda url, *, json, headers, timeout: post(app, "/extract", json))
    evaluation = evaluate_extractor(RemoteHTTPExtractor("http://test/extract"), dataset)
    write_eval_outputs(
        evaluation, metrics_path=tmp_path / "metrics.json", predictions_path=tmp_path / "predictions.jsonl"
    )
    assert (tmp_path / "metrics.json").exists()
    assert '"predicted_entities"' in (tmp_path / "predictions.jsonl").read_text()


@pytest.mark.parametrize(
    ("text", "kind", "fields", "expected"),
    [
        ("Сегодня таблетку не выпил", "medication", {"status": "missed", "slot": "unknown"}, "unknown"),
        (
            "Иногда думаю о самоубийстве",
            "risk_signal",
            {"type": "self_harm_or_suicidal"},
            "self_harm_or_suicidal",
        ),
        (
            "Боюсь, что могу принять слишком много таблеток",
            "risk_signal",
            {"type": "possible_overdose"},
            "possible_overdose",
        ),
        (
            "Гемоглобин 120 г/л",
            "lab_mention",
            {"analyte": "hemoglobin", "value": 120, "unit": "г/л"},
            "hemoglobin",
        ),
    ],
)
def test_annotation_style_non_symptoms_and_transport_defaults(text, kind, fields, expected):
    item = result(text, entity(kind, text, text, **fields))[0]
    assert expected in item["value"].values()
    assert (item["polarity"], item["experiencer"], item["temporality"]) == ("present", "patient", "current")
    assert not {"polarity", "experiencer", "temporality"} & item["value"].keys()


def test_missed_evening_with_dizziness():
    text = "Вчера вечером таблетку не выпил, потому что кружилась голова"
    items = result(
        text,
        entity("medication", text, "Вчера вечером таблетку не выпил", status="missed", slot="evening"),
        entity(
            "symptom",
            text,
            "кружилась голова",
            normalized_type="dizziness",
            polarity="present",
            experiencer="patient",
            temporality="recent_past",
        ),
    )
    assert [item["type"] for item in items] == ["medication", "symptom"]
    assert items[1]["value"]["normalized_type"] == "dizziness"


def test_hypothetical_nausea():
    text = "Боюсь, что начнёт тошнить"
    item = result(
        text,
        entity(
            "symptom",
            text,
            text,
            normalized_type="nausea",
            polarity="present",
            experiencer="patient",
            temporality="hypothetical",
        ),
    )[0]
    assert item["temporality"] == "hypothetical"


@pytest.mark.parametrize(
    "text", ["У мамы мысли о самоубийстве", "Не думаю о самоубийстве", "От смеха умереть можно"]
)
def test_non_actionable_risk_is_not_emitted(text):
    assert result(text) == []


@pytest.mark.parametrize(
    ("kind", "fields"),
    [
        ("medication", {"status": "missed", "slot": "unknown"}),
        ("risk_signal", {"type": "possible_overdose"}),
        ("lab_mention", {"analyte": "hemoglobin", "value": 120, "unit": "г/л"}),
    ],
)
def test_non_symptoms_reject_annotation_modifiers(kind, fields):
    text = "Гемоглобин 120 г/л"
    bad = entity(kind, text, text, polarity="present", **fields)
    provider = FakeProvider([json.dumps({"entities": [bad]}), json.dumps({"entities": [bad]})])
    response = post(create_app(provider=provider, settings=Settings(model="test")), "/extract", request(text))
    assert response.status_code == 502


def _post_with(app, headers):
    async def call():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            return await client.post("/extract", json=request("Болит голова"), headers=headers)

    return asyncio.run(call())


def test_service_token_is_required_when_configured():
    text = "Болит голова"
    symptom = entity(
        "symptom",
        text,
        text,
        normalized_type="headache",
        polarity="present",
        experiencer="patient",
        temporality="current",
    )
    answer = json.dumps({"entities": [symptom], "unknown_fields": []})
    settings = Settings(model="test", service_token="s3cret-service-token")
    app = create_app(provider=FakeProvider([answer, answer]), settings=settings)
    assert _post_with(app, {}).status_code == 401
    assert _post_with(app, {"Authorization": "Bearer wrong"}).status_code == 401
    assert _post_with(app, {"Authorization": "Bearer s3cret-service-token"}).status_code == 200
    # Проверка здоровья не требует токена — её дергают балансировщик и скрипты запуска.
    assert post(app, "/health").status_code == 200
