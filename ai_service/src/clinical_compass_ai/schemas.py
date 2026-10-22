from datetime import datetime
from typing import Annotated, Literal

from clinical_compass.domain.enums import (
    Experiencer,
    LabAnalyte,
    MissedReason,
    Polarity,
    RiskSignalType,
    Severity,
    SymptomType,
    Temporality,
    Tri,
)
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictInt,
    StrictStr,
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Evidence(StrictModel):
    text: StrictStr = Field(min_length=1)
    start: StrictInt = Field(ge=0)
    end: StrictInt = Field(ge=0)


class Symptom(StrictModel):
    entity_type: Literal["symptom"]
    normalized_type: SymptomType
    evidence_span: Evidence
    polarity: Polarity
    experiencer: Experiencer
    temporality: Temporality
    onset_date: str | None = None
    affects_daily_life: Tri | None = None
    severity: Severity | None = None


class Medication(StrictModel):
    entity_type: Literal["medication"]
    status: Literal["taken", "missed", "unknown"]
    slot: Literal["morning", "evening", "unknown"]
    evidence_span: Evidence
    missed_reason: MissedReason | None = None
    drug: str | None = None
    dose_mg: float | None = None


class Risk(StrictModel):
    entity_type: Literal["risk_signal"]
    type: RiskSignalType
    evidence_span: Evidence
    value: str | dict | None = None


class Lab(StrictModel):
    entity_type: Literal["lab_mention"]
    analyte: LabAnalyte
    value: float
    unit: str
    evidence_span: Evidence


Entity = Annotated[Symptom | Medication | Risk | Lab, Field(discriminator="entity_type")]


class ModelOutput(StrictModel):
    entities: list[Entity]
    unknown_fields: list[str] = []


class ExtractRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message_id: str = Field(min_length=1)
    patient_id: str = Field(min_length=1)
    timestamp: datetime
    text: str = Field(min_length=1)
    schema_version: Literal["0.2.0"] = "0.2.0"
