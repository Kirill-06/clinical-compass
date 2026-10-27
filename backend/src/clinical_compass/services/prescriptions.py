"""Препараты, которые врач выписывает пациенту.

Пациент видит активные назначения списком и может показать его в аптеке. Это не рецепт:
рецептурные препараты отпускаются по рецепту, который врач оформляет отдельно.
Отметки приёма по-прежнему ведутся по плану приёма (`MedicationPlanRow`).
"""

from dataclasses import dataclass

from clinical_compass.db.models import PrescriptionRow
from clinical_compass.services.access import AccessPolicy
from clinical_compass.services.context import Deps, Principal, new_id
from clinical_compass.services.errors import InvalidInputError, NotFoundError
from clinical_compass.services.presenter import Json, Presenter


@dataclass(frozen=True)
class PrescriptionDraft:
    drug: str
    dosage: str
    regimen: str
    duration: str | None = None
    note: str | None = None


def _clean(value: str | None) -> str | None:
    text = " ".join(value.split()) if value else ""
    return text or None


class PrescriptionService:
    def __init__(self, deps: Deps) -> None:
        self._d = deps
        self._access = AccessPolicy(deps)
        self._present = Presenter(deps)

    def for_doctor(self, principal: Principal, patient_id: str) -> list[Json]:
        """Все назначения пациента, включая отменённые."""
        self._access.require_doctor_for(principal, patient_id)
        return self._present.prescriptions(patient_id, active_only=False)

    def prescribe(self, principal: Principal, patient_id: str, draft: PrescriptionDraft) -> Json:
        self._access.require_doctor_for(principal, patient_id)
        drug, dosage, regimen = _clean(draft.drug), _clean(draft.dosage), _clean(draft.regimen)
        if not drug or not dosage or not regimen:
            raise InvalidInputError("Укажите препарат, дозировку и как принимать")
        row = PrescriptionRow(
            id=new_id("rx"),
            patient_id=patient_id,
            doctor_id=principal.user_id,
            drug=drug,
            dosage=dosage,
            regimen=regimen,
            duration=_clean(draft.duration),
            note=draft.note.strip() if draft.note and draft.note.strip() else None,
            created_at=self._d.clock.now(),
            cancelled_at=None,
            cancelled_by=None,
        )
        self._d.repos.care.add_prescription(row)
        self._d.audit(principal, "prescription.created", "prescription", row.id, patient_id)
        return self._present.prescription(row)

    def cancel(self, principal: Principal, prescription_id: str) -> Json:
        row = self._d.repos.care.prescription(prescription_id)
        if row is None:
            raise NotFoundError("Назначение не найдено")
        self._access.require_doctor_for(principal, row.patient_id)
        if row.cancelled_at is None:
            row.cancelled_at = self._d.clock.now()
            row.cancelled_by = principal.user_id
            self._d.audit(principal, "prescription.cancelled", "prescription", row.id, row.patient_id)
        return self._present.prescription(row)
