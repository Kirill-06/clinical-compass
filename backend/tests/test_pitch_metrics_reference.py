"""Числа медпроверки в публичных слайдах не должны противоречить TP/FP/FN."""

import json
from pathlib import Path


def test_postreview_pitch_metrics_are_internally_consistent() -> None:
    root = Path(__file__).resolve().parents[2]
    data = json.loads((root / "docs/presentation/medical_review_metrics_reference.json").read_text())
    counts = data["overall"]
    tp, fp, fn = counts["tp"], counts["fp"], counts["fn"]
    assert data["dataset"]["gold_entities"] == tp + fn
    precision = tp / (tp + fp)
    recall = tp / (tp + fn)
    f1 = 2 * precision * recall / (precision + recall)
    for key, expected in (("precision", precision), ("recall", recall), ("f1", f1)):
        assert abs(counts[key] - expected) < 1e-6
    assert sum(v["tp"] for v in data["per_entity_type"].values()) == tp
    assert sum(v["fp"] for v in data["per_entity_type"].values()) == fp
    assert sum(v["fn"] for v in data["per_entity_type"].values()) == fn

    local_metrics = root / "evaluation/results/gigachat_v1_2_medical_rc1/metrics.json"
    if local_metrics.exists():
        source = json.loads(local_metrics.read_text())
        assert source["dataset"] == data["dataset"]
        for key in ("tp", "fp", "fn", "precision", "recall", "f1"):
            assert source["overall"][key] == data["overall"][key]
