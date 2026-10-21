"""Проверка доступа (§3). Выполняется на сервере в каждом сценарии.

Пациент — только свои данные; врач — только закреплённые пациенты
(активная DoctorPatientLink); администратор — только задачи на запись.
"""

from clinical_compass.db.models import PatientRow
from clinical_compass.domain.enums import Role
from clinical_compass.services.context import Deps, Principal
from clinical_compass.services.errors import ForbiddenError, NotFoundError


class AccessPolicy:
    def __init__(self, deps: Deps) -> None:
        self._d = deps

    def patient(self, patient_id: str) -> PatientRow:
        row = self._d.repos.people.patient(patient_id)
        if row is None:
            raise NotFoundError("Пациент не найден")
        return row

    def doctor_of(self, patient_id: str) -> str | None:
        return self._d.repos.people.doctor_of(patient_id, self._d.clock.now())

    def require_role(self, principal: Principal, role: Role, message: str) -> None:
        if principal.role is not role:
            raise ForbiddenError(message)

    def require_self(self, principal: Principal, patient_id: str) -> PatientRow:
        row = self.patient(patient_id)
        if principal.role is not Role.PATIENT or principal.user_id != patient_id:
            raise ForbiddenError("Нет доступа к этим данным")
        return row

    def require_doctor_for(self, principal: Principal, patient_id: str) -> PatientRow:
        row = self.patient(patient_id)
        if principal.role is not Role.DOCTOR or self.doctor_of(patient_id) != principal.user_id:
            raise ForbiddenError("Пациент не закреплён за вами")
        return row

    def require_read(self, principal: Principal, patient_id: str) -> PatientRow:
        if principal.role is Role.PATIENT:
            return self.require_self(principal, patient_id)
        if principal.role is Role.DOCTOR:
            return self.require_doctor_for(principal, patient_id)
        raise ForbiddenError("Администратор не видит клинические данные")

    def doctor_patient_ids(self, principal: Principal) -> list[str]:
        self.require_role(principal, Role.DOCTOR, "Раздел доступен врачу")
        return self._d.repos.people.patient_ids_of(principal.user_id, self._d.clock.now())
