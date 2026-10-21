"""Экстренные предупреждения пациенту и что пациент с ними сделал.

Сервис не вызывает скорую сам: пациент видит предупреждение и сам нажимает
«Позвонить 112/103» — звонок начинает телефон пациента. Каждое действие
пишется в журнал, и врач видит его в карточке события.
"""

from clinical_compass.domain.enums import AlertStatus, PatientAction, SafetyAction
from clinical_compass.services.access import AccessPolicy
from clinical_compass.services.context import Deps, Principal
from clinical_compass.services.errors import InvalidInputError, NotFoundError
from clinical_compass.services.presenter import SAFETY_AUDIT_PREFIX, Json, iso

EMERGENCY_ACTIONS = frozenset({PatientAction.RECOMMEND_AMBULANCE, PatientAction.CONTACT_CLINIC_TODAY})


class SafetyService:
    def __init__(self, deps: Deps) -> None:
        self._d = deps
        self._access = AccessPolicy(deps)

    def record(self, principal: Principal, patient_id: str, alert_id: str, action: SafetyAction) -> Json:
        self._access.require_self(principal, patient_id)
        alert = self._d.repos.alerts.get(alert_id)
        if alert is None or alert.patient_id != patient_id:
            raise NotFoundError("Предупреждение не найдено")
        if PatientAction(alert.patient_action) not in EMERGENCY_ACTIONS:
            raise InvalidInputError("Это предупреждение не экстренное")
        self._d.audit(principal, f"{SAFETY_AUDIT_PREFIX}{action.value}", "alert", alert.id, patient_id)
        return {"alert_id": alert.id, "action": action.value, "at": iso(self._d.clock.now())}

    def pending_for(self, patient_id: str) -> list[str]:
        """Открытые экстренные предупреждения, которые пациент ещё не закрыл."""
        closed = {
            e.entity_id
            for e in self._d.repos.audit.for_patient(patient_id)
            if e.action == f"{SAFETY_AUDIT_PREFIX}{SafetyAction.DISMISSED.value}"
        }
        return [
            a.id
            for a in self._d.repos.alerts.for_patient(patient_id)
            if PatientAction(a.patient_action) in EMERGENCY_ACTIONS
            and AlertStatus(a.status).is_open
            and a.id not in closed
        ]
