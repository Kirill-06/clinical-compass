"""Переписка пациента с врачом и подключение к Centrifugo для доставки в реальном времени."""

from datetime import timedelta
from typing import Any

from fastapi import APIRouter, status

from clinical_compass.api.deps import DepsDep, PrincipalDep, RuntimeDep
from clinical_compass.api.schemas import DoctorMessageRequest
from clinical_compass.services.chat import ChatService

router = APIRouter(tags=["chat"])

Json = dict[str, Any]
_CONNECTION_TOKEN_TTL = timedelta(hours=1)
"""Клиент запрашивает новый токен сам, когда старый истекает."""


@router.get("/patients/{patient_id}/chat")
def thread(patient_id: str, deps: DepsDep, principal: PrincipalDep) -> Json:
    """Переписка по порядку. Только чтение."""
    return ChatService(deps).thread(principal, patient_id)


@router.post("/patients/{patient_id}/chat/read")
def mark_read(patient_id: str, deps: DepsDep, principal: PrincipalDep) -> Json:
    """Сообщения собеседника прочитаны: переписка открыта на экране."""
    return ChatService(deps).mark_read(principal, patient_id)


@router.post("/doctor/patients/{patient_id}/messages", status_code=status.HTTP_201_CREATED)
def doctor_reply(patient_id: str, body: DoctorMessageRequest, deps: DepsDep, principal: PrincipalDep) -> Json:
    return ChatService(deps).doctor_reply(principal, patient_id, body.text)


@router.get("/realtime/connection")
def connection(deps: DepsDep, principal: PrincipalDep, runtime: RuntimeDep) -> Json:
    """Адрес Centrifugo и токен с разрешёнными каналами; `{"enabled": false}`, если не настроен."""
    return ChatService(deps).connection(principal, runtime.realtime, _CONNECTION_TOKEN_TTL)
