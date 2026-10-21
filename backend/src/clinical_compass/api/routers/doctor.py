"""Маршруты врача (§19): пациенты, очередь, карточка, решения."""

from typing import Any

from fastapi import APIRouter, status

from clinical_compass.api.deps import DepsDep, PrincipalDep
from clinical_compass.api.schemas import ContactDeadlineRequest, RoutingRequest, ScheduleRequest
from clinical_compass.domain.enums import Instrument
from clinical_compass.services.doctors import DoctorService

router = APIRouter(prefix="/doctor", tags=["doctor"])

Json = dict[str, Any]


@router.get("/patients")
def patients(deps: DepsDep, principal: PrincipalDep) -> list[Json]:
    return DoctorService(deps).patients(principal)


@router.get("/queue")
def queue(deps: DepsDep, principal: PrincipalDep, include_resolved: bool = False) -> list[Json]:
    return DoctorService(deps).queue(principal, include_resolved=include_resolved)


@router.get("/patients/{patient_id}/timeline")
def dossier(patient_id: str, deps: DepsDep, principal: PrincipalDep) -> Json:
    return DoctorService(deps).dossier(principal, patient_id)


@router.get("/patients/{patient_id}/audit")
def audit(patient_id: str, deps: DepsDep, principal: PrincipalDep) -> list[Json]:
    return DoctorService(deps).audit(principal, patient_id)


@router.post("/alerts/{alert_id}/{action}")
def alert_action(alert_id: str, action: str, deps: DepsDep, principal: PrincipalDep) -> Json:
    return DoctorService(deps).alert_action(principal, alert_id, action)


@router.put("/patients/{patient_id}/questionnaire-schedules/{instrument}")
def set_schedule(
    patient_id: str, instrument: Instrument, body: ScheduleRequest, deps: DepsDep, principal: PrincipalDep
) -> Json:
    return DoctorService(deps).set_schedule(
        principal, patient_id, instrument, body.interval_days, body.active
    )


@router.post("/patients/{patient_id}/routing")
def set_routing(patient_id: str, body: RoutingRequest, deps: DepsDep, principal: PrincipalDep) -> Json:
    return DoctorService(deps).set_routing(principal, patient_id, body.decision)


@router.post("/patients/{patient_id}/contact-deadline", status_code=status.HTTP_201_CREATED)
def set_contact_deadline(
    patient_id: str, body: ContactDeadlineRequest, deps: DepsDep, principal: PrincipalDep
) -> Json:
    return DoctorService(deps).set_contact_deadline(principal, patient_id, body.deadline)
