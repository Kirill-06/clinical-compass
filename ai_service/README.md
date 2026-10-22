# Clinical Compass AI extraction

The service converts patient free text to the backend's existing `FreeTextExtraction` v0.2 JSON. It does not make clinical decisions, set doctor priority or patient action, or produce advice. The provider is an OpenAI-compatible Chat Completions endpoint; the extraction and validation code is separate from its HTTP transport.

## Setup and run

From the repository root:

```bash
cd ai_service
export AI_MODEL='your-model-id'
export AI_API_KEY='your-secret-key'
export AI_BASE_URL='https://api.openai.com/v1'  # optional compatible endpoint
UV_CACHE_DIR=/tmp/uv-cache uv run uvicorn clinical_compass_ai.main:app --host 127.0.0.1 --port 8090
```

`AI_MODEL` and `AI_API_KEY` are required for `/extract`. `GET /health` remains available without them. `AI_TIMEOUT_SECONDS` defaults to 15. The service makes one repair attempt for malformed model output and returns HTTP 502 if validation still fails. Provider failures return HTTP 502; missing configuration returns HTTP 503. Keep credentials in the environment, not in git.

Example request:

```bash
curl -X POST http://127.0.0.1:8090/extract -H 'Content-Type: application/json' -d '{"message_id":"m1","patient_id":"p1","timestamp":"2026-10-22T12:00:00Z","text":"Болит голова","schema_version":"0.2.0"}'
```

The response is a full `FreeTextExtraction`. Each entity has exact source offsets. A unique exact substring may repair incorrect offsets. Ambiguous or absent evidence causes an extraction error. The model output must use the annotation v0.2 entity vocabulary. Only symptom annotations carry `polarity`, `experiencer`, and `temporality`. The adapter fills these fields for other entity types in the backend transport contract.

## Tests

```bash
cd ai_service
UV_CACHE_DIR=/tmp/uv-cache uv run pytest
cd ../backend
PYTHONPATH=src uv run pytest
```

## Real model evaluation

With the service running on port 8090:

```bash
cd backend
export CC_EXTRACTOR_MODE=remote
export CC_EXTRACTOR_URL=http://127.0.0.1:8090/extract
PYTHONPATH=src uv run clinical-compass evaluate-extractor ../evaluation/data/generated_annotations.v1.1.jsonl --out-dir ../evaluation/out
```

The existing evaluator writes `evaluation/out/predictions.jsonl` and `evaluation/out/metrics.json`. Its outputs should be reviewed before any clinical use. The first real run requires reachable provider credentials and an API implementing OpenAI-compatible `/chat/completions` with JSON response format.

## Contract caveat

The annotation schema does not carry polarity, experiencer, or temporality on medication, risk, and lab entities, while `ExtractedEntity` requires them. The adapter supplies `present`, `patient`, and `current` for medication, risk, and lab entities after semantic extraction. These are transport compatibility fields, not gold labels. Patient State now accepts medication `slot=unknown` without inferring morning or evening.
