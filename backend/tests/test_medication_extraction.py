from datetime import UTC, datetime

from clinical_compass.domain.enums import (
    Confirmation,
    Experiencer,
    FactSource,
    IntakeSlot,
    IntakeStatus,
    MissedReason,
    Polarity,
    Temporality,
)
from clinical_compass.domain.extraction import (
    ExtractedEntity,
    FreeTextExtraction,
    IntakeWindow,
    facts_from_extraction,
)
from clinical_compass.domain.state import EvidenceSpan


def test_yesterday_missed_medication_becomes_pending_intake() -> None:
    extraction = FreeTextExtraction(
        message_id="msg_test",
        patient_id="p_test",
        timestamp=datetime(2026, 10, 23, 11, 0, tzinfo=UTC),
        original_text=("Вчера вечером таблетку не выпил, потому что сильно кружилась голова."),
        entities=(
            ExtractedEntity(
                type="medication",
                value={
                    "status": "missed",
                    "slot": "evening",
                    "missed_reason": "felt_unwell",
                },
                evidence_span=EvidenceSpan(
                    start=0,
                    end=31,
                    text="Вчера вечером таблетку не выпил",
                ),
                polarity=Polarity.PRESENT,
                experiencer=Experiencer.PATIENT,
                temporality=Temporality.CURRENT,
            ),
        ),
        model_version="GigaChat-3-Ultra:extractor_prompt_v1.2",
    )

    facts = facts_from_extraction(
        extraction,
        lambda prefix: f"{prefix}_test",
    )

    assert len(facts.medication_intakes) == 1

    intake = facts.medication_intakes[0]
    assert intake.slot_date.isoformat() == "2026-10-22"
    assert intake.slot is IntakeSlot.EVENING
    assert intake.status is IntakeStatus.MISSED
    assert intake.missed_reason is MissedReason.FELT_UNWELL
    assert intake.drug is None
    assert intake.source is FactSource.TEXT_LLM
    assert intake.confirmation is Confirmation.PENDING


def _medication(text: str, **value: object) -> ExtractedEntity:
    return ExtractedEntity(
        type="medication",
        value={"status": "missed", "slot": "morning", **value},
        evidence_span=EvidenceSpan(start=0, end=len(text), text=text),
        polarity=Polarity.PRESENT,
        experiencer=Experiencer.PATIENT,
        temporality=Temporality.CURRENT,
    )


def _message(at: datetime, *entities: ExtractedEntity) -> FreeTextExtraction:
    return FreeTextExtraction(
        message_id="msg_test",
        patient_id="p_test",
        timestamp=at,
        original_text=" ".join(e.evidence_span.text for e in entities),
        entities=entities,
        model_version="test-llm",
    )


def test_relative_dates_follow_the_clinic_calendar() -> None:
    # 22:30 UTC — это уже 01:30 следующего дня в клинике (UTC+3).
    late_evening = datetime(2026, 10, 21, 22, 30, tzinfo=UTC)
    window = IntakeWindow.for_message(late_evening, utc_offset_hours=3, backfill_days=2)
    facts = facts_from_extraction(
        _message(late_evening, _medication("Сегодня утром не выпил таблетку")),
        lambda prefix: f"{prefix}_1",
        window=window,
    )
    assert [i.slot_date.isoformat() for i in facts.medication_intakes] == ["2026-10-22"]


def test_dates_outside_the_backfill_window_are_ignored() -> None:
    at = datetime(2026, 10, 21, 9, 0, tzinfo=UTC)
    window = IntakeWindow.for_message(at, utc_offset_hours=3, backfill_days=2)
    facts = facts_from_extraction(
        _message(
            at,
            _medication("пропустил давно", slot_date="2025-01-01"),
            _medication("пропущу завтра", slot_date="2026-10-22"),
            _medication("позавчера утром не выпил", slot_date="2026-10-19"),
        ),
        lambda prefix: f"{prefix}_{prefix}",
        window=window,
    )
    assert [i.slot_date.isoformat() for i in facts.medication_intakes] == ["2026-10-19"]


def test_one_unusable_entity_does_not_drop_the_others() -> None:
    at = datetime(2026, 10, 21, 9, 0, tzinfo=UTC)
    broken_risk = ExtractedEntity(
        type="risk_signal",
        value={"type": "not_a_known_risk"},
        evidence_span=EvidenceSpan(start=0, end=5, text="что-то"),
        polarity=Polarity.PRESENT,
        experiencer=Experiencer.PATIENT,
        temporality=Temporality.CURRENT,
    )
    facts = facts_from_extraction(
        _message(at, broken_risk, _medication("Сегодня утром не выпил таблетку")),
        lambda prefix: f"{prefix}_1",
    )
    assert facts.risk_signals == ()
    assert len(facts.medication_intakes) == 1
