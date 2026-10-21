"""Фабрика приложения FastAPI.

Запуск: `uvicorn clinical_compass.main:app` (или `clinical-compass serve`).
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from clinical_compass import SCHEMA_VERSION
from clinical_compass.api.errors import install_error_handlers
from clinical_compass.api.routers import admin, auth, doctor, internal, patients, system
from clinical_compass.api.runtime import Runtime
from clinical_compass.config import Settings, get_settings
from clinical_compass.db.migrations import upgrade_to_head
from clinical_compass.seed import seed_if_empty

logger = logging.getLogger("clinical_compass")


def create_app(settings: Settings | None = None, runtime: Runtime | None = None) -> FastAPI:
    settings = settings or get_settings()
    runtime = runtime or Runtime.build(settings)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        upgrade_to_head(settings.database_url)
        if settings.seed_demo_data:
            with runtime.session_factory() as session:
                if seed_if_empty(runtime.deps(session)):
                    session.commit()
                    logger.info("База пуста — загружены вымышленные демо-данные")
        logger.info(
            "Клинический компас: схема %s, правила %s (%d)",
            SCHEMA_VERSION,
            runtime.contracts.rules.rule_version,
            len(runtime.contracts.rules.rules),
        )
        yield
        runtime.engine.dispose()

    app = FastAPI(
        title="Клинический компас API",
        version=SCHEMA_VERSION,
        description="Patient State v0.2, rule engine и рабочая очередь врача.",
        lifespan=lifespan,
    )
    app.state.runtime = runtime
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PUT", "PATCH", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-Internal-Token"],
        expose_headers=["Content-Disposition"],
    )
    install_error_handlers(app)
    for router in (system.router, auth.router, patients.router, doctor.router, admin.router, internal.router):
        app.include_router(router)
    if settings.web_dir is not None:
        # Собранное Flutter Web приложение с того же адреса: без CORS и отдельного сервера.
        app.mount("/", StaticFiles(directory=settings.web_dir, html=True), name="web")
    return app


def app_factory() -> FastAPI:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    return create_app()
