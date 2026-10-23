from datetime import UTC, datetime

from clinical_compass.domain.enums import (
    Confirmation,
    Experiencer,
    Polarity,
    RiskSignalType,
    SymptomType,
    Temporality,
)
from clinical_compass.domain.extraction import (
    ExtractedEntity,
    FreeTextExtraction,
    facts_from_extraction,
)
from clinical_compass.domain.state import EvidenceSpan


def entity(
    entity_type: str,
    value: dict[str, str],
    start: int,
    end: int,
    text: str,
) -> ExtractedEntity:
    return ExtractedEntity(
        type=entity_type,
        value=value,
        evidence_span=EvidenceSpan(start=start, end=end, text=text),
        polarity=Polarity.PRESENT,
        experiencer=Experiencer.PATIENT,
        temporality=Temporality.CURRENT,
    )


def test_allergy_risk_absorbs_overlapping_unlisted_symptoms() -> None:
    extraction = FreeTextExtraction(
        message_id="msg_allergy",
        patient_id="p_test",
        timestamp=datetime(2026, 10, 23, 11, 0, tzinfo=UTC),
        original_text=(
            "После таблетки появились сыпь и отек губ, стало трудно дышать, но также кружится голова."
        ),
        entities=(
            entity(
                "risk_signal",
                {"type": "possible_allergic_reaction"},
                25,
                61,
                "сыпь и отек губ, стало трудно дышать",
            ),
            entity(
                "symptom",
                {"normalized_type": "other_unlisted"},
                25,
                29,
                "сыпь",
            ),
            entity(
                "symptom",
                {"normalized_type": "other_unlisted"},
                32,
                40,
                "отек губ",
            ),
            entity(
                "symptom",
                {"normalized_type": "other_unlisted"},
                48,
                61,
                "трудно дышать",
            ),
            entity(
                "symptom",
                {"normalized_type": "dizziness"},
                74,
                89,
                "кружится голова",
            ),
        ),
        confirmation=Confirmation.PENDING,
        model_version="GigaChat-3-Ultra:extractor_prompt_v1.2",
    )

    facts = facts_from_extraction(
        extraction,
        lambda prefix: f"{prefix}_test",
    )

    assert len(facts.risk_signals) == 1
    assert facts.risk_signals[0].type is RiskSignalType.POSSIBLE_ALLERGIC_REACTION

    assert len(facts.symptoms) == 1
    assert facts.symptoms[0].normalized_type is SymptomType.DIZZINESS
