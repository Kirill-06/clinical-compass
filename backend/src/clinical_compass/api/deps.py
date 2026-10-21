"""Зависимости маршрутов: сессия БД на запрос, текущий пользователь, служебный ключ."""

import secrets
from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Header, Request

from clinical_compass.api.runtime import Runtime
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
        try:
            yield runtime.deps(session)
            session.commit()
        except Exception:
            session.rollback()
            raise


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


IdempotencyKey = Annotated[str | None, Header(alias="Idempotency-Key", max_length=200)]
