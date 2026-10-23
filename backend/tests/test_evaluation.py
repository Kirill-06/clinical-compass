"""Regression checks for per-message semantic matching."""

import json
from datetime import datetime
from pathlib import Path

from clinical_compass.domain.extraction import ExtractedEntity, FreeTextExtraction
from clinical_compass.domain.state import EvidenceSpan
from clinical_compass.evaluation import evaluate_extractor, rescore_saved_predictions


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def test_risk_in_another_message_is_fp_and_fn(tmp_path: Path) -> None:
    dataset = tmp_path / "gold.jsonl"
    _write_jsonl(
        dataset,
        [
            {
                "message_id": "a",
                "text": "Хочу умереть",
                "gold_entities": [
                    {
                        "entity_type": "risk_signal",
                        "type": "self_harm_or_suicidal",
                        "evidence_span": {"start": 0, "end": 12, "text": "Хочу умереть"},
                    }
                ],
            },
            {"message_id": "b", "text": "Все хорошо", "gold_entities": []},
        ],
    )

    class Extractor:
        def extract(
            self, *, message_id: str, patient_id: str, timestamp: datetime, text: str
        ) -> FreeTextExtraction:
            entities = (
                ()
                if message_id == "a"
                else (
                    ExtractedEntity(
                        type="risk_signal",
                        value={"type": "self_harm_or_suicidal"},
                        evidence_span=EvidenceSpan(start=0, end=10, text="Все хорошо"),
                        polarity="present",
                        experiencer="patient",
                        temporality="current",
                    ),
                )
            )
            return FreeTextExtraction(
                message_id=message_id,
                patient_id=patient_id,
                timestamp=timestamp,
                original_text=text,
                entities=entities,
                model_version="test",
            )

    metrics = evaluate_extractor(Extractor(), dataset).metrics
    assert metrics["overall"] == {
        "tp": 0,
        "fp": 1,
        "fn": 1,
        "precision": 0.0,
        "recall": 0.0,
        "f1": 0.0,
    }
    assert metrics["per_entity_type"]["risk_signal"]["fn"] == 1
    assert metrics["risk_recall"] == 0.0


def test_saved_symptom_and_medication_attributes_do_not_cancel_across_messages(tmp_path: Path) -> None:
    gold_path = tmp_path / "gold.jsonl"
    pred_path = tmp_path / "pred.jsonl"
    original_path = tmp_path / "old.json"
    symptoms = [
        {
            "entity_type": "symptom",
            "normalized_type": "headache",
            "polarity": polarity,
            "experiencer": "patient",
            "temporality": "current",
        }
        for polarity in ("present", "absent")
    ]
    medications = [
        {"entity_type": "medication", "status": "missed", "slot": slot, "missed_reason": "forgot"}
        for slot in ("morning", "evening")
    ]
    _write_jsonl(
        gold_path,
        [
            {"message_id": "a", "text": "a", "gold_entities": [symptoms[0], medications[0]]},
            {"message_id": "b", "text": "b", "gold_entities": [symptoms[1], medications[1]]},
        ],
    )
    _write_jsonl(
        pred_path,
        [
            {"message_id": "a", "text": "a", "predicted_entities": [symptoms[1], medications[1]]},
            {"message_id": "b", "text": "b", "predicted_entities": [symptoms[0], medications[0]]},
        ],
    )
    original_path.write_text(
        json.dumps(
            {"latency_ms": {"mean": 7.25}, "schema_pass_rate": 0.5, "evidence_span_exact_match": 0.75}
        ),
        encoding="utf-8",
    )
    metrics = rescore_saved_predictions(gold_path, pred_path, original_path)
    assert metrics["overall"]["tp"] == 0
    assert (metrics["overall"]["fp"], metrics["overall"]["fn"]) == (4, 4)
    for kind in ("symptom", "medication"):
        assert (
            metrics["per_entity_type"][kind]["tp"],
            metrics["per_entity_type"][kind]["fp"],
            metrics["per_entity_type"][kind]["fn"],
        ) == (0, 2, 2)
    assert metrics["latency_ms"] == {"mean": 7.25}
    assert metrics["schema_pass_rate"] == 0.5
    assert metrics["evidence_span_exact_match"] == 0.75


def test_evidence_span_difference_does_not_change_semantic_tp(tmp_path: Path) -> None:
    dataset = tmp_path / "gold.jsonl"
    _write_jsonl(
        dataset,
        [
            {
                "message_id": "a",
                "text": "Сильно болит голова",
                "gold_entities": [
                    {
                        "entity_type": "symptom",
                        "normalized_type": "headache",
                        "polarity": "present",
                        "experiencer": "patient",
                        "temporality": "current",
                        "evidence_span": {"start": 7, "end": 19, "text": "болит голова"},
                    }
                ],
            }
        ],
    )

    class Extractor:
        def extract(
            self, *, message_id: str, patient_id: str, timestamp: datetime, text: str
        ) -> FreeTextExtraction:
            entity = ExtractedEntity(
                type="symptom",
                value={"normalized_type": "headache"},
                evidence_span=EvidenceSpan(start=0, end=19, text=text),
                polarity="present",
                experiencer="patient",
                temporality="current",
            )
            return FreeTextExtraction(
                message_id=message_id,
                patient_id=patient_id,
                timestamp=timestamp,
                original_text=text,
                entities=(entity,),
                model_version="test",
            )

    metrics = evaluate_extractor(Extractor(), dataset).metrics
    assert (metrics["overall"]["tp"], metrics["overall"]["fp"], metrics["overall"]["fn"]) == (1, 0, 0)
    assert metrics["evidence_span_exact_match"] == 0.0
