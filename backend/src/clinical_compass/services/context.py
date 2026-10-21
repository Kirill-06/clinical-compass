"""Зависимости сценариев: время клиники, хранилище файлов, репозитории, контракты."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from sqlalchemy.orm import Session

from clinical_compass.domain.contracts import Contracts
from clinical_compass.domain.enums import Role
from clinical_compass.domain.extraction import Extractor
from clinical_compass.repositories.care import CareRepository
from clinical_compass.repositories.facts import FactsRepository
from clinical_compass.repositories.people import PeopleRepository
from clinical_compass.repositories.workflow import (
    AlertRepository,
    AuditRepository,
    BookingRepository,
    IdempotencyRepository,
    MessageRepository,
)


class ClinicClock:
    """Время клиники. Моменты — в UTC, календарные даты слотов — в поясе клиники."""

    def __init__(self, utc_offset_hours: int = 3, now: Callable[[], datetime] | None = None) -> None:
        self.utc_offset_hours = utc_offset_hours
        self._now = now or (lambda: datetime.now(UTC))

    def now(self) -> datetime:
        return self._now().astimezone(UTC)

    def local_now(self) -> datetime:
        return self.now() + timedelta(hours=self.utc_offset_hours)

    def today(self) -> date:
        return self.local_now().date()

    def at(self, moment: datetime) -> "ClinicClock":
        """Те же часы, остановленные в момент `moment` (загрузка демо-данных «в прошлом»)."""
        return ClinicClock(self.utc_offset_hours, lambda: moment)


class BlobStorage(Protocol):
    """Хранилище содержимого вложений. Локальный диск сейчас, объектное хранилище потом."""

    def put(self, key: str, data: bytes) -> None: ...

    def get(self, key: str) -> bytes | None: ...


class LocalBlobStorage:
    def __init__(self, directory: Path) -> None:
        self._dir = directory
        self._dir.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        # Ключи генерирует сервер, но защищаемся от выхода за пределы каталога.
        safe = Path(key).name
        return self._dir / safe

    def put(self, key: str, data: bytes) -> None:
        self._path(key).write_bytes(data)

    def get(self, key: str) -> bytes | None:
        path = self._path(key)
        return path.read_bytes() if path.exists() else None


class MemoryBlobStorage:
    def __init__(self) -> None:
        self._items: dict[str, bytes] = {}

    def put(self, key: str, data: bytes) -> None:
        self._items[key] = data

    def get(self, key: str) -> bytes | None:
        return self._items.get(key)


@dataclass(frozen=True)
class Principal:
    """Кто выполняет запрос. Определяется сервером по сессии."""

    user_id: str
    role: Role
    name: str

    def to_json(self) -> dict[str, str]:
        return {"id": self.user_id, "role": self.role.value, "name": self.name}


SYSTEM = Principal(user_id="system", role=Role.ADMIN, name="Система")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:20]}"


@dataclass(frozen=True)
class Repositories:
    people: PeopleRepository
    facts: FactsRepository
    care: CareRepository
    alerts: AlertRepository
    messages: MessageRepository
    bookings: BookingRepository
    audit: AuditRepository
    idempotency: IdempotencyRepository

    @classmethod
    def of(cls, session: Session) -> "Repositories":
        return cls(
            people=PeopleRepository(session),
            facts=FactsRepository(session),
            care=CareRepository(session),
            alerts=AlertRepository(session),
            messages=MessageRepository(session),
            bookings=BookingRepository(session),
            audit=AuditRepository(session),
            idempotency=IdempotencyRepository(session),
        )


@dataclass(frozen=True)
class Limits:
    max_text_length: int = 2000
    max_phrase_length: int = 1000
    max_file_bytes: int = 10 * 1024 * 1024
    max_files: int = 5
    intake_backfill_days: int = 2
    """На сколько дней назад пациент может отметить или исправить приём."""
    mime_types: frozenset[str] = frozenset(
        {"application/pdf", "image/jpeg", "image/png", "image/heic", "text/plain"}
    )


@dataclass(frozen=True)
class Deps:
    session: Session
    repos: Repositories
    contracts: Contracts
    clock: ClinicClock
    extractor: Extractor
    storage: BlobStorage
    limits: Limits

    def with_clock(self, clock: ClinicClock) -> "Deps":
        return Deps(
            self.session, self.repos, self.contracts, clock, self.extractor, self.storage, self.limits
        )

    def audit(
        self, actor: Principal, action: str, entity: str, entity_id: str, patient_id: str | None
    ) -> None:
        self.repos.audit.record(
            at=self.clock.now(),
            actor=actor.user_id,
            action=action,
            entity=entity,
            entity_id=entity_id,
            patient_id=patient_id,
        )
