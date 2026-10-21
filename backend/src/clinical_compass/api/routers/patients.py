"""Маршруты пациента (§19): опросники, приём, симптомы, сообщения, анализы."""

from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, Response, status

from clinical_compass.api.deps import DepsDep, IdempotencyKey, PrincipalDep
from clinical_compass.api.schemas import (
    IntakeRequest,
    LabRequest,
    MessageRequest,
    QuestionnaireRequest,
    SafetyActionRequest,
    SymptomRequest,
)
from clinical_compass.services.doctors import DoctorService
from clinical_compass.services.errors import InvalidInputError
from clinical_compass.services.patients import PatientService, SymptomReport, Upload
from clinical_compass.services.safety import SafetyService

router = APIRouter(prefix="/patients/{patient_id}", tags=["patient"])

Json = dict[str, Any]


@router.get("/dashboard")
def dashboard(patient_id: str, deps: DepsDep, principal: PrincipalDep) -> Json:
    return PatientService(deps).dashboard(principal, patient_id)


@router.get("/history")
def history(patient_id: str, deps: DepsDep, principal: PrincipalDep) -> Json:
    return PatientService(deps).history(principal, patient_id)


@router.get("/state")
def patient_state(patient_id: str, deps: DepsDep, principal: PrincipalDep) -> Json:
    """Patient State v0.2 и результат проверки по JSON Schema."""
    return DoctorService(deps).patient_state(principal, patient_id)


@router.post("/questionnaires", status_code=status.HTTP_201_CREATED)
def submit_questionnaire(
    patient_id: str,
    body: QuestionnaireRequest,
    deps: DepsDep,
    principal: PrincipalDep,
    key: IdempotencyKey = None,
) -> Json:
    service = PatientService(deps)
    return service.idempotent(
        principal,
        key,
        lambda: service.submit_questionnaire(principal, patient_id, body.instrument, body.item_scores),
    )


@router.post("/intakes", status_code=status.HTTP_201_CREATED)
def mark_intake(patient_id: str, body: IntakeRequest, deps: DepsDep, principal: PrincipalDep) -> Json:
    return PatientService(deps).mark_intake(
        principal,
        patient_id,
        slot_date=body.slot_date,
        slot=body.slot,
        status=body.status,
        missed_reason=body.missed_reason,
    )


@router.post("/symptoms", status_code=status.HTTP_201_CREATED)
def report_symptom(
    patient_id: str, body: SymptomRequest, deps: DepsDep, principal: PrincipalDep, key: IdempotencyKey = None
) -> Json:
    report = SymptomReport(
        type=body.normalized_type,
        phrase=body.patient_phrase,
        affects_daily_life=body.affects_daily_life,
        severity=body.severity,
        worsened_since_start=body.worsened_since_start,
        onset_date=body.onset_date,
    )
    service = PatientService(deps)
    return service.idempotent(principal, key, lambda: service.report_symptom(principal, patient_id, report))


@router.post("/messages", status_code=status.HTTP_201_CREATED)
def send_message(
    patient_id: str, body: MessageRequest, deps: DepsDep, principal: PrincipalDep, key: IdempotencyKey = None
) -> Json:
    try:
        files = [Upload(a.filename, a.mime_type, a.decode()) for a in body.attachments]
    except ValueError as exc:
        raise InvalidInputError(str(exc)) from exc
    service = PatientService(deps)
    return service.idempotent(
        principal, key, lambda: service.send_message(principal, patient_id, body.text, files)
    )


@router.get("/attachments/{attachment_id}")
def download_attachment(
    patient_id: str, attachment_id: str, deps: DepsDep, principal: PrincipalDep
) -> Response:
    row, data = PatientService(deps).attachment(principal, patient_id, attachment_id)
    return Response(
        content=data,
        media_type=row.mime_type,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(row.filename)}"},
    )


@router.post("/labs", status_code=status.HTTP_201_CREATED)
def add_lab(patient_id: str, body: LabRequest, deps: DepsDep, principal: PrincipalDep) -> Json:
    return PatientService(deps).add_lab(principal, patient_id, body.to_body())


@router.post("/safety-actions", status_code=status.HTTP_201_CREATED)
def safety_action(patient_id: str, body: SafetyActionRequest, deps: DepsDep, principal: PrincipalDep) -> Json:
    """Действие пациента с экстренным предупреждением: показано, звонок 112/103, закрыто."""
    return SafetyService(deps).record(principal, patient_id, body.alert_id, body.action)
