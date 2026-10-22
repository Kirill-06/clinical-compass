# Evaluation assets

`generated_annotations.v1.1.jsonl` — development/evaluation seed for the free-text extraction layer.
It is intentionally evaluated separately from deterministic clinical rules.

Run the same extractor used by the application:

```bash
cd backend
PYTHONPATH=src uv run clinical-compass evaluate-extractor ../evaluation/data/generated_annotations.v1.1.jsonl --out-dir ../evaluation/out
```

Outputs:
- `evaluation/out/metrics.json`
- `evaluation/out/predictions.jsonl`

With the default `CC_EXTRACTOR_MODE=mock` this evaluates the lexicon stub.  In the AI branch set
`CC_EXTRACTOR_MODE=remote` and `CC_EXTRACTOR_URL` to evaluate the real model service without changing
patient/doctor code.
