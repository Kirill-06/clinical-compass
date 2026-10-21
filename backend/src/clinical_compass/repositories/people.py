"""Врачи, пациенты, администраторы, связи врач–пациент и сессии."""

from datetime import datetime

from sqlalchemy import ColumnElement, or_, select
from sqlalchemy.orm import Session

from clinical_compass.db.models import AdminRow, DoctorPatientLinkRow, DoctorRow, PatientRow, SessionRow


class PeopleRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def patient(self, patient_id: str) -> PatientRow | None:
        return self._s.get(PatientRow, patient_id)

    def doctor(self, doctor_id: str) -> DoctorRow | None:
        return self._s.get(DoctorRow, doctor_id)

    def admin(self, admin_id: str) -> AdminRow | None:
        return self._s.get(AdminRow, admin_id)

    def all_patients(self) -> list[PatientRow]:
        return list(self._s.scalars(select(PatientRow).order_by(PatientRow.display_id)))

    def all_doctors(self) -> list[DoctorRow]:
        return list(self._s.scalars(select(DoctorRow).order_by(DoctorRow.full_name)))

    def all_admins(self) -> list[AdminRow]:
        return list(self._s.scalars(select(AdminRow).order_by(AdminRow.full_name)))

    def doctor_of(self, patient_id: str, now: datetime) -> str | None:
        """Ведущий врач по активной связи DoctorPatientLink."""
        stmt = (
            select(DoctorPatientLinkRow.doctor_id)
            .where(DoctorPatientLinkRow.patient_id == patient_id, *self._active(now))
            .order_by(DoctorPatientLinkRow.active_from.desc())
        )
        return self._s.scalars(stmt).first()

    def patient_ids_of(self, doctor_id: str, now: datetime) -> list[str]:
        stmt = select(DoctorPatientLinkRow.patient_id).where(
            DoctorPatientLinkRow.doctor_id == doctor_id, *self._active(now)
        )
        return list(self._s.scalars(stmt))

    @staticmethod
    def _active(now: datetime) -> tuple[ColumnElement[bool], ...]:
        return (
            DoctorPatientLinkRow.active_from <= now,
            or_(DoctorPatientLinkRow.active_to.is_(None), DoctorPatientLinkRow.active_to > now),
        )

    def add(self, *rows: object) -> None:
        """Строки записываются в переданном порядке: родитель раньше дочерних (связей ORM нет)."""
        for row in rows:
            self._s.add(row)
            self._s.flush()

    # ------------------------------------------------------------ sessions

    def add_session(self, row: SessionRow) -> None:
        self._s.add(row)

    def session_by_hash(self, token_hash: str) -> SessionRow | None:
        return self._s.get(SessionRow, token_hash)
