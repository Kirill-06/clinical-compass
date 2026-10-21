"""Единый формат ошибок API: `{"error": код, "message": текст для пользователя}`."""

import logging
from collections.abc import Sequence
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from clinical_compass.services.errors import (
    ConflictError,
    ForbiddenError,
    InvalidInputError,
    NotFoundError,
    ServiceError,
    UnauthorizedError,
)

logger = logging.getLogger("clinical_compass")

_STATUS: dict[type[ServiceError], tuple[int, str]] = {
    InvalidInputError: (400, "bad_request"),
    UnauthorizedError: (401, "unauthorized"),
    ForbiddenError: (403, "forbidden"),
    NotFoundError: (404, "not_found"),
    ConflictError: (409, "conflict"),
}


def _describe(errors: Sequence[Any]) -> str:
    """Первая ошибка валидации в виде «поле — причина» (без входных данных пациента)."""
    if not errors:
        return "ошибка"
    first = errors[0]
    where = ".".join(str(p) for p in first.get("loc", ()) if p != "body")
    return f"{where} — {first.get('msg', 'ошибка')}"


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": code, "message": message})


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ServiceError)
    async def service_error(_request: Request, exc: ServiceError) -> JSONResponse:
        status, code = next((v for k, v in _STATUS.items() if isinstance(exc, k)), (400, "bad_request"))
        return _error(status, code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
        return _error(400, "bad_request", f"Некорректные данные: {_describe(exc.errors())}")

    @app.exception_handler(ValidationError)
    async def model_error(_request: Request, exc: ValidationError) -> JSONResponse:
        return _error(
            400, "bad_request", f"Данные не соответствуют контракту v0.2: {_describe(exc.errors())}"
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
        message = "Маршрут не найден" if exc.status_code == 404 else str(exc.detail)
        return _error(exc.status_code, "not_found" if exc.status_code == 404 else "http_error", message)

    @app.exception_handler(Exception)
    async def unexpected(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Необработанная ошибка %s %s", request.method, request.url.path, exc_info=exc)
        return _error(500, "internal", "Внутренняя ошибка сервера")
