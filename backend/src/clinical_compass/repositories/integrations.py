"""Сопоставление идентификаторов внешних МИС и коды запуска окна."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from clinical_compass.db.models import ExternalIdentityRow, LaunchCodeRow
from clinical_compass.domain.enums import ExternalSystem, IdentityKind


class IntegrationRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def resolve(self, system: ExternalSystem, kind: IdentityKind, external_id: str) -> str | None:
        """Внутренний id по идентификатору во внешней системе."""
        stmt = select(ExternalIdentityRow.internal_id).where(
            ExternalIdentityRow.system == system.value,
            ExternalIdentityRow.kind == kind.value,
            ExternalIdentityRow.external_id == external_id,
        )
        return self._s.scalars(stmt).first()

    def identities_of(self, internal_id: str) -> list[ExternalIdentityRow]:
        stmt = select(ExternalIdentityRow).where(ExternalIdentityRow.internal_id == internal_id)
        return list(self._s.scalars(stmt.order_by(ExternalIdentityRow.system)))

    def all_identities(self, system: ExternalSystem, kind: IdentityKind) -> list[ExternalIdentityRow]:
        stmt = select(ExternalIdentityRow).where(
            ExternalIdentityRow.system == system.value, ExternalIdentityRow.kind == kind.value
        )
        return list(self._s.scalars(stmt.order_by(ExternalIdentityRow.external_id)))

    def add_identity(self, row: ExternalIdentityRow) -> None:
        self._s.add(row)
        self._s.flush()

    def add_launch(self, row: LaunchCodeRow) -> None:
        self._s.add(row)

    def launch(self, code_hash: str) -> LaunchCodeRow | None:
        return self._s.get(LaunchCodeRow, code_hash)
