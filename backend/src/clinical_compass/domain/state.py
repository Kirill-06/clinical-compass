"""Сущности Patient State v0.2.

`to_schema()` каждой модели выдаёт ровно поля `patient_state_v0.2.schema.json`
(в схеме `additionalProperties: false`). Модели неизменяемые.
"""

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from clinical_compass import SCHEMA_VERSION
from clinical_compass.domain.enums import (
    AlertStatus,
    CompletionStatus,
    Confirmation,
    DoctorPriority,
    Experiencer,
    FactSource,
    Instrument,
    IntakeSlot,
    IntakeStatus,
    LabAnalyte,
    MissedReason,
    PatientAction,
    Polarity,
    RiskSignalType,
    RouteDecision,
    Severity,
    SymptomType,
    Temporality,
    Tri,
)

DEFAULT_INTERVAL_DAYS = 14


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    def to_schema(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class QuestionnaireSchedule(_Frozen):
    instrument: Instrument
    interval_days: int = Field(ge=1)
    configured_by: str  # system_default | doctor
    active: bool
    next_due_at: datetime | None = None

    def to_schema(self) -> dict[str, Any]:
        return {**super().to_schema(), "default_interval_days": DEFAULT_INTERVAL_DAYS}


class QuestionnaireResponse(_Frozen):
    id: str
    instrument: Instrument
    administered_at: datetime
    item_scores: tuple[int, ...]
    completion_status: CompletionStatus
    total_score: int | None = None
    severity_band: str | None = None
    baseline_score: int | None = None
    delta_from_previous: int | None = None
    """Со знаком: текущий − предыдущий (§6.1)."""
    delta_from_baseline: int | None = None
    phq9_item9: int | None = None
    source: FactSource


class MedicationIntake(_Frozen):
    id: str
    drug: str | None = None
    dose_mg: float | None = None
    slot_date: date
    slot: IntakeSlot
    status: IntakeStatus
    missed_reason: MissedReason | None = None
    marked_at: datetime | None = None
    source: FactSource
    confirmation: Confirmation

    def to_schema(self) -> dict[str, Any]:
        data = super().to_schema()
        # В схеме у этих полей нет null — отсутствие передаётся отсутствием ключа.
        for key in ("drug", "missed_reason"):
            if data[key] is None:
                del data[key]
        return data


class EvidenceSpan(_Frozen):
    start: int = Field(ge=0)
    end: int = Field(ge=0)
    text: str


class SymptomEvent(_Frozen):
    id: str
    normalized_type: SymptomType
    patient_phrase: str | None = None
    evidence_span: EvidenceSpan | None = None
    polarity: Polarity
    experiencer: Experiencer
    temporality: Temporality
    onset_date: date | None = None
    onset_precision: str = "unknown"
    existed_before_medication: Tri = Tri.UNKNOWN
    worsened_since_start: Tri = Tri.UNKNOWN
    affects_daily_life: Tri = Tri.UNKNOWN
    severity: Severity = Severity.UNKNOWN
    status: str = "unknown"
    interferes_with_driving: str = "unknown"
    source: FactSource
    confirmation: Confirmation


class RiskSignal(_Frozen):
    id: str
    type: RiskSignalType
    value: str | dict[str, Any] | None = None
    evidence_span: EvidenceSpan | None = None
    source: FactSource
    confirmation: Confirmation
    created_at: datetime


class LabResult(_Frozen):
    id: str
    analyte: LabAnalyte
    value: float
    unit: str
    reference_low: float | None = None
    reference_high: float | None = None
    sample_date: date
    entered_by: str  # patient | doctor | imported
    doctor_verified: bool
    egfr_source: str | None = None

    def to_schema(self) -> dict[str, Any]:
        data = super().to_schema()
        if data["egfr_source"] is None:
            del data["egfr_source"]
        return data


class RoutingDecision(_Frozen):
    system_recommendation: str = "none"  # none | review_needed
    doctor_decision: RouteDecision = RouteDecision.PENDING
    patient_visible: bool = False
    """Пациент видит маршрут только после подтверждения врачом (§14)."""
    confirmed_at: datetime | None = None


class Alert(_Frozen):
    id: str
    rule_id: str
    doctor_priority: DoctorPriority
    patient_action: PatientAction
    source_fact_ids: tuple[str, ...] = ()
    message_template_id: str | None = None
    rule_version: str
    created_at: datetime
    delivered_to_workplace_at: datetime | None = None
    viewed_at: datetime | None = None
    status: AlertStatus


class PatientState(_Frozen):
    """Нормализованное состояние пациента — единственный вход rule engine."""

    patient_id: str
    doctor_id: str | None = None
    updated_at: datetime
    questionnaire_schedules: tuple[QuestionnaireSchedule, ...] = ()
    questionnaires: tuple[QuestionnaireResponse, ...] = ()
    medication_intakes: tuple[MedicationIntake, ...] = ()
    symptoms: tuple[SymptomEvent, ...] = ()
    risk_signals: tuple[RiskSignal, ...] = ()
    labs: tuple[LabResult, ...] = ()
    routing: RoutingDecision | None = None
    alerts: tuple[Alert, ...] = ()

    def to_schema(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "patient_id": self.patient_id,
            "doctor_id": self.doctor_id,
            "updated_at": self.model_dump(mode="json")["updated_at"],
            "questionnaire_schedules": [s.to_schema() for s in self.questionnaire_schedules],
            "questionnaires": [q.to_schema() for q in self.questionnaires],
            "medication_intakes": [i.to_schema() for i in self.medication_intakes],
            "symptoms": [s.to_schema() for s in self.symptoms],
            "risk_signals": [r.to_schema() for r in self.risk_signals],
            "labs": [lab.to_schema() for lab in self.labs],
            "routing": self.routing.to_schema() if self.routing else None,
            "alerts": [a.to_schema() for a in self.alerts],
        }

    @classmethod
    def from_schema(cls, data: dict[str, Any]) -> "PatientState":
        """Разобрать Patient State, уже проверенный по JSON Schema."""
        payload = {k: v for k, v in data.items() if k != "schema_version"}
        payload["questionnaire_schedules"] = [
            {k: v for k, v in s.items() if k != "default_interval_days"}
            for s in payload.get("questionnaire_schedules", [])
        ]
        return cls.model_validate(payload)
