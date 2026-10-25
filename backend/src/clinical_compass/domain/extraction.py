"""Контракт FreeTextExtraction v0.2 (§16) и заглушка извлечения.

ЗАГЛУШКА: небольшой лексикон red-flag фраз вместо NLP/LLM. Это не
валидированный классификатор: он нужен, чтобы цепочка
«текст → факты → правила → очередь» работала до подключения модели.
Факты от заглушки имеют source=text_lexicon и confirmation=pending.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict

from clinical_compass.domain.enums import (
    Confirmation,
    Experiencer,
    FactSource,
    IntakeSlot,
    IntakeStatus,
    MissedReason,
    Polarity,
    RiskSignalType,
    SymptomType,
    Temporality,
    Tri,
)
from clinical_compass.domain.state import EvidenceSpan, MedicationIntake, RiskSignal, SymptomEvent


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
    medication_intakes: tuple[MedicationIntake, ...]


@dataclass(frozen=True)
class IntakeWindow:
    """Какие даты приёма можно взять из текста: по календарю клиники, не в будущем
    и не раньше, чем пациент может отметить приём вручную."""

    today: date
    backfill_days: int = 2

    @classmethod
    def for_message(
        cls, timestamp: datetime, *, utc_offset_hours: int = 0, backfill_days: int = 2
    ) -> "IntakeWindow":
        local_day = (timestamp + timedelta(hours=utc_offset_hours)).date()
        return cls(today=local_day, backfill_days=backfill_days)

    def contains(self, day: date) -> bool:
        return self.today - timedelta(days=self.backfill_days) <= day <= self.today


def facts_from_extraction(
    extraction: FreeTextExtraction,
    new_id: Callable[[str], str],
    *,
    window: IntakeWindow | None = None,
) -> ExtractedFacts:
    """Сущности извлечения → факты Patient State.

    Отрицание, опыт другого человека и гипотетические упоминания фактами не становятся.
    Непригодная сущность (неизвестный код, неверный тип поля) пропускается:
    одна ошибка модели не отменяет остальные факты сообщения.
    """
    window = window or IntakeWindow.for_message(extraction.timestamp)
    source = (
        FactSource.TEXT_LEXICON
        if extraction.model_version.startswith("mock-lexicon")
        else FactSource.TEXT_LLM
    )
    symptoms: list[SymptomEvent] = []
    risks: list[RiskSignal] = []
    intakes: list[MedicationIntake] = []
    for entity in extraction.entities:
        if not _is_current_patient_fact(entity):
            continue
        try:
            if entity.type == "risk_signal":
                risks.append(_risk_signal(entity, source, extraction.timestamp, new_id))
            elif entity.type == "symptom":
                symptoms.append(_symptom(entity, source, new_id))
            elif entity.type == "medication" and (
                intake := _medication_intake(entity, source, extraction.timestamp, window, new_id)
            ):
                intakes.append(intake)
        except (KeyError, ValueError):
            continue
    return ExtractedFacts(
        symptoms=tuple(_without_allergy_duplicates(symptoms, risks)),
        risk_signals=tuple(risks),
        medication_intakes=tuple(intakes),
    )


def _is_current_patient_fact(entity: ExtractedEntity) -> bool:
    return (
        entity.polarity is Polarity.PRESENT
        and entity.experiencer is Experiencer.PATIENT
        and entity.temporality is not Temporality.HYPOTHETICAL
    )


def _risk_signal(
    entity: ExtractedEntity, source: FactSource, at: datetime, new_id: Callable[[str], str]
) -> RiskSignal:
    return RiskSignal(
        id=new_id("risk"),
        type=RiskSignalType(entity.value["type"]),
        evidence_span=entity.evidence_span,
        source=source,
        confirmation=Confirmation.PENDING,
        created_at=at,
    )


def _symptom(entity: ExtractedEntity, source: FactSource, new_id: Callable[[str], str]) -> SymptomEvent:
    return SymptomEvent(
        id=new_id("sym"),
        normalized_type=SymptomType(entity.value["normalized_type"]),
        patient_phrase=entity.evidence_span.text,
        evidence_span=entity.evidence_span,
        polarity=entity.polarity,
        experiencer=entity.experiencer,
        temporality=entity.temporality,
        affects_daily_life=Tri(entity.value.get("affects_daily_life", Tri.UNKNOWN)),
        source=source,
        confirmation=Confirmation.PENDING,
    )


def _medication_intake(
    entity: ExtractedEntity,
    source: FactSource,
    at: datetime,
    window: IntakeWindow,
    new_id: Callable[[str], str],
) -> MedicationIntake | None:
    """Отметка приёма из текста — только если дата, слот и статус однозначны."""
    slot_date = _slot_date(entity, window)
    status_raw, slot_raw = entity.value.get("status"), entity.value.get("slot")
    if slot_date is None or status_raw not in {"taken", "missed"} or slot_raw not in {"morning", "evening"}:
        return None
    status = IntakeStatus(status_raw)
    return MedicationIntake(
        id=new_id("intake"),
        drug=_drug_name(entity.value.get("drug")),
        dose_mg=_dose_mg(entity.value.get("dose_mg")),
        slot_date=slot_date,
        slot=IntakeSlot(slot_raw),
        status=status,
        missed_reason=_missed_reason(entity.value.get("missed_reason"))
        if status is IntakeStatus.MISSED
        else None,
        marked_at=at,
        source=source,
        confirmation=Confirmation.PENDING,
    )


def _slot_date(entity: ExtractedEntity, window: IntakeWindow) -> date | None:
    """Дата из ответа модели или из слов «сегодня»/«вчера» — только внутри окна отметок."""
    raw = entity.value.get("slot_date")
    day: date | None = None
    if isinstance(raw, str):
        try:
            day = date.fromisoformat(raw)
        except ValueError:
            day = None
    if day is None:
        text = entity.evidence_span.text.lower().replace("ё", "е")
        if "вчера" in text:
            day = window.today - timedelta(days=1)
        elif "сегодня" in text:
            day = window.today
    return day if day is not None and window.contains(day) else None


def _missed_reason(raw: Any) -> MissedReason:
    try:
        return MissedReason(raw)
    except ValueError:
        return MissedReason.UNKNOWN


def _drug_name(raw: Any) -> str | None:
    return raw.strip() if isinstance(raw, str) and raw.strip() and raw != "unknown" else None


def _dose_mg(raw: Any) -> float | None:
    """Доза только числом: «50 мг» или мусор от модели не должны ронять весь факт."""
    if isinstance(raw, bool) or not isinstance(raw, int | float):
        return None
    return float(raw) if raw > 0 else None


def _without_allergy_duplicates(symptoms: list[SymptomEvent], risks: list[RiskSignal]) -> list[SymptomEvent]:
    """«Другой симптом» внутри фрагмента об аллергической реакции — тот же факт, не второй алерт."""
    allergy_spans = [
        r.evidence_span
        for r in risks
        if r.type is RiskSignalType.POSSIBLE_ALLERGIC_REACTION and r.evidence_span is not None
    ]

    def inside_allergy(symptom: SymptomEvent) -> bool:
        span = symptom.evidence_span
        return span is not None and any(a.start <= span.start and span.end <= a.end for a in allergy_spans)

    return [
        s for s in symptoms if not (s.normalized_type is SymptomType.OTHER_UNLISTED and inside_allergy(s))
    ]


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
        "выпила всю пачку таблеток",
        "выпил всю пачку таблеток",
        "выпил много таблеток",
        "выпила много таблеток",
        "принял лишнюю",
        "приняла лишнюю",
        "передозиров",
    ),
    RiskSignalType.PREGNANCY_OR_LACTATION: (
        "забеременела",
        "беременна",
        "кормлю грудью",
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
