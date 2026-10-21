"""Маршруты администратора записи (§15)."""

from typing import Any

from fastapi import APIRouter

from clinical_compass.api.deps import DepsDep, PrincipalDep
from clinical_compass.api.schemas import BookingUpdateRequest
from clinical_compass.services.admin import AdminService

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/booking-tasks")
def tasks(deps: DepsDep, principal: PrincipalDep) -> list[dict[str, Any]]:
    return AdminService(deps).tasks(principal)


@router.patch("/booking-tasks/{task_id}")
def update_task(
    task_id: str, body: BookingUpdateRequest, deps: DepsDep, principal: PrincipalDep
) -> dict[str, Any]:
    return AdminService(deps).update(principal, task_id, body.status)
