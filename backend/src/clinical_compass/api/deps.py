"""Зависимости маршрутов: сессия БД на запрос, текущий пользователь, служебный ключ."""

import secrets
from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Header, Request

from clinical_compass.api.runtime import Runtime
from clinical_compass.domain.enums import ExternalSystem
from clinical_compass.services.auth import AuthService
from clinical_compass.services.context import Deps, Principal
from clinical_compass.services.errors import ForbiddenError


def get_runtime(request: Request) -> Runtime:
    runtime: Runtime = request.app.state.runtime
    return runtime


RuntimeDep = Annotated[Runtime, Depends(get_runtime)]


def get_deps(runtime: RuntimeDep) -> Iterator[Deps]:
    """Одна транзакция на запрос: commit при успехе, rollback при ошибке."""
    with runtime.session_factory() as session:
        deps = runtime.deps(session)
        try:
            yield deps
            session.commit()
        except Exception:
            session.rollback()
            raise
        # Только после коммита: клиент сразу перечитает данные, и они должны уже быть в базе.
        runtime.realtime.publish(deps.outbox)


DepsDep = Annotated[Deps, Depends(get_deps)]


def get_principal(
    deps: DepsDep,
    runtime: RuntimeDep,
    authorization: Annotated[str | None, Header()] = None,
) -> Principal:
    token = authorization.removeprefix("Bearer ").strip() if authorization else None
    return AuthService(deps, runtime.settings.session_ttl_hours).authenticate(token)


PrincipalDep = Annotated[Principal, Depends(get_principal)]


def require_internal(
    runtime: RuntimeDep,
    x_internal_token: Annotated[str | None, Header()] = None,
) -> None:
    """Внутренние эндпоинты AI-слоя: только со служебным ключом."""
    expected = runtime.settings.internal_token
    if not x_internal_token or not secrets.compare_digest(x_internal_token, expected):
        raise ForbiddenError("Внутренний эндпоинт AI-слоя")


def require_integration(
    system: ExternalSystem,
    runtime: RuntimeDep,
    x_integration_key: Annotated[str | None, Header()] = None,
) -> ExternalSystem:
    """Серверные вызовы МИС: ключ своей системы в заголовке X-Integration-Key."""
    expected = runtime.settings.integration_keys.get(system.value)
    if not expected or not x_integration_key or not secrets.compare_digest(x_integration_key, expected):
        raise ForbiddenError(f"Неверный ключ интеграции {system.display_name}")
    return system


IntegrationSystem = Annotated[ExternalSystem, Depends(require_integration)]


IdempotencyKey = Annotated[str | None, Header(alias="Idempotency-Key", max_length=200)]
