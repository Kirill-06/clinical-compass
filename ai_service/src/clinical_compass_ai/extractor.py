from pydantic import ValidationError

from clinical_compass.domain.extraction import ExtractedEntity, FreeTextExtraction
from clinical_compass.domain.state import EvidenceSpan
from clinical_compass_ai.prompts import PROMPT_VERSION
from clinical_compass_ai.provider import Provider
from clinical_compass_ai.schemas import ExtractRequest, ModelOutput


class ExtractionError(RuntimeError):
    pass


def _validated_output(raw: str, text: str) -> ModelOutput:
    output = ModelOutput.model_validate_json(raw)
    for entity in output.entities:
        span = entity.evidence_span
        if span.end <= span.start or span.end > len(text) or text[span.start : span.end] != span.text:
            if text.count(span.text) != 1:
                raise ValueError("evidence span offsets invalid and exact substring is not unique")
            start = text.index(span.text)
            span.start, span.end = start, start + len(span.text)
    return output


def extract(request: ExtractRequest, provider: Provider, model_version: str) -> FreeTextExtraction:
    error = None
    for attempt in range(2):
        raw = provider.complete(request.text, error)
        try:
            output = _validated_output(raw, request.text)
            break
        except (ValueError, ValidationError) as exc:
            error = str(exc)[:1000]
            if attempt == 1:
                raise ExtractionError("model returned invalid extraction after one repair: " + error) from exc
    entities = []
    for item in output.entities:
        data = item.model_dump(mode="json", exclude_none=True)
        kind = data.pop("entity_type")
        span = EvidenceSpan.model_validate(data.pop("evidence_span"))
        # Compatibility fields required by FreeTextExtraction v0.2, not extra gold labels.
        # Non-symptom entities are admitted only as current patient facts.
        polarity = data.pop("polarity") if kind == "symptom" else "present"
        experiencer = data.pop("experiencer") if kind == "symptom" else "patient"
        temporality = data.pop("temporality") if kind == "symptom" else "current"
        entities.append(
            ExtractedEntity(
                type=kind,
                value=data,
                evidence_span=span,
                polarity=polarity,
                experiencer=experiencer,
                temporality=temporality,
            )
        )
    return FreeTextExtraction(
        message_id=request.message_id,
        patient_id=request.patient_id,
        timestamp=request.timestamp,
        original_text=request.text,
        entities=tuple(entities),
        unknown_fields=tuple(output.unknown_fields),
        model_version=f"{model_version}:{PROMPT_VERSION}",
    )
