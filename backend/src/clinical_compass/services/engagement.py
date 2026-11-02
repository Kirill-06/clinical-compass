"""Агрегация уже записанных пациентом действий; без новой БД и без побочных эффектов."""

from datetime import date, datetime, timedelta
from typing import Any

from clinical_compass.domain.engagement import weekly_engagement
from clinical_compass.domain.enums import CompletionStatus, FactSource
from clinical_compass.services.context import Deps


def engagement_for_patient(deps: Deps, patient_id: str) -> dict[str, Any]:
    offset = timedelta(hours=deps.clock.utc_offset_hours)

    def local_date(moment: datetime) -> date:
        return (moment + offset).date()

    dates = [
        local_date(q.administered_at)
        for q in deps.repos.facts.questionnaires(patient_id)
        if q.source is FactSource.FORM and q.completion_status is CompletionStatus.COMPLETE
    ]
    dates.extend(
        intake.slot_date
        for intake in deps.repos.facts.intakes(patient_id)
        if intake.source is FactSource.FORM
    )
    dates.extend(
        local_date(row.reported_at)
        for symptom, row in deps.repos.facts.symptoms(patient_id)
        if symptom.source is FactSource.FORM
    )
    return weekly_engagement(today=deps.clock.today(), record_dates=dates)
