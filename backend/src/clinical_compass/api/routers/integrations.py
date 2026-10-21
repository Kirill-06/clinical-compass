"""Интеграция с МИС: окно сервиса внутри ЕМИАС / 1С:Медицина и выгрузка сводки (FHIR R4)."""

from datetime import timedelta
from typing import Any

from fastapi import APIRouter, status

from clinical_compass.api.deps import DepsDep, IntegrationSystem, RuntimeDep
from clinical_compass.api.schemas import LaunchExchangeRequest, LaunchRequest
from clinical_compass.domain.enums import ExternalSystem
from clinical_compass.services.context import Deps
from clinical_compass.services.errors import NotFoundError
from clinical_compass.services.integrations import IntegrationService

router = APIRouter(prefix="/integrations", tags=["integrations"])


def _service(deps: Deps, runtime: RuntimeDep) -> IntegrationService:
    settings = runtime.settings
    return IntegrationService(
        deps,
        launch_ttl=timedelta(seconds=settings.launch_code_seconds),
        session_ttl=timedelta(minutes=settings.embed_session_minutes),
    )


@router.post("/{system}/launch", status_code=status.HTTP_201_CREATED)
def create_launch(
    system: IntegrationSystem, body: LaunchRequest, deps: DepsDep, runtime: RuntimeDep
) -> dict[str, Any]:
    """Сервер МИС → одноразовый код окна для пары врач–пациент (идентификаторы МИС)."""
    return _service(deps, runtime).create_launch(
        system, doctor_external_id=body.doctor_external_id, patient_external_id=body.patient_external_id
    )


@router.post("/launch/exchange")
def exchange_launch(body: LaunchExchangeRequest, deps: DepsDep, runtime: RuntimeDep) -> dict[str, Any]:
    """Окно в МИС → сессия врача по одноразовому коду."""
    return _service(deps, runtime).exchange(body.code)


@router.get("/{system}/patients/{patient_external_id}/summary")
def summary(
    system: IntegrationSystem, patient_external_id: str, deps: DepsDep, runtime: RuntimeDep
) -> dict[str, Any]:
    """Сводка для карты пациента в МИС: FHIR R4 Bundle."""
    return _service(deps, runtime).summary(system, patient_external_id)


# --- Демо-стенд, имитирующий МИС (только при CC_DEMO_AUTH=true) ------------------------------------


def _require_demo(runtime: RuntimeDep) -> None:
    if not runtime.settings.demo_auth:
        raise NotFoundError("Демо-стенд МИС отключён")


@router.get("/demo/{system}/directory", tags=["demo"])
def demo_directory(system: ExternalSystem, deps: DepsDep, runtime: RuntimeDep) -> dict[str, Any]:
    _require_demo(runtime)
    return _service(deps, runtime).directory(system)


@router.post("/demo/{system}/launch", tags=["demo"], status_code=status.HTTP_201_CREATED)
def demo_launch(
    system: ExternalSystem, body: LaunchRequest, deps: DepsDep, runtime: RuntimeDep
) -> dict[str, Any]:
    """То же, что `/{system}/launch`, но без ключа: им пользуется страница-имитация МИС."""
    _require_demo(runtime)
    return _service(deps, runtime).create_launch(
        system, doctor_external_id=body.doctor_external_id, patient_external_id=body.patient_external_id
    )
