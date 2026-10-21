"""Сессии и демо-вход.

Демо-вход выдаёт сессию по id без пароля (`CC_DEMO_AUTH=false` его отключает).
Production-аутентификация подключается здесь же: она должна создавать ту же
сессию, а проверка ролей и связей врач–пациент от неё не зависит.
"""

import hashlib
import secrets
from collections import Counter
from datetime import timedelta

from clinical_compass.db.models import SessionRow
from clinical_compass.domain.enums import Role
from clinical_compass.services.context import Deps, Principal
from clinical_compass.services.errors import NotFoundError, UnauthorizedError
from clinical_compass.services.presenter import Json


def hash_secret(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class AuthService:
    def __init__(self, deps: Deps, session_ttl_hours: int = 12) -> None:
        self._d = deps
        self._ttl = timedelta(hours=session_ttl_hours)

    def principal_for(self, user_id: str) -> Principal:
        people = self._d.repos.people
        if doctor := people.doctor(user_id):
            return Principal(user_id, Role.DOCTOR, doctor.short_name)
        if patient := people.patient(user_id):
            return Principal(user_id, Role.PATIENT, patient.full_name)
        if admin := people.admin(user_id):
            return Principal(user_id, Role.ADMIN, admin.full_name)
        raise NotFoundError("Пользователь не найден")

    def login(self, user_id: str) -> tuple[str, Principal]:
        principal = self.principal_for(user_id)
        return self.open_session(principal, self._ttl), principal

    def open_session(self, principal: Principal, ttl: timedelta) -> str:
        """Выдать токен сессии. В базе хранится только его хэш."""
        token = secrets.token_urlsafe(32)
        now = self._d.clock.now()
        self._d.repos.people.add_session(
            SessionRow(
                token_hash=hash_secret(token),
                user_id=principal.user_id,
                role=principal.role.value,
                created_at=now,
                expires_at=now + ttl,
            )
        )
        self._d.audit(principal, "session.created", "session", principal.user_id, None)
        return token

    def authenticate(self, token: str | None) -> Principal:
        if not token:
            raise UnauthorizedError("Требуется вход")
        row = self._d.repos.people.session_by_hash(hash_secret(token))
        if row is None or row.expires_at <= self._d.clock.now():
            raise UnauthorizedError("Сессия истекла, войдите снова")
        return self.principal_for(row.user_id)

    def demo_accounts(self) -> Json:
        people, now = self._d.repos.people, self._d.clock.now()
        doctors = {d.id: d for d in people.all_doctors()}
        patients = people.all_patients()
        doctor_of = {p.id: people.doctor_of(p.id, now) for p in patients}
        counts = Counter(doctor_of.values())
        return {
            "doctors": [
                {"id": d.id, "name": d.full_name, "subtitle": f"{d.specialty} · пациентов: {counts[d.id]}"}
                for d in doctors.values()
            ],
            "patients": [
                {
                    "id": p.id,
                    "name": p.full_name,
                    "subtitle": f"{p.display_id} · врач "
                    f"{doctors[doc].short_name if (doc := doctor_of[p.id]) in doctors else '—'}",
                }
                for p in patients
            ],
            "admins": [
                {"id": a.id, "name": a.full_name, "subtitle": "Администратор записи"}
                for a in people.all_admins()
            ],
        }
