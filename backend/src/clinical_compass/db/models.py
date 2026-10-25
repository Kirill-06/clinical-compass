"""Таблицы. Поля фактов совпадают с patient_state_v0.2.schema.json.

Все моменты времени хранятся с часовым поясом (UTC); календарные даты — `date`.
Схема БД меняется только миграциями Alembic (`migrations/`).
"""

from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Dialect,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    TypeDecorator,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class UTCDateTime(TypeDecorator[datetime]):
    """Момент времени в UTC с часовым поясом — одинаково в PostgreSQL и SQLite."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:  # noqa: ARG002
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("Ожидалось время с часовым поясом")
        return value.astimezone(UTC)

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:  # noqa: ARG002
        if value is None:
            return None
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class Base(DeclarativeBase):
    type_annotation_map = {  # noqa: RUF012 — так требует SQLAlchemy
        datetime: UTCDateTime(),
        dict[str, Any]: JSON,
        list[Any]: JSON,
    }


_ID = 64


# ---------------------------------------------------------------- люди и связи


class DoctorRow(Base):
    __tablename__ = "doctors"

    id: Mapped[str] = mapped_column(String(_ID), primary_key=True)
    full_name: Mapped[str] = mapped_column(String(200))
    short_name: Mapped[str] = mapped_column(String(100))
    specialty: Mapped[str] = mapped_column(String(200))


class AdminRow(Base):
    __tablename__ = "admins"

    id: Mapped[str] = mapped_column(String(_ID), primary_key=True)
    full_name: Mapped[str] = mapped_column(String(200))


class PatientRow(Base):
    __tablename__ = "patients"

    id: Mapped[str] = mapped_column(String(_ID), primary_key=True)
    display_id: Mapped[str] = mapped_column(String(32), unique=True)
    full_name: Mapped[str] = mapped_column(String(200))
    first_name: Mapped[str] = mapped_column(String(100))
    birth_year: Mapped[int] = mapped_column(Integer)
    sex: Mapped[str | None] = mapped_column(String(16))
    phone: Mapped[str | None] = mapped_column(String(32))
    observation_start: Mapped[datetime]


class DoctorPatientLinkRow(Base):
    """Врач видит только закреплённых пациентов (§3)."""

    __tablename__ = "doctor_patient_links"

    id: Mapped[str] = mapped_column(String(_ID), primary_key=True)
    doctor_id: Mapped[str] = mapped_column(ForeignKey("doctors.id"), index=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), index=True)
    active_from: Mapped[datetime]
    active_to: Mapped[datetime | None]


class SessionRow(Base):
    """Сессии входа. Хранится только хэш токена."""

    __tablename__ = "sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(_ID), index=True)
    role: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime]
    expires_at: Mapped[datetime]


# ---------------------------------------------------------------- назначения и расписания


class MedicationPlanRow(Base):
    __tablename__ = "medication_plans"

    id: Mapped[str] = mapped_column(String(_ID), primary_key=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), index=True)
    drug: Mapped[str] = mapped_column(String(200))
    instructions: Mapped[str] = mapped_column(Text)
    slots: Mapped[list[Any]]
    start_date: Mapped[date] = mapped_column(Date)
    created_by: Mapped[str] = mapped_column(ForeignKey("doctors.id"))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class QuestionnaireScheduleRow(Base):
    __tablename__ = "questionnaire_schedules"

    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), primary_key=True)
    instrument: Mapped[str] = mapped_column(String(8), primary_key=True)
    interval_days: Mapped[int] = mapped_column(Integer)
    configured_by: Mapped[str] = mapped_column(String(32))
    active: Mapped[bool] = mapped_column(Boolean)
    updated_at: Mapped[datetime]


class ClinicalProfileRow(Base):
    __tablename__ = "clinical_profiles"

    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), primary_key=True)
    route_review_needed: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime]


class RoutingDecisionRow(Base):
    __tablename__ = "routing_decisions"

    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), primary_key=True)
    system_recommendation: Mapped[str] = mapped_column(String(32))
    doctor_decision: Mapped[str] = mapped_column(String(16))
    patient_visible: Mapped[bool] = mapped_column(Boolean)
    confirmed_at: Mapped[datetime | None]
    confirmed_by: Mapped[str | None] = mapped_column(String(_ID))


# ---------------------------------------------------------------- факты Patient State


class QuestionnaireResponseRow(Base):
    __tablename__ = "questionnaire_responses"
    __table_args__ = (Index("ix_questionnaire_patient_time", "patient_id", "administered_at"),)

    id: Mapped[str] = mapped_column(String(_ID), primary_key=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"))
    instrument: Mapped[str] = mapped_column(String(8))
    administered_at: Mapped[datetime]
    item_scores: Mapped[list[Any]]
    completion_status: Mapped[str] = mapped_column(String(16))
    total_score: Mapped[int | None] = mapped_column(Integer)
    severity_band: Mapped[str | None] = mapped_column(String(32))
    baseline_score: Mapped[int | None] = mapped_column(Integer)
    delta_from_previous: Mapped[int | None] = mapped_column(Integer)
    delta_from_baseline: Mapped[int | None] = mapped_column(Integer)
    phq9_item9: Mapped[int | None] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(16))


class MedicationIntakeRow(Base):
    """Одна запись на слот: исправление обновляет её (аудит хранит историю)."""

    __tablename__ = "medication_intakes"
    __table_args__ = (UniqueConstraint("patient_id", "slot_date", "slot", name="uq_intake_slot"),)

    id: Mapped[str] = mapped_column(String(_ID), primary_key=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), index=True)
    drug: Mapped[str | None] = mapped_column(String(200))
    dose_mg: Mapped[float | None] = mapped_column(Float)
    slot_date: Mapped[date] = mapped_column(Date)
    slot: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16))
    missed_reason: Mapped[str | None] = mapped_column(String(32))
    marked_at: Mapped[datetime | None]
    source: Mapped[str] = mapped_column(String(16))
    confirmation: Mapped[str] = mapped_column(String(24))


class SymptomEventRow(Base):
    __tablename__ = "symptom_events"

    id: Mapped[str] = mapped_column(String(_ID), primary_key=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), index=True)
    reported_at: Mapped[datetime]
    normalized_type: Mapped[str] = mapped_column(String(32))
    patient_phrase: Mapped[str | None] = mapped_column(Text)
    evidence_span: Mapped[dict[str, Any] | None]
    polarity: Mapped[str] = mapped_column(String(16))
    experiencer: Mapped[str] = mapped_column(String(16))
    temporality: Mapped[str] = mapped_column(String(16))
    onset_date: Mapped[date | None] = mapped_column(Date)
    onset_precision: Mapped[str] = mapped_column(String(16))
    existed_before_medication: Mapped[str] = mapped_column(String(8))
    worsened_since_start: Mapped[str] = mapped_column(String(8))
    affects_daily_life: Mapped[str] = mapped_column(String(8))
    severity: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16))
    interferes_with_driving: Mapped[str] = mapped_column(String(16))
    source: Mapped[str] = mapped_column(String(16))
    confirmation: Mapped[str] = mapped_column(String(24))


class RiskSignalRow(Base):
    __tablename__ = "risk_signals"

    id: Mapped[str] = mapped_column(String(_ID), primary_key=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), index=True)
    type: Mapped[str] = mapped_column(String(40))
    value: Mapped[dict[str, Any] | None]
    evidence_span: Mapped[dict[str, Any] | None]
    source: Mapped[str] = mapped_column(String(16))
    confirmation: Mapped[str] = mapped_column(String(24))
    created_at: Mapped[datetime]


class LabResultRow(Base):
    __tablename__ = "lab_results"

    id: Mapped[str] = mapped_column(String(_ID), primary_key=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), index=True)
    analyte: Mapped[str] = mapped_column(String(32))
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(32))
    reference_low: Mapped[float | None] = mapped_column(Float)
    reference_high: Mapped[float | None] = mapped_column(Float)
    sample_date: Mapped[date] = mapped_column(Date)
    entered_by: Mapped[str] = mapped_column(String(16))
    doctor_verified: Mapped[bool] = mapped_column(Boolean)
    egfr_source: Mapped[str | None] = mapped_column(String(16))


# ---------------------------------------------------------------- сообщения и вложения


class MessageRow(Base):
    """Сообщение сохраняется ДО обработки ИИ; сбой извлечения его не теряет (§21)."""

    __tablename__ = "messages"
    __table_args__ = (Index("ix_message_patient_time", "patient_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(_ID), primary_key=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"))
    sender: Mapped[str] = mapped_column(String(16))
    recipient_doctor_id: Mapped[str | None] = mapped_column(String(_ID))
    text: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime]
    extraction_status: Mapped[str] = mapped_column(String(24))
    extraction_error: Mapped[str | None] = mapped_column(Text)
    clarifying_questions: Mapped[list[Any]]
    read_at: Mapped[datetime | None]
    """Когда получатель (пациент или врач) открыл переписку с этим сообщением."""


class AttachmentRow(Base):
    __tablename__ = "attachments"

    id: Mapped[str] = mapped_column(String(_ID), primary_key=True)
    message_id: Mapped[str] = mapped_column(ForeignKey("messages.id"), index=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(100))
    size: Mapped[int] = mapped_column(Integer)
    storage_key: Mapped[str] = mapped_column(String(255))
    uploaded_at: Mapped[datetime]


class ExtractionRow(Base):
    """Результат извлечения (FreeTextExtraction v0.2) для сообщения."""

    __tablename__ = "extractions"

    message_id: Mapped[str] = mapped_column(String(_ID), primary_key=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), index=True)
    model_version: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict[str, Any]]
    created_at: Mapped[datetime]


# ---------------------------------------------------------------- алерты и задачи


class AlertRow(Base):
    __tablename__ = "alerts"
    __table_args__ = (
        UniqueConstraint("patient_id", "dedupe_key", name="uq_alert_dedupe"),
        Index("ix_alert_doctor_status", "doctor_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(_ID), primary_key=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"))
    doctor_id: Mapped[str | None] = mapped_column(String(_ID))
    rule_id: Mapped[str] = mapped_column(String(64))
    rule_version: Mapped[str] = mapped_column(String(16))
    rule_source: Mapped[str] = mapped_column(String(128))
    doctor_priority: Mapped[str] = mapped_column(String(16))
    patient_action: Mapped[str] = mapped_column(String(32))
    medical_urgency_classified: Mapped[bool] = mapped_column(Boolean)
    message_template_id: Mapped[str | None] = mapped_column(String(64))
    source_fact_ids: Mapped[list[Any]]
    dedupe_key: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime]
    delivered_to_workplace_at: Mapped[datetime | None]
    viewed_at: Mapped[datetime | None]
    acknowledged_at: Mapped[datetime | None]
    acknowledged_by: Mapped[str | None] = mapped_column(String(100))
    resolved_at: Mapped[datetime | None]
    resolved_by: Mapped[str | None] = mapped_column(String(100))


class BookingTaskRow(Base):
    """Задача администратору: только контакт и срок, без клинических данных (§15)."""

    __tablename__ = "booking_tasks"

    id: Mapped[str] = mapped_column(String(_ID), primary_key=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), index=True)
    requested_by_doctor_id: Mapped[str] = mapped_column(ForeignKey("doctors.id"))
    deadline: Mapped[datetime]
    status: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]


# ---------------------------------------------------------------- служебное


class AuditEventRow(Base):
    """Audit trail: кто, когда и что изменил (§21)."""

    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_audit_patient_time", "patient_id", "at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    at: Mapped[datetime]
    actor: Mapped[str] = mapped_column(String(_ID))
    action: Mapped[str] = mapped_column(String(64))
    entity: Mapped[str] = mapped_column(String(32))
    entity_id: Mapped[str] = mapped_column(String(_ID))
    patient_id: Mapped[str | None] = mapped_column(String(_ID))


# ---------------------------------------------------------------- интеграции с МИС


class ExternalIdentityRow(Base):
    """Идентификатор пациента или врача во внешней МИС (ЕМИАС, 1С) → внутренний id."""

    __tablename__ = "external_identities"
    __table_args__ = (UniqueConstraint("system", "kind", "external_id", name="uq_external_identity"),)

    id: Mapped[str] = mapped_column(String(_ID), primary_key=True)
    system: Mapped[str] = mapped_column(String(16))
    kind: Mapped[str] = mapped_column(String(16))
    external_id: Mapped[str] = mapped_column(String(64))
    internal_id: Mapped[str] = mapped_column(String(_ID), index=True)


class LaunchCodeRow(Base):
    """Одноразовый код запуска окна из МИС. Хранится только хэш кода."""

    __tablename__ = "launch_codes"

    code_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    system: Mapped[str] = mapped_column(String(16))
    doctor_id: Mapped[str] = mapped_column(ForeignKey("doctors.id"))
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"))
    created_at: Mapped[datetime]
    expires_at: Mapped[datetime]
    used_at: Mapped[datetime | None]


class IdempotencyKeyRow(Base):
    """Повтор запроса с тем же ключом возвращает прежний ответ, а не создаёт дубль."""

    __tablename__ = "idempotency_keys"

    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    response: Mapped[dict[str, Any]]
    created_at: Mapped[datetime]
