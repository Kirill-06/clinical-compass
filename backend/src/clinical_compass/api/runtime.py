"""Объекты, живущие всё время работы процесса: настройки, контракты, БД, хранилище."""

from dataclasses import dataclass
from datetime import UTC

from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from clinical_compass.config import Settings
from clinical_compass.db.session import make_engine, make_session_factory
from clinical_compass.domain.contracts import Contracts, load_contracts
from clinical_compass.domain.extraction import Extractor, MockLexiconExtractor
from clinical_compass.services.context import (
    BlobStorage,
    ClinicClock,
    Deps,
    Limits,
    LocalBlobStorage,
    Repositories,
)


@dataclass(frozen=True)
class Runtime:
    settings: Settings
    contracts: Contracts
    engine: Engine
    session_factory: sessionmaker[Session]
    clock: ClinicClock
    extractor: Extractor
    storage: BlobStorage
    limits: Limits

    @classmethod
    def build(
        cls,
        settings: Settings,
        *,
        extractor: Extractor | None = None,
        storage: BlobStorage | None = None,
    ) -> "Runtime":
        engine = make_engine(settings.database_url)
        fixed = settings.fixed_now
        clock = ClinicClock(
            settings.clinic_utc_offset_hours,
            (lambda: fixed.astimezone(UTC)) if fixed else None,
        )
        return cls(
            settings=settings,
            contracts=load_contracts(settings.contracts_dir),
            engine=engine,
            session_factory=make_session_factory(engine),
            clock=clock,
            extractor=extractor or MockLexiconExtractor(),
            storage=storage or LocalBlobStorage(settings.storage_dir),
            limits=Limits(max_file_bytes=settings.max_upload_bytes, max_files=settings.max_files_per_message),
        )

    def deps(self, session: Session) -> Deps:
        return Deps(
            session=session,
            repos=Repositories.of(session),
            contracts=self.contracts,
            clock=self.clock,
            extractor=self.extractor,
            storage=self.storage,
            limits=self.limits,
        )
