"""Внутренние эндпоинты AI-слоя (§16, §19). Только со служебным ключом X-Internal-Token."""

from typing import Any

from fastapi import APIRouter, Depends, status

from clinical_compass.api.deps import DepsDep, require_internal
from clinical_compass.api.schemas import (
    ClinicalProfileRequest,
    EvaluateRulesRequest,
    ExtractRequest,
    FactsRequest,
)
from clinical_compass.domain.rules import RuleContext
from clinical_compass.services.internal import InternalService

router = APIRouter(prefix="/internal", tags=["internal"], dependencies=[Depends(require_internal)])


@router.post("/extract")
def extract(body: ExtractRequest, deps: DepsDep) -> dict[str, Any]:
    """Текст → FreeTextExtraction v0.2 (сейчас заглушка-лексикон)."""
    return InternalService(deps).extract(body.patient_id, body.text)


@router.post("/evaluate-rules")
def evaluate_rules(body: EvaluateRulesRequest, deps: DepsDep) -> list[dict[str, Any]]:
    """Patient State → RuleResult[]. Чистая функция, ничего не сохраняет."""
    ctx = body.context
    context = RuleContext(sex=ctx.sex, route_review_needed=ctx.route_review_needed) if ctx else RuleContext()
    return InternalService(deps).evaluate_rules(body.patient_state, context)


@router.post("/patients/{patient_id}/facts", status_code=status.HTTP_201_CREATED)
def ingest_facts(patient_id: str, body: FactsRequest, deps: DepsDep) -> dict[str, Any]:
    """Факты от AI-слоя: `{"extraction": …}` или фрагмент Patient State."""
    return InternalService(deps).ingest_facts(patient_id, body.model_dump(exclude_none=True))


@router.post("/patients/{patient_id}/clinical-profile")
def clinical_profile(patient_id: str, body: ClinicalProfileRequest, deps: DepsDep) -> dict[str, Any]:
    return InternalService(deps).set_clinical_profile(
        patient_id, route_review_needed=body.route_review_needed
    )
