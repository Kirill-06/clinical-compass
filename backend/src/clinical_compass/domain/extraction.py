"""Контракт FreeTextExtraction v0.2 (§16) и заглушка извлечения.

ЗАГЛУШКА: небольшой лексикон red-flag фраз вместо NLP/LLM. Это не
валидированный классификатор: он нужен, чтобы цепочка
«текст → факты → правила → очередь» работала до подключения модели.
Факты от заглушки имеют source=text_lexicon и confirmation=pending.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict

from clinical_compass.domain.enums import (
    Confirmation,
    Experiencer,
    FactSource,
    Polarity,
    RiskSignalType,
    SymptomType,
    Temporality,
    Tri,
)
from clinical_compass.domain.state import EvidenceSpan, RiskSignal, SymptomEvent


class ExtractedEntity(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    type: Literal["symptom", "medication", "risk_signal", "lab_mention"]
    value: dict[str, Any]
    evidence_span: EvidenceSpan
    polarity: Polarity
    experiencer: Experiencer
    temporality: Temporality
    source: str = "llm"


class FreeTextExtraction(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    message_id: str
    patient_id: str
    timestamp: datetime
    channel: str = "chat"
    original_text: str
    entities: tuple[ExtractedEntity, ...] = ()
    unknown_fields: tuple[str, ...] = ()
    clarifying_questions: tuple[str, ...] = ()
    schema_validation: str = "valid"
    confirmation: Confirmation = Confirmation.PENDING
    model_version: str
    schema_version: Literal["0.2.0"] = "0.2.0"


class Extractor(Protocol):
    """Граница AI-слоя. Реализация: заглушка, LLM или внешний сервис."""

    def extract(
        self, *, message_id: str, patient_id: str, timestamp: datetime, text: str
    ) -> FreeTextExtraction: ...


@dataclass(frozen=True)
class ExtractedFacts:
    symptoms: tuple[SymptomEvent, ...]
    risk_signals: tuple[RiskSignal, ...]


def facts_from_extraction(extraction: FreeTextExtraction, new_id: Callable[[str], str]) -> ExtractedFacts:
    """Сущности извлечения → факты Patient State.

    Отрицание, опыт другого человека и гипотетические упоминания фактами не становятся.
    """
    source = (
        FactSource.TEXT_LEXICON
        if extraction.model_version.startswith("mock-lexicon")
        else FactSource.TEXT_LLM
    )
    symptoms: list[SymptomEvent] = []
    risks: list[RiskSignal] = []
    for e in extraction.entities:
        if e.polarity is not Polarity.PRESENT or e.experiencer is not Experiencer.PATIENT:
            continue
        if e.temporality is Temporality.HYPOTHETICAL:
            continue
        if e.type == "risk_signal":
            risks.append(
                RiskSignal(
                    id=new_id("risk"),
                    type=RiskSignalType(e.value["type"]),
                    evidence_span=e.evidence_span,
                    source=source,
                    confirmation=Confirmation.PENDING,
                    created_at=extraction.timestamp,
                )
            )
        elif e.type == "symptom":
            symptoms.append(
                SymptomEvent(
                    id=new_id("sym"),
                    normalized_type=SymptomType(e.value["normalized_type"]),
                    patient_phrase=e.evidence_span.text,
                    evidence_span=e.evidence_span,
                    polarity=e.polarity,
                    experiencer=e.experiencer,
                    temporality=e.temporality,
                    affects_daily_life=Tri(e.value.get("affects_daily_life", Tri.UNKNOWN)),
                    source=source,
                    confirmation=Confirmation.PENDING,
                )
            )
    return ExtractedFacts(symptoms=tuple(symptoms), risk_signals=tuple(risks))


_PATTERNS: dict[RiskSignalType, tuple[str, ...]] = {
    RiskSignalType.SELF_HARM_OR_SUICIDAL: (
        "не хочу жить",
        "хочу умереть",
        "покончить с собой",
        "покончить с жизнью",
        "причинить себе вред",
        "навредить себе",
        "суицид",
        "самоубийств",
    ),
    RiskSignalType.POSSIBLE_OVERDOSE: (
        "выпил много таблеток",
        "выпила много таблеток",
        "принял лишнюю",
        "приняла лишнюю",
        "передозиров",
    ),
    RiskSignalType.POSSIBLE_ALLERGIC_REACTION: (
        "отек лица",
        "отёк лица",
        "отекло горло",
        "отёк горла",
        "трудно дышать",
        "аллергическ",
        "крапивниц",
    ),
    RiskSignalType.INTENTION_TO_STOP_TREATMENT: (
        "брошу пить",
        "брошу принимать",
        "перестану принимать",
        "перестану пить",
        "хочу бросить лечение",
        "хочу прекратить лечение",
        "не буду больше принимать",
    ),
}
_NEGATIONS = (" не ", " нет ", " никогда ", " ни разу ")
_OTHER_PEOPLE = (
    "у мамы",
    "у папы",
    "у мужа",
    "у жены",
    "у друга",
    "у подруги",
    "у сына",
    "у дочери",
    "у брата",
    "у сестры",
)
_VAGUE_ABDOMINAL = ("болит живот", "живот болит")


class MockLexiconExtractor:
    """Заглушка: только red-flag сигналы по фиксированным фразам."""

    version = "mock-lexicon-0.1"

    def extract(
        self, *, message_id: str, patient_id: str, timestamp: datetime, text: str
    ) -> FreeTextExtraction:
        lower = text.lower()
        entities: list[ExtractedEntity] = []
        for signal, stems in _PATTERNS.items():
            for stem in stems:
                at = lower.find(stem)
                if at < 0:
                    continue
                before = " " + lower[max(0, at - 12) : at]
                context = lower[max(0, at - 32) : at]
                # Фразы, которые сами начинаются с «не» («не хочу жить»), не считаются отрицанием.
                negated = not stem.startswith("не ") and any(n in before for n in _NEGATIONS)
                other = any(o in context for o in _OTHER_PEOPLE)
                entities.append(
                    ExtractedEntity(
                        type="risk_signal",
                        value={"type": signal.value},
                        evidence_span=EvidenceSpan(
                            start=at, end=at + len(stem), text=text[at : at + len(stem)]
                        ),
                        polarity=Polarity.ABSENT if negated else Polarity.PRESENT,
                        experiencer=Experiencer.OTHER if other else Experiencer.PATIENT,
                        temporality=Temporality.CURRENT,
                        source="lexicon",
                    )
                )
                break
        clarifying: tuple[str, ...] = ()
        if any(p in lower for p in _VAGUE_ABDOMINAL):
            clarifying = ("Где именно болит живот: вверху, внизу, справа или слева?",)
        return FreeTextExtraction(
            message_id=message_id,
            patient_id=patient_id,
            timestamp=timestamp,
            original_text=text,
            entities=tuple(entities),
            clarifying_questions=clarifying,
            model_version=self.version,
        )
