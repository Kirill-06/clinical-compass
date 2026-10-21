"""Граница AI-слоя (§16, §19): извлечение, чистая оценка правил, приём фактов.

Эндпоинты защищены служебным ключом и не доступны пользователям.
"""

from typing import Any

from clinical_compass import SCHEMA_VERSION
from clinical_compass.domain.enums import Role
from clinical_compass.domain.extraction import FreeTextExtraction
from clinical_compass.domain.rules import RuleContext, RuleEngine
from clinical_compass.domain.state import PatientState
from clinical_compass.services.access import AccessPolicy
from clinical_compass.services.context import Deps, Principal, new_id
from clinical_compass.services.errors import InvalidInputError
from clinical_compass.services.patients import PatientService
from clinical_compass.services.presenter import Json, Presenter
from clinical_compass.services.state import PatientStateService

AI_LAYER = Principal(user_id="system:ai", role=Role.ADMIN, name="AI-слой")
PROFILE = Principal(user_id="system:profile", role=Role.ADMIN, name="Клинический профиль")


class InternalService:
    def __init__(self, deps: Deps) -> None:
        self._d = deps
        self._access = AccessPolicy(deps)
        self._state = PatientStateService(deps)
        self._present = Presenter(deps)

    def extract(self, patient_id: str, text: str) -> Json:
        self._access.patient(patient_id)
        extraction = self._d.extractor.extract(
            message_id=new_id("ext"), patient_id=patient_id, timestamp=self._d.clock.now(), text=text
        )
        return extraction.model_dump(mode="json")

    def evaluate_rules(self, document: dict[str, Any], context: RuleContext) -> list[Json]:
        """Чистая функция: Patient State по схеме v0.2 → RuleResult[]. Ничего не сохраняет."""
        errors = self._d.contracts.schema_errors(document)
        if errors:
            raise InvalidInputError(f"Patient State не соответствует схеме v0.2: {errors[0]}")
        state = PatientState.from_schema(document)
        return [r.to_json() for r in RuleEngine(self._d.contracts.rules).evaluate(state, context)]

    def ingest_facts(self, patient_id: str, body: dict[str, Any]) -> Json:
        """Принять FreeTextExtraction или фрагмент Patient State (symptoms / risk_signals / labs)."""
        self._access.patient(patient_id)
        if "extraction" in body:
            extraction = FreeTextExtraction.model_validate(body["extraction"])
            if extraction.patient_id != patient_id:
                raise InvalidInputError("patient_id извлечения не совпадает")
            PatientService(self._d).ingest_extraction(patient_id, extraction, AI_LAYER)
        else:
            fragment = {
                "schema_version": SCHEMA_VERSION,
                "patient_id": patient_id,
                "updated_at": self._d.clock.now().isoformat(),
                "symptoms": body.get("symptoms", []),
                "risk_signals": body.get("risk_signals", []),
                "labs": body.get("labs", []),
            }
            errors = self._d.contracts.schema_errors(fragment)
            if errors:
                raise InvalidInputError(f"Факты не соответствуют схеме v0.2: {errors[0]}")
            state = PatientState.from_schema(fragment)
            facts = self._d.repos.facts
            for symptom in state.symptoms:
                facts.add_symptom(patient_id, symptom, self._d.clock.now())
                self._d.audit(AI_LAYER, "symptom.ingested", "symptom", symptom.id, patient_id)
            for signal in state.risk_signals:
                facts.add_risk_signal(patient_id, signal)
                self._d.audit(AI_LAYER, "risk_signal.ingested", "risk_signal", signal.id, patient_id)
            for lab in state.labs:
                facts.add_lab(patient_id, lab)
                self._d.audit(AI_LAYER, "lab.ingested", "lab", lab.id, patient_id)
        alerts = self._state.evaluate(patient_id, AI_LAYER)
        return {"alerts": [self._present.alert(a) for a in alerts]}

    def set_clinical_profile(self, patient_id: str, *, route_review_needed: bool) -> Json:
        self._access.patient(patient_id)
        self._d.repos.care.set_route_review_needed(patient_id, route_review_needed, self._d.clock.now())
        self._d.audit(PROFILE, "profile.updated", "profile", patient_id, patient_id)
        alerts = self._state.evaluate(patient_id, PROFILE)
        return {"alerts": [self._present.alert(a) for a in alerts]}
