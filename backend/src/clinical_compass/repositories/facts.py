"""Факты Patient State: опросники, приём, симптомы, сигналы, анализы."""

from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from clinical_compass.db.models import (
    LabResultRow,
    MedicationIntakeRow,
    QuestionnaireResponseRow,
    RiskSignalRow,
    SymptomEventRow,
)
from clinical_compass.domain.enums import IntakeSlot
from clinical_compass.domain.state import (
    EvidenceSpan,
    LabResult,
    MedicationIntake,
    QuestionnaireResponse,
    RiskSignal,
    SymptomEvent,
)


class FactsRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    # ------------------------------------------------------------ questionnaires

    def questionnaires(self, patient_id: str) -> list[QuestionnaireResponse]:
        stmt = (
            select(QuestionnaireResponseRow)
            .where(QuestionnaireResponseRow.patient_id == patient_id)
            .order_by(QuestionnaireResponseRow.administered_at)
        )
        return [_questionnaire(r) for r in self._s.scalars(stmt)]

    def questionnaire(self, patient_id: str, fact_id: str) -> QuestionnaireResponse | None:
        row = self._s.get(QuestionnaireResponseRow, fact_id)
        return _questionnaire(row) if row and row.patient_id == patient_id else None

    def add_questionnaire(self, patient_id: str, q: QuestionnaireResponse) -> None:
        self._s.add(QuestionnaireResponseRow(patient_id=patient_id, **q.model_dump()))

    # ------------------------------------------------------------ medication intakes

    def intakes(self, patient_id: str) -> list[MedicationIntake]:
        stmt = select(MedicationIntakeRow).where(MedicationIntakeRow.patient_id == patient_id)
        return [_intake(r) for r in self._s.scalars(stmt)]

    def intake(self, patient_id: str, fact_id: str) -> MedicationIntake | None:
        row = self._s.get(MedicationIntakeRow, fact_id)
        return _intake(row) if row and row.patient_id == patient_id else None

    def intake_for_slot(self, patient_id: str, slot_date: date, slot: IntakeSlot) -> MedicationIntake | None:
        stmt = select(MedicationIntakeRow).where(
            MedicationIntakeRow.patient_id == patient_id,
            MedicationIntakeRow.slot_date == slot_date,
            MedicationIntakeRow.slot == slot.value,
        )
        row = self._s.scalars(stmt).first()
        return _intake(row) if row else None

    def upsert_intake(self, patient_id: str, intake: MedicationIntake) -> None:
        row = self._s.get(MedicationIntakeRow, intake.id)
        values = intake.model_dump()
        if row is None:
            self._s.add(MedicationIntakeRow(patient_id=patient_id, **values))
        else:
            for key, value in values.items():
                setattr(row, key, value)

    # ------------------------------------------------------------ symptoms

    def symptoms(self, patient_id: str) -> list[tuple[SymptomEvent, SymptomEventRow]]:
        stmt = (
            select(SymptomEventRow)
            .where(SymptomEventRow.patient_id == patient_id)
            .order_by(SymptomEventRow.reported_at)
        )
        return [(_symptom(r), r) for r in self._s.scalars(stmt)]

    def symptom(self, patient_id: str, fact_id: str) -> SymptomEvent | None:
        row = self._s.get(SymptomEventRow, fact_id)
        return _symptom(row) if row and row.patient_id == patient_id else None

    def add_symptom(self, patient_id: str, symptom: SymptomEvent, reported_at: datetime) -> None:
        data = symptom.model_dump()
        data["evidence_span"] = symptom.evidence_span.model_dump() if symptom.evidence_span else None
        self._s.add(SymptomEventRow(patient_id=patient_id, reported_at=reported_at, **data))

    # ------------------------------------------------------------ risk signals

    def risk_signals(self, patient_id: str) -> list[RiskSignal]:
        stmt = (
            select(RiskSignalRow)
            .where(RiskSignalRow.patient_id == patient_id)
            .order_by(RiskSignalRow.created_at)
        )
        return [_risk(r) for r in self._s.scalars(stmt)]

    def risk_signal(self, patient_id: str, fact_id: str) -> RiskSignal | None:
        row = self._s.get(RiskSignalRow, fact_id)
        return _risk(row) if row and row.patient_id == patient_id else None

    def add_risk_signal(self, patient_id: str, signal: RiskSignal) -> None:
        data = signal.model_dump()
        data["evidence_span"] = signal.evidence_span.model_dump() if signal.evidence_span else None
        data["value"] = (
            signal.value
            if isinstance(signal.value, dict)
            else ({"text": signal.value} if signal.value else None)
        )
        self._s.add(RiskSignalRow(patient_id=patient_id, **data))

    # ------------------------------------------------------------ labs

    def labs(self, patient_id: str) -> list[LabResult]:
        stmt = (
            select(LabResultRow)
            .where(LabResultRow.patient_id == patient_id)
            .order_by(LabResultRow.sample_date)
        )
        return [_lab(r) for r in self._s.scalars(stmt)]

    def lab(self, patient_id: str, fact_id: str) -> LabResult | None:
        row = self._s.get(LabResultRow, fact_id)
        return _lab(row) if row and row.patient_id == patient_id else None

    def add_lab(self, patient_id: str, lab: LabResult) -> None:
        self._s.add(LabResultRow(patient_id=patient_id, **lab.model_dump()))


