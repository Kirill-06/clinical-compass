"""Evaluation harness for free-text extraction against annotation_v0.2 JSONL.

The evaluator deliberately measures extraction only.  Clinical rule correctness
is tested separately by the deterministic rule-engine tests.
"""

from __future__ import annotations

import json
import math
import statistics
import time
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from clinical_compass.domain.extraction import ExtractedEntity, Extractor, FreeTextExtraction

Json = dict[str, Any]


@dataclass(frozen=True)
class EvalResult:
    metrics: Json
    predictions: list[Json]


def _primary_label(entity: Json) -> tuple[Any, ...]:
    kind = entity.get("entity_type") or entity.get("type")
    if kind == "symptom":
        return (
            kind,
            entity.get("normalized_type"),
            entity.get("polarity"),
            entity.get("experiencer"),
            entity.get("temporality"),
        )
    if kind == "medication":
        return (kind, entity.get("status"), entity.get("slot"), entity.get("missed_reason"))
    if kind == "risk_signal":
        return (kind, entity.get("risk_type") or entity.get("type_value") or entity.get("signal_type"))
    if kind == "lab_mention":
        return (kind, entity.get("analyte"), entity.get("value"), entity.get("unit"))
    return (kind,)


def _gold_to_flat(entity: Json) -> Json:
    result = dict(entity)
    if result.get("entity_type") == "risk_signal":
        # In annotation_v0.2, `type` is the risk label while entity_type carries the class.
        result["risk_type"] = result.get("type")
    return result


def _prediction_to_flat(entity: ExtractedEntity) -> Json:
    value = dict(entity.value)
    result: Json = {
        "entity_type": entity.type,
        **value,
        "evidence_span": entity.evidence_span.model_dump(mode="json"),
        "polarity": entity.polarity.value,
        "experiencer": entity.experiencer.value,
        "temporality": entity.temporality.value,
    }
    if entity.type == "risk_signal":
        result["risk_type"] = value.get("type")
        result.pop("type", None)
    return result


def _counter_metrics(gold: Counter[tuple[Any, ...]], pred: Counter[tuple[Any, ...]]) -> tuple[int, int, int]:
    tp = sum((gold & pred).values())
    fp = sum((pred - gold).values())
    fn = sum((gold - pred).values())
    return tp, fp, fn


def _prf(tp: int, fp: int, fn: int) -> Json:
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": round(precision, 6),
        "recall": round(recall, 6),
        "f1": round(f1, 6),
    }


def _percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    pos = (len(ordered) - 1) * q
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return ordered[lo]
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (pos - lo)


def _span_key(entity: Json) -> tuple[Any, ...] | None:
    span = entity.get("evidence_span")
    if not isinstance(span, dict):
        return None
    return (span.get("start"), span.get("end"), span.get("text"))


def _read_rows(dataset_path: Path) -> list[Json]:
    rows: list[Json] = []
    with dataset_path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _count_exact_spans(gold_entities: list[Json], pred_entities: list[Json]) -> tuple[int, int]:
    """Pair matching semantic labels once each, then compare their evidence spans."""
    exact_span_hits = 0
    matched_for_span = 0
    remaining = list(pred_entities)
    for gold in gold_entities:
        key = _primary_label(gold)
        match_index = next((i for i, pred in enumerate(remaining) if _primary_label(pred) == key), None)
        if match_index is None:
            continue
        pred = remaining.pop(match_index)
        matched_for_span += 1
        if _span_key(gold) == _span_key(pred):
            exact_span_hits += 1
    return exact_span_hits, matched_for_span


