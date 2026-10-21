"""Алерты, сообщения и вложения, задачи на запись, журнал аудита, ключи идемпотентности."""

from collections.abc import Iterable
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from clinical_compass.db.models import (
    AlertRow,
    AttachmentRow,
    AuditEventRow,
    BookingTaskRow,
    ExtractionRow,
    IdempotencyKeyRow,
    MessageRow,
)
from clinical_compass.domain.enums import AlertStatus


class AlertRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def get(self, alert_id: str) -> AlertRow | None:
        return self._s.get(AlertRow, alert_id)

    def for_patient(self, patient_id: str) -> list[AlertRow]:
        stmt = select(AlertRow).where(AlertRow.patient_id == patient_id).order_by(AlertRow.created_at.desc())
        return list(self._s.scalars(stmt))

    def for_patients(self, patient_ids: Iterable[str], *, include_resolved: bool) -> list[AlertRow]:
        stmt = select(AlertRow).where(AlertRow.patient_id.in_(list(patient_ids)))
        if not include_resolved:
            stmt = stmt.where(AlertRow.status != AlertStatus.RESOLVED.value)
        return list(self._s.scalars(stmt))

    def dedupe_keys(self, patient_id: str) -> set[str]:
        stmt = select(AlertRow.dedupe_key).where(AlertRow.patient_id == patient_id)
        return set(self._s.scalars(stmt))

    def add(self, row: AlertRow) -> None:
        self._s.add(row)


class MessageRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def get(self, message_id: str) -> MessageRow | None:
        return self._s.get(MessageRow, message_id)

    def for_patient(self, patient_id: str) -> list[MessageRow]:
        stmt = (
            select(MessageRow)
            .where(MessageRow.patient_id == patient_id)
            .order_by(MessageRow.created_at.desc())
        )
        return list(self._s.scalars(stmt))

    def attachments(self, message_ids: Iterable[str]) -> dict[str, list[AttachmentRow]]:
        ids = list(message_ids)
        result: dict[str, list[AttachmentRow]] = {i: [] for i in ids}
        if not ids:
            return result
        stmt = (
            select(AttachmentRow).where(AttachmentRow.message_id.in_(ids)).order_by(AttachmentRow.uploaded_at)
        )
        for row in self._s.scalars(stmt):
            result[row.message_id].append(row)
        return result

    def attachment(self, attachment_id: str) -> AttachmentRow | None:
        return self._s.get(AttachmentRow, attachment_id)

    def add(self, *rows: MessageRow | AttachmentRow | ExtractionRow) -> None:
        """Строки записываются в переданном порядке: родитель раньше дочерних (связей ORM нет)."""
        for row in rows:
            self._s.add(row)
            self._s.flush()


class BookingRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def get(self, task_id: str) -> BookingTaskRow | None:
        return self._s.get(BookingTaskRow, task_id)

    def all(self) -> list[BookingTaskRow]:
        return list(self._s.scalars(select(BookingTaskRow).order_by(BookingTaskRow.deadline)))

    def for_patient(self, patient_id: str) -> list[BookingTaskRow]:
        stmt = (
            select(BookingTaskRow)
            .where(BookingTaskRow.patient_id == patient_id)
            .order_by(BookingTaskRow.deadline)
        )
        return list(self._s.scalars(stmt))

    def add(self, row: BookingTaskRow) -> None:
        self._s.add(row)


class AuditRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def record(
        self,
        *,
        at: datetime,
        actor: str,
        action: str,
        entity: str,
        entity_id: str,
        patient_id: str | None,
    ) -> None:
        self._s.add(
            AuditEventRow(
                at=at, actor=actor, action=action, entity=entity, entity_id=entity_id, patient_id=patient_id
            )
        )

    def for_patient(self, patient_id: str, limit: int = 500) -> list[AuditEventRow]:
        stmt = (
            select(AuditEventRow)
            .where(AuditEventRow.patient_id == patient_id)
            .order_by(AuditEventRow.at.desc(), AuditEventRow.id.desc())
            .limit(limit)
        )
        return list(self._s.scalars(stmt))

    def for_entity(self, entity: str, entity_id: str) -> list[AuditEventRow]:
        stmt = (
            select(AuditEventRow)
            .where(AuditEventRow.entity == entity, AuditEventRow.entity_id == entity_id)
            .order_by(AuditEventRow.at.desc(), AuditEventRow.id.desc())
        )
        return list(self._s.scalars(stmt))

    def last_at(self, entity: str, entity_id: str) -> datetime | None:
        stmt = (
            select(AuditEventRow.at)
            .where(AuditEventRow.entity == entity, AuditEventRow.entity_id == entity_id)
            .order_by(AuditEventRow.at.desc())
        )
        return self._s.scalars(stmt).first()


class IdempotencyRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def get(self, key: str) -> dict[str, Any] | None:
        row = self._s.get(IdempotencyKeyRow, key)
        return row.response if row else None

    def save(self, key: str, response: dict[str, Any], now: datetime) -> None:
        self._s.add(IdempotencyKeyRow(key=key, response=response, created_at=now))