# ---------------------------------------------------------------- mappers


def _questionnaire(r: QuestionnaireResponseRow) -> QuestionnaireResponse:
    return QuestionnaireResponse.model_validate(
        {
            "id": r.id,
            "instrument": r.instrument,
            "administered_at": r.administered_at,
            "item_scores": tuple(r.item_scores),
            "completion_status": r.completion_status,
            "total_score": r.total_score,
            "severity_band": r.severity_band,
            "baseline_score": r.baseline_score,
            "delta_from_previous": r.delta_from_previous,
            "delta_from_baseline": r.delta_from_baseline,
            "phq9_item9": r.phq9_item9,
            "source": r.source,
        }
    )


def _intake(r: MedicationIntakeRow) -> MedicationIntake:
    return MedicationIntake.model_validate(
        {
            "id": r.id,
            "drug": r.drug,
            "dose_mg": r.dose_mg,
            "slot_date": r.slot_date,
            "slot": r.slot,
            "status": r.status,
            "missed_reason": r.missed_reason,
            "marked_at": r.marked_at,
            "source": r.source,
            "confirmation": r.confirmation,
        }
    )


def _symptom(r: SymptomEventRow) -> SymptomEvent:
    return SymptomEvent.model_validate(
        {
            "id": r.id,
            "normalized_type": r.normalized_type,
            "patient_phrase": r.patient_phrase,
            "evidence_span": EvidenceSpan.model_validate(r.evidence_span) if r.evidence_span else None,
            "polarity": r.polarity,
            "experiencer": r.experiencer,
            "temporality": r.temporality,
            "onset_date": r.onset_date,
            "onset_precision": r.onset_precision,
            "existed_before_medication": r.existed_before_medication,
            "worsened_since_start": r.worsened_since_start,
            "affects_daily_life": r.affects_daily_life,
            "severity": r.severity,
            "status": r.status,
            "interferes_with_driving": r.interferes_with_driving,
            "source": r.source,
            "confirmation": r.confirmation,
        }
    )


def _risk(r: RiskSignalRow) -> RiskSignal:
    return RiskSignal.model_validate(
        {
            "id": r.id,
            "type": r.type,
            "value": r.value,
            "evidence_span": EvidenceSpan.model_validate(r.evidence_span) if r.evidence_span else None,
            "source": r.source,
            "confirmation": r.confirmation,
            "created_at": r.created_at,
        }
    )


def _lab(r: LabResultRow) -> LabResult:
    return LabResult.model_validate(
        {
            "id": r.id,
            "analyte": r.analyte,
            "value": r.value,
            "unit": r.unit,
            "reference_low": r.reference_low,
            "reference_high": r.reference_high,
            "sample_date": r.sample_date,
            "entered_by": r.entered_by,
            "doctor_verified": r.doctor_verified,
            "egfr_source": r.egfr_source,
        }
    )
