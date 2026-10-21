"""Назначения врача: план приёма, расписание опросников, клинический профиль, маршрутизация."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from clinical_compass.db.models import (
    ClinicalProfileRow,
    MedicationPlanRow,
    QuestionnaireScheduleRow,
    RoutingDecisionRow,
)
from clinical_compass.domain.enums import Instrument
from clinical_compass.domain.state import QuestionnaireSchedule, RoutingDecision


class CareRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def active_plan(self, patient_id: str) -> MedicationPlanRow | None:
        stmt = (
            select(MedicationPlanRow)
            .where(MedicationPlanRow.patient_id == patient_id, MedicationPlanRow.active.is_(True))
            .order_by(MedicationPlanRow.start_date.desc())
        )
        return self._s.scalars(stmt).first()

    def schedule(self, patient_id: str, instrument: Instrument) -> QuestionnaireSchedule | None:
        row = self._s.get(QuestionnaireScheduleRow, (patient_id, instrument.value))
        if row is None:
            return None
        return QuestionnaireSchedule(
            instrument=Instrument(row.instrument),
            interval_days=row.interval_days,
            configured_by=row.configured_by,
            active=row.active,
        )

    def save_schedule(self, patient_id: str, schedule: QuestionnaireSchedule, now: datetime) -> None:
        row = self._s.get(QuestionnaireScheduleRow, (patient_id, schedule.instrument.value))
        if row is None:
            row = QuestionnaireScheduleRow(patient_id=patient_id, instrument=schedule.instrument.value)
            self._s.add(row)
        row.interval_days = schedule.interval_days
        row.configured_by = schedule.configured_by
        row.active = schedule.active
        row.updated_at = now

    def route_review_needed(self, patient_id: str) -> bool:
        row = self._s.get(ClinicalProfileRow, patient_id)
        return bool(row and row.route_review_needed)

    def set_route_review_needed(self, patient_id: str, value: bool, now: datetime) -> None:
        row = self._s.get(ClinicalProfileRow, patient_id)
        if row is None:
            row = ClinicalProfileRow(patient_id=patient_id)
            self._s.add(row)
        row.route_review_needed = value
        row.updated_at = now

    def routing(self, patient_id: str) -> RoutingDecision:
        row = self._s.get(RoutingDecisionRow, patient_id)
        if row is None:
            return RoutingDecision()
        return RoutingDecision.model_validate(
            {
                "system_recommendation": row.system_recommendation,
                "doctor_decision": row.doctor_decision,
                "patient_visible": row.patient_visible,
                "confirmed_at": row.confirmed_at,
            }
        )

    def save_routing(
        self, patient_id: str, routing: RoutingDecision, confirmed_by: str | None = None
    ) -> None:
        row = self._s.get(RoutingDecisionRow, patient_id)
        if row is None:
            row = RoutingDecisionRow(patient_id=patient_id)
            self._s.add(row)
        row.system_recommendation = routing.system_recommendation
        row.doctor_decision = routing.doctor_decision.value
        row.patient_visible = routing.patient_visible
        row.confirmed_at = routing.confirmed_at
        if confirmed_by is not None:
            row.confirmed_by = confirmed_by
