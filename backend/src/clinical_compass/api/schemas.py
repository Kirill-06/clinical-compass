"""Схемы входящих запросов. Ответы описаны в `services/presenter.py`."""

import base64
import binascii
from datetime import date
from typing import Any

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from clinical_compass.domain.enums import (
    BookingStatus,
    Instrument,
    IntakeSlot,
    IntakeStatus,
    LabAnalyte,
    MissedReason,
    RouteDecision,
    Severity,
    SymptomType,
    Tri,
)


class _Request(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DemoLoginRequest(_Request):
    user_id: str = Field(min_length=1, max_length=64)


class QuestionnaireRequest(_Request):
    instrument: Instrument
    item_scores: list[int] = Field(max_length=20)


class IntakeRequest(_Request):
    slot_date: date
    slot: IntakeSlot
    status: IntakeStatus
    missed_reason: MissedReason | None = None


class SymptomRequest(_Request):
    normalized_type: SymptomType
    patient_phrase: str | None = Field(default=None, max_length=1000)
    affects_daily_life: Tri = Tri.UNKNOWN
    severity: Severity = Severity.UNKNOWN
    worsened_since_start: Tri = Tri.UNKNOWN
    onset_date: date | None = None


class AttachmentUpload(_Request):
    filename: str = Field(min_length=1, max_length=255)
    mime_type: str = Field(min_length=1, max_length=100)
    data_base64: str

    def decode(self) -> bytes:
        try:
            return base64.b64decode(self.data_base64, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("Вложение повреждено") from exc


class MessageRequest(_Request):
    text: str | None = Field(default=None, max_length=2000)
    attachments: list[AttachmentUpload] = Field(default_factory=list, max_length=10)


class LabRequest(_Request):
    analyte: LabAnalyte
    value: float
    unit: str = Field(min_length=1, max_length=32)
    reference_low: float | None = None
    reference_high: float | None = None
    sample_date: date
    egfr_source: str | None = None

    def to_body(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class ScheduleRequest(_Request):
    interval_days: int | None = Field(default=None, ge=1, le=180)
    active: bool | None = None


class RoutingRequest(_Request):
    decision: RouteDecision


class ContactDeadlineRequest(_Request):
    deadline: AwareDatetime


class BookingUpdateRequest(_Request):
    status: BookingStatus


class ExtractRequest(_Request):
    patient_id: str
    text: str = Field(min_length=1, max_length=5000)


class RuleContextRequest(_Request):
    sex: str | None = None
    route_review_needed: bool = False


class EvaluateRulesRequest(_Request):
    patient_state: dict[str, Any]
    context: RuleContextRequest | None = None


class ClinicalProfileRequest(_Request):
    route_review_needed: bool


class FactsRequest(BaseModel):
    """Свободная форма: проверяется по JSON Schema v0.2 в сервисе."""

    model_config = ConfigDict(extra="forbid")

    extraction: dict[str, Any] | None = None
    symptoms: list[dict[str, Any]] | None = None
    risk_signals: list[dict[str, Any]] | None = None
    labs: list[dict[str, Any]] | None = None
