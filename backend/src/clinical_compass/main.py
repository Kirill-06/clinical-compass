"""Фабрика приложения FastAPI.

Запуск: `uvicorn clinical_compass.main:app` (или `clinical-compass serve`).
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import RequestResponseEndpoint

from clinical_compass import SCHEMA_VERSION
from clinical_compass.api.errors import install_error_handlers
from clinical_compass.api.routers import admin, auth, chat, doctor, integrations, internal, patients, system
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
    _install_frame_policy(app, settings)
    routers = (system, auth, patients, doctor, chat, admin, internal, integrations)
    for module in routers:
        app.include_router(module.router)
    if settings.web_dir is not None:
        # Собранное Flutter Web приложение с того же адреса: без CORS и отдельного сервера.
        app.mount("/", StaticFiles(directory=settings.web_dir, html=True), name="web")
    return app


_REVALIDATE_SUFFIXES = (".html", ".js", ".json", ".wasm")


def _install_frame_policy(app: FastAPI, settings: Settings) -> None:
    """Окно сервиса можно встроить только в разрешённые МИС (CSP frame-ancestors)."""
    policy = "frame-ancestors " + " ".join(settings.frame_ancestors)

    @app.middleware("http")
    async def frame_ancestors(request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = policy
        response.headers["X-Content-Type-Options"] = "nosniff"
        if request.url.path == "/" or request.url.path.endswith(_REVALIDATE_SUFFIXES):
            # Сборка Flutter обновляется целиком: браузер сверяет ETag, а не берёт старый main.dart.js.
            response.headers["Cache-Control"] = "no-cache"
        return response


def app_factory() -> FastAPI:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    return create_app()