def _semantic_metrics(rows: list[Json], predictions: list[Json]) -> Json:
    """Match semantic labels within each message before aggregating counts."""
    if len(rows) != len(predictions):
        raise ValueError("Gold and prediction row counts differ")
    totals: Counter[str] = Counter()
    per_type_counts: Counter[tuple[str, str]] = Counter()
    gold_count = 0
    pred_count = 0
    for row, prediction in zip(rows, predictions, strict=True):
        if row["message_id"] != prediction["message_id"] or row["text"] != prediction["text"]:
            raise ValueError(f"Gold and prediction rows differ at {row['message_id']}")
        gold = Counter(_primary_label(_gold_to_flat(e)) for e in row.get("gold_entities", []))
        pred = Counter(_primary_label(e) for e in prediction["predicted_entities"])
        gold_count += sum(gold.values())
        pred_count += sum(pred.values())
        row_tp, row_fp, row_fn = _counter_metrics(gold, pred)
        totals.update({"tp": row_tp, "fp": row_fp, "fn": row_fn})
        for outcome, matches in (("tp", gold & pred), ("fp", pred - gold), ("fn", gold - pred)):
            for label, count in matches.items():
                per_type_counts[str(label[0]), outcome] += count
    kinds = sorted(kind for kind, _ in per_type_counts)
    per_type = {
        kind: _prf(*(per_type_counts[kind, outcome] for outcome in ("tp", "fp", "fn")))
        for kind in dict.fromkeys(kinds)
    }
    return {
        "dataset": {"messages": len(rows), "gold_entities": gold_count},
        "overall": _prf(totals["tp"], totals["fp"], totals["fn"]),
        "per_entity_type": per_type,
        "risk_recall": per_type.get("risk_signal", _prf(0, 0, 0))["recall"],
        "hallucination_rate": round(totals["fp"] / pred_count, 6) if pred_count else 0.0,
    }


def evaluate_extractor(extractor: Extractor, dataset_path: Path) -> EvalResult:
    rows = _read_rows(dataset_path)

    latencies_ms: list[float] = []
    predictions: list[Json] = []
    valid = 0
    failures = 0
    exact_span_hits = 0
    matched_for_span = 0

    for index, row in enumerate(rows):
        message_id = str(row["message_id"])
        text = str(row["text"])
        gold_entities = [_gold_to_flat(e) for e in row.get("gold_entities", [])]

        started = time.perf_counter()
        try:
            extraction: FreeTextExtraction = extractor.extract(
                message_id=message_id,
                patient_id="eval-patient",
                timestamp=datetime(2026, 10, 22, 12, 0, index % 60, tzinfo=UTC),
                text=text,
            )
        except Exception as exc:  # evaluation must record model/provider failures, not abort the run
            latency = (time.perf_counter() - started) * 1000
            latencies_ms.append(latency)
            failures += 1
            predictions.append(
                {
                    "message_id": message_id,
                    "text": text,
                    "error": f"{type(exc).__name__}: {exc}",
                    "latency_ms": round(latency, 3),
                    "predicted_entities": [],
                }
            )
            pred_entities: list[Json] = []
        else:
            latency = (time.perf_counter() - started) * 1000
            latencies_ms.append(latency)
            valid += 1
            pred_entities = [_prediction_to_flat(e) for e in extraction.entities]
            predictions.append(
                {
                    "message_id": message_id,
                    "text": text,
                    "latency_ms": round(latency, 3),
                    "model_version": extraction.model_version,
                    "predicted_entities": pred_entities,
                    "unknown_fields": list(extraction.unknown_fields),
                    "clarifying_questions": list(extraction.clarifying_questions),
                }
            )

        # Evidence-span accuracy only among entities whose semantic label can be paired exactly.
        row_exact_hits, row_matched = _count_exact_spans(gold_entities, pred_entities)
        exact_span_hits += row_exact_hits
        matched_for_span += row_matched

    metrics: Json = {
        **_semantic_metrics(rows, predictions),
        "schema_pass_rate": round(valid / len(rows), 6) if rows else 1.0,
        "failed_messages": failures,
        "evidence_span_exact_match": (
            round(exact_span_hits / matched_for_span, 6) if matched_for_span else None
        ),
        "latency_ms": {
            "mean": round(statistics.fmean(latencies_ms), 3) if latencies_ms else None,
            "p50": round(_percentile(latencies_ms, 0.50) or 0.0, 3) if latencies_ms else None,
            "p95": round(_percentile(latencies_ms, 0.95) or 0.0, 3) if latencies_ms else None,
        },
    }
    return EvalResult(metrics=metrics, predictions=predictions)


def rescore_saved_predictions(
    dataset_path: Path, predictions_path: Path, original_metrics_path: Path
) -> Json:
    """Correct semantic counts from saved predictions; retain unrounded runtime metrics."""
    rows = _read_rows(dataset_path)
    predictions = _read_rows(predictions_path)
    original = json.loads(original_metrics_path.read_text(encoding="utf-8"))
    return {**original, **_semantic_metrics(rows, predictions)}


def write_eval_outputs(result: EvalResult, *, metrics_path: Path, predictions_path: Path) -> None:
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    predictions_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.write_text(json.dumps(result.metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with predictions_path.open("w", encoding="utf-8") as handle:
        for row in result.predictions:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
