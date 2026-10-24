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
