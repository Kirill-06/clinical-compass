"""Сводка пациента в формате HL7 FHIR R4 (Bundle) для передачи в МИС.

FHIR — общий язык обмена для ЕМИАС, 1С:Медицина и других МИС: одна выгрузка
вместо отдельного формата для каждой системы. Коды шкал — LOINC; собственные
коды сервиса — в пространстве `urn:clinical-compass:*`.
"""

from typing import Any

from clinical_compass.db.models import AlertRow, PatientRow
from clinical_compass.domain.enums import AlertStatus, Instrument
from clinical_compass.domain.state import QuestionnaireResponse
from clinical_compass.services.context import Deps
from clinical_compass.services.errors import NotFoundError
from clinical_compass.services.presenter import Json, Presenter, iso

LOINC = "http://loinc.org"
OBSERVATION_CATEGORY = "http://terminology.hl7.org/CodeSystem/observation-category"
_SCORE_CODES = {
    Instrument.GAD7: ("70274-6", "Generalized anxiety disorder 7 item (GAD-7) total score"),
    Instrument.PHQ9: ("44261-6", "Patient Health Questionnaire 9 item (PHQ-9) total score"),
}
_NS = "urn:clinical-compass"
ADHERENCE_WINDOW_DAYS = 14


class FhirSummaryBuilder:
    def __init__(self, deps: Deps) -> None:
        self._d = deps
        self._present = Presenter(deps)

    def bundle(self, patient_id: str) -> Json:
        patient = self._d.repos.people.patient(patient_id)
        if patient is None:
            raise NotFoundError("Пациент не найден")
        subject = {"reference": f"Patient/{patient.id}"}
        resources: list[Json] = [self._patient(patient)]
        resources += [
            self._score(q, subject)
            for q in self._d.repos.facts.questionnaires(patient_id)
            if q.total_score is not None
        ]
        if (adherence := self._adherence(patient_id, subject)) is not None:
            resources.append(adherence)
        open_alerts = [
            a for a in self._d.repos.alerts.for_patient(patient_id) if AlertStatus(a.status).is_open
        ]
        resources += [self._flag(a, subject) for a in open_alerts]
        return {
            "resourceType": "Bundle",
            "type": "collection",
            "timestamp": iso(self._d.clock.now()),
            "meta": {"tag": [{"system": f"{_NS}:schema", "code": "patient_state_v0.2"}]},
            "entry": [{"fullUrl": f"{_NS}:{r['resourceType']}/{r['id']}", "resource": r} for r in resources],
        }

    def _patient(self, p: PatientRow) -> Json:
        identifiers = [{"system": f"{_NS}:patient", "value": p.display_id}] + [
            {"system": f"{_NS}:{i.system}:patient", "value": i.external_id}
            for i in self._d.repos.integrations.identities_of(p.id)
        ]
        resource: dict[str, Any] = {
            "resourceType": "Patient",
            "id": p.id,
            "identifier": identifiers,
            "name": [{"text": p.full_name}],
        }
        if p.sex in ("female", "male"):
            resource["gender"] = p.sex
        return resource

    def _score(self, q: QuestionnaireResponse, subject: Json) -> Json:
        code, display = _SCORE_CODES[q.instrument]
        definition = self._d.contracts.instruments[q.instrument]
        assert q.total_score is not None
        resource: dict[str, Any] = {
            "resourceType": "Observation",
            "id": q.id,
            "status": "final",
            "category": [{"coding": [{"system": OBSERVATION_CATEGORY, "code": "survey"}]}],
            "code": {
                "coding": [{"system": LOINC, "code": code, "display": display}],
                "text": definition.label,
            },
            "subject": subject,
            "effectiveDateTime": iso(q.administered_at),
            "valueInteger": q.total_score,
            "interpretation": [{"text": definition.band_for(q.total_score).label}],
            "note": [{"text": "Скрининг, не диагноз. Оценку проводит врач."}],
        }  # fmt: skip
        if q.delta_from_previous is not None:
            resource["component"] = [
                {
                    "code": {"text": "Изменение от предыдущего (текущий − предыдущий)"},
                    "valueInteger": q.delta_from_previous,
                }
            ]
        return resource

    def _adherence(self, patient_id: str, subject: Json) -> Json | None:
        adherence = self._present.adherence(patient_id, ADHERENCE_WINDOW_DAYS)
        if adherence is None or adherence.ratio is None:
            return None
        return {
            "resourceType": "Observation",
            "id": f"adherence-{patient_id}-{ADHERENCE_WINDOW_DAYS}d",
            "status": "final",
            "code": {
                "coding": [{"system": f"{_NS}:observation", "code": f"adherence-{ADHERENCE_WINDOW_DAYS}d"}],
                "text": f"Доля принятых доз за {ADHERENCE_WINDOW_DAYS} дней",
            },
            "subject": subject,
            "effectiveDateTime": iso(self._d.clock.now()),
            "valueQuantity": {"value": round(adherence.ratio * 100), "unit": "%"},
            "note": [
                {
                    "text": f"Принято {adherence.taken}, пропущено {adherence.missed}, "
                    f"без отметки {adherence.unknown}"
                }
            ],
        }

    def _flag(self, alert: AlertRow, subject: Json) -> Json:
        return {
            "resourceType": "Flag",
            "id": alert.id,
            "status": "active",
            "code": {
                "coding": [{"system": f"{_NS}:rule", "code": alert.rule_id}],
                "text": self._d.contracts.rule_title(alert.rule_id),
            },
            "subject": subject,
            "period": {"start": iso(alert.created_at)},
            "extension": [{"url": f"{_NS}:doctor-priority", "valueCode": alert.doctor_priority}],
        }
