"""Служебные маршруты: здоровье, метаданные контрактов, сводка правил."""

from typing import Any

from fastapi import APIRouter

from clinical_compass import SCHEMA_VERSION
from clinical_compass.api.deps import PrincipalDep, RuntimeDep
from clinical_compass.domain.enums import Role
from clinical_compass.services.errors import ForbiddenError

router = APIRouter(tags=["system"])

_PATIENT_VOCABULARIES = ("symptom_types", "missed_reasons", "intake_slots", "severity")


@router.get("/health")
def health(runtime: RuntimeDep) -> dict[str, str]:
    return {
        "status": "ok",
        "schema_version": SCHEMA_VERSION,
        "rule_version": runtime.contracts.rules.rule_version,
    }


@router.get("/meta")
def meta(runtime: RuntimeDep) -> dict[str, Any]:
    """Формулировки шкал и подписи справочников — единый источник для приложения."""
    c = runtime.contracts
    return {
        "schema_version": SCHEMA_VERSION,
        "rule_version": c.rules.rule_version,
        "instruments": [d.to_json() for d in c.instruments.values()],
        "vocabulary": {k: c.vocabulary.get(k, {}) for k in _PATIENT_VOCABULARIES},
    }


@router.get("/contracts/rules")
def rules_summary(runtime: RuntimeDep, principal: PrincipalDep) -> dict[str, Any]:
    """Активная конфигурация правил (только чтение)."""
    if principal.role is not Role.DOCTOR:
        raise ForbiddenError("Раздел доступен врачу")
    c = runtime.contracts
    rules = c.rules
    return {
        "schema_version": rules.schema_version,
        "rule_version": rules.rule_version,
        "status": rules.status,
        "templates_version": c.templates_version,
        "questionnaire_default_days": {k.value: v for k, v in rules.questionnaire_default_days.items()},
        "doctor_configurable_schedule": rules.doctor_configurable_schedule,
        "personal_push_default": rules.personal_push_default,
        "urgent_pinned_until_acknowledged": rules.urgent_pinned_until_acknowledged,
        "rules": [
            {
                "id": r.id,
                "title": c.rule_title(r.id),
                "doctor_priority": r.doctor_priority.value,
                "patient_action": r.patient_action.value,
                "message_template_id": r.message_template_id,
                "template_status": t.status if (t := c.template(r.message_template_id)) else None,
                "source": r.source,
                "medical_urgency_classified": r.medical_urgency_classified,
            }
            for r in rules.rules
        ],
    }
