"""Окно сервиса внутри МИС (ЕМИАС, 1С:Медицина) и выгрузка сводки в МИС.

Запуск окна устроен по образцу SMART on FHIR «EHR launch»:

1. МИС на своём сервере вызывает `POST /integrations/{system}/launch` со служебным
   ключом и идентификаторами врача и пациента *в своей* системе.
2. Сервис сопоставляет их с внутренними, проверяет закрепление пациента за врачом
   и выдаёт одноразовый код (живёт минуты).
3. МИС открывает окно (iframe, встроенный браузер 1С, вкладка) по адресу
   `/#/embed/launch/{code}`; окно обменивает код на короткую сессию врача.

Сессия получается обычной сессией врача, поэтому все проверки доступа те же,
что и в рабочем месте: окно не даёт видеть чужих пациентов.
"""

import secrets
from datetime import timedelta

from clinical_compass.db.models import LaunchCodeRow
from clinical_compass.domain.enums import ExternalSystem, IdentityKind, Role
from clinical_compass.services.access import AccessPolicy
from clinical_compass.services.auth import AuthService, hash_secret
from clinical_compass.services.context import Deps, Principal
from clinical_compass.services.errors import ForbiddenError, NotFoundError, UnauthorizedError
from clinical_compass.services.fhir import FhirSummaryBuilder
from clinical_compass.services.presenter import Json, iso


def integration_actor(system: ExternalSystem) -> Principal:
    return Principal(f"integration:{system.value}", Role.ADMIN, system.display_name)


class IntegrationService:
    def __init__(
        self,
        deps: Deps,
        *,
        launch_ttl: timedelta = timedelta(minutes=2),
        session_ttl: timedelta = timedelta(minutes=30),
    ) -> None:
        self._d = deps
        self._access = AccessPolicy(deps)
        self._launch_ttl = launch_ttl
        self._session_ttl = session_ttl

    # ------------------------------------------------------------------ запуск окна

    def create_launch(
        self, system: ExternalSystem, *, doctor_external_id: str, patient_external_id: str
    ) -> Json:
        doctor_id = self._resolve(system, IdentityKind.DOCTOR, doctor_external_id, "Врач")
        patient_id = self._resolve(system, IdentityKind.PATIENT, patient_external_id, "Пациент")
        if self._access.doctor_of(patient_id) != doctor_id:
            raise ForbiddenError("Пациент не закреплён за этим врачом в «Клиническом компасе»")
        code = secrets.token_urlsafe(24)
        now = self._d.clock.now()
        expires = now + self._launch_ttl
        self._d.repos.integrations.add_launch(
            LaunchCodeRow(
                code_hash=hash_secret(code),
                system=system.value,
                doctor_id=doctor_id,
                patient_id=patient_id,
                created_at=now,
                expires_at=expires,
                used_at=None,
            )
        )
        self._d.audit(
            integration_actor(system), "integration.launch_created", "patient", patient_id, patient_id
        )
        return {"code": code, "launch_path": f"/#/embed/launch/{code}", "expires_at": iso(expires)}

    def exchange(self, code: str) -> Json:
        """Обменять одноразовый код на сессию врача для встроенного окна."""
        row = self._d.repos.integrations.launch(hash_secret(code))
        now = self._d.clock.now()
        if row is None or row.used_at is not None or row.expires_at <= now:
            raise UnauthorizedError(
                "Ссылка из МИС недействительна или устарела — откройте окно из МИС ещё раз"
            )
        row.used_at = now
        system = ExternalSystem(row.system)
        auth = AuthService(self._d)
        principal = auth.principal_for(row.doctor_id)
        token = auth.open_session(principal, self._session_ttl)
        self._d.audit(
            principal, f"integration.opened_from_{system.value}", "patient", row.patient_id, row.patient_id
        )
        return {
            "token": token,
            "user": principal.to_json(),
            "patient_id": row.patient_id,
            "system": system.value,
            "system_title": system.display_name,
        }

    # ------------------------------------------------------------------ данные для МИС

    def summary(self, system: ExternalSystem, patient_external_id: str) -> Json:
        """Сводка для карты пациента в МИС: FHIR R4 Bundle (шкалы, приверженность, открытые события)."""
        patient_id = self._resolve(system, IdentityKind.PATIENT, patient_external_id, "Пациент")
        self._d.audit(
            integration_actor(system), "integration.summary_read", "patient", patient_id, patient_id
        )
        return FhirSummaryBuilder(self._d).bundle(patient_id)

    def directory(self, system: ExternalSystem) -> Json:
        """Демо-справочник идентификаторов (для стенда, имитирующего МИС)."""
        people, repo = self._d.repos.people, self._d.repos.integrations
        now = self._d.clock.now()
        doctors: list[Json] = []
        for identity in repo.all_identities(system, IdentityKind.DOCTOR):
            doctor = people.doctor(identity.internal_id)
            if doctor is None:
                continue
            patients: list[Json] = []
            for pid in people.patient_ids_of(doctor.id, now):
                patient = people.patient(pid)
                external = next(
                    (i.external_id for i in repo.identities_of(pid) if i.system == system.value), None
                )
                if patient is not None and external is not None:
                    patients.append(
                        {"external_id": external, "name": patient.full_name, "birth_year": patient.birth_year}
                    )
            doctors.append({
                "external_id": identity.external_id,
                "name": doctor.full_name,
                "specialty": doctor.specialty,
                "patients": sorted(patients, key=lambda p: str(p["name"])),
            })  # fmt: skip
        return {"system": system.value, "title": system.display_name, "doctors": doctors}

    def _resolve(self, system: ExternalSystem, kind: IdentityKind, external_id: str, what: str) -> str:
        internal = self._d.repos.integrations.resolve(system, kind, external_id)
        if internal is None:
            raise NotFoundError(f"{what} с идентификатором {system.display_name} «{external_id}» не найден")
        return internal
